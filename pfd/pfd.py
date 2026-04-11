"""
 Copyright (c) 2022 Pablo Ramirez Escudero
 
 This software is released under the MIT License.
 https://opensource.org/licenses/MIT
"""

import sys
from dataclasses import dataclass

import numpy as np
import pygame

from .airspeed import AirspeedIndicator
from .airspeed_little import AirspeedIndicatorLittle
from .altimeter import AltitudeIndicator
from .altimeter_little import AltitudeIndicatorLittle
from .attitude import ArtificalHorizon
from .heading import HeadingIndicator
from .topbar import TopBarIndicator
from .vspeed import VerticalSpeedIndicator
from .vspeed_little import VerticalSpeedIndicatoLittle


@dataclass
class AircraftState:
    ### artificial horizon inputs
    roll: float
    pitch: float
    ### airspeed indicator inputs
    airspeed: float
    airspeed_cmd: float
    ### altitude indicator inputs
    altitude: float
    altitude_cmd: float
    ### vspeed indicator inputs
    vspeed: float
    ### heading indicator inputs
    heading: float
    heading_cmd: float
    course: float
    ### top bar telemetry
    nav1_freq: float = 111.70
    nav2_freq: float = 111.70
    com1_freq: float = 121.800
    com2_freq: float = 121.800
    ap_gps: bool = True
    ap_ap: bool = True
    ap_alt: bool = True
    ap_vs: bool = False
    bug_heading: float = 0.0
    bug_bearing: float = 0.0
    next_point: str = "DIRECT"
    next_distance_nm: float = 0.0
    next_bearing_deg: float = 0.0
    baro_hpa: float = 1013.0


class PrimaryFlightDisplay:
    def __init__(self, resolution: tuple, **kwargs) -> None:
        self.resolution = resolution

        pygame.init()
        self.game_clock = pygame.time.Clock()
        self.screen = pygame.display.set_mode((self.resolution[0], self.resolution[1]))
        self.screen_rect = self.screen.get_rect()
        pygame.display.set_caption("Primary Flight Display - v1.0")

        self.max_fps = kwargs.get("max_fps", None)
        self.fps = 0.0

        self.size = min(self.resolution)
        self.unit = self.size / 16

        self.top_bar_indicator = TopBarIndicator(
            self.screen,
            width=self.size * 1.05,
            height=self.size / 11.0,
            position=(self.screen_rect.centerx, self.screen_rect.top + self.size / 60),
        )

        self.artifical_horizon = ArtificalHorizon(self.screen, size=self.size / 2)
        self.airspeed_indicator = AirspeedIndicator(
            self.screen,
            size=self.size / 2,
            position=(self.screen_rect.center[0] - self.unit * 5, self.screen_rect.center[1]),
        )
        self.altitude_indicator = AltitudeIndicator(
            self.screen,
            size=self.size / 2,
            position=(self.screen_rect.center[0] + self.unit * 5, self.screen_rect.center[1]),
        )
        self.vspeed_indicator = VerticalSpeedIndicator(
            self.screen,
            size=self.size / 2.5,
            position=(self.altitude_indicator.background_rect.right + self.size / 100, self.screen_rect.center[1]),
        )
        self.heading_indicator = HeadingIndicator(
            self.screen,
            size=self.size / 2,
            position=(self.screen_rect.center[0], self.screen_rect.center[1] + self.unit * 5.55),
        )

        self.render_rects = [self.screen_rect]
        self.text_color = (0, 0, 0)

        self.masked = kwargs.get("masked", False)
        if self.masked:
            self.render_rects = self.get_render_rects()
            self.text_color = (255, 255, 255)
            self.ah_screen = pygame.Surface((self.resolution[1] / 2, self.resolution[1] / 2))
            self.ah_screen_rect = self.ah_screen.get_rect()
            self.ah_screen_rect.center = self.screen_rect.center
            self.artifical_horizon = ArtificalHorizon(self.ah_screen, size=self.resolution[1] / 2)

        self.little = kwargs.get("little", False)
        if self.little:
            self.airspeed_indicator = AirspeedIndicatorLittle(
                self.screen,
                size=self.size / 2,
                position=(self.screen_rect.center[0] - self.unit * 5, self.screen_rect.center[1]),
            )
            self.altitude_indicator = AltitudeIndicatorLittle(
                self.screen,
                size=self.size / 2,
                position=(self.screen_rect.center[0] + self.unit * 5, self.screen_rect.center[1]),
            )
            self.vspeed_indicator = VerticalSpeedIndicatoLittle(
                self.screen,
                size=self.size / 2.5,
                position=(self.altitude_indicator.background_rect.right + self.size / 100, self.screen_rect.center[1]),
            )

    def update(self, state: AircraftState, real_time: float = None, sim_time: float = None) -> None:
        self.state = state
        self.top_bar_indicator.update(
            nav1_freq=state.nav1_freq,
            nav2_freq=state.nav2_freq,
            com1_freq=state.com1_freq,
            com2_freq=state.com2_freq,
            ap_gps=state.ap_gps,
            ap_ap=state.ap_ap,
            ap_alt=state.ap_alt,
            ap_vs=state.ap_vs,
            bug_heading=state.bug_heading,
            bug_bearing=state.bug_bearing,
            next_point=state.next_point,
            next_distance_nm=state.next_distance_nm,
            next_bearing_deg=state.next_bearing_deg,
            baro_hpa=state.baro_hpa,
        )
        self.artifical_horizon.update(state.roll, state.pitch)
        self.airspeed_indicator.update(state.airspeed, state.airspeed_cmd)
        self.altitude_indicator.update(state.altitude, state.altitude_cmd, state.baro_hpa)
        self.vspeed_indicator.update(state.vspeed)
        self.heading_indicator.update(state.heading, state.course, state.heading_cmd)

    def get_render_rects(self) -> list:
        render_rects = []
        render_rects.append(self.top_bar_indicator.draw())
        render_rects.append(self.artifical_horizon.draw())
        render_rects.append(self.airspeed_indicator.draw())
        render_rects.append(self.altitude_indicator.draw())
        render_rects.append(self.vspeed_indicator.draw())
        render_rects.append(self.heading_indicator.draw())
        return render_rects

    def draw_render_rects(self) -> None:
        for rect in self.render_rects:
            pygame.draw.rect(self.screen, (255, 0, 0), rect, width=1)

    def draw_aux_lines(self) -> None:
        N = 16
        for k in range(N + 1):
            posx = 0 + k * self.screen_rect.w / N
            p1 = (posx, 0)
            p2 = (posx, self.screen_rect.h)
            pygame.draw.line(self.screen, (255, 255, 0), p1, p2, width=1)
        for k in range(N + 1):
            posy = 0 + k * self.screen_rect.h / N
            p1 = (0, posy)
            p2 = (self.screen_rect.w, posy)
            pygame.draw.line(self.screen, (255, 255, 0), p1, p2, width=1)

    def draw(self, debug: bool = False) -> None:
        self.screen.fill((0, 0, 0))
        self.top_bar_indicator.draw()
        self.artifical_horizon.draw()
        if self.masked:
            self.screen.blit(self.ah_screen, self.ah_screen_rect)
        self.airspeed_indicator.draw()
        self.vspeed_indicator.draw()
        self.altitude_indicator.draw()
        self.heading_indicator.draw()
        if debug:
            self.artifical_horizon.draw_aux_axis()

    def render(self):
        ### pygame event handler
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()  # exit pg screen
                sys.exit()  # exit python script
        ### pygame screen update (rendering)
        pygame.display.update(self.render_rects)
        if self.max_fps is None:
            self.game_clock.tick()
        else:
            self.game_clock.tick(self.max_fps)
        self.fps = self.game_clock.get_fps()
