"""
 Copyright (c) 2022 Pablo Ramirez Escudero
 
 This software is released under the MIT License.
 https://opensource.org/licenses/MIT
"""

import numpy as np
import pygame

from .common import PFD_COLORS


class VerticalSpeedIndicator:
    def __init__(self, screen: pygame.Surface, *args, **kwargs) -> None:
        self.screen = screen
        self.screen_rect = screen.get_rect()

        self.size = kwargs.get("size", 300)
        self.height = self.size
        self.width = self.size / 5
        self.position = kwargs.get("position", (0, 0))

        self.vmid = self.height / 2
        self.hmid = self.width / 2

        self.background = pygame.Surface((self.width, self.height))
        self.background = self.background.convert_alpha()
        self.background_rect = self.background.get_rect()
        self.background_rect.midleft = self.position
        self.background_color = PFD_COLORS["panel_bg"]

        self.long_lines_length = self.width / 5
        self.short_lines_length = self.long_lines_length / 2
        self.long_lines_nums = [6, 4, 2, 1, 0, -1, -2, -4, -6]
        self.short_lines_nums = [5, 3, 1.5, 0.5, -0.5, -1.5, -3, -5]

        self.height_scale = self.height / 13

        if kwargs.get("log_scale", True):
            self.vspeed2heigth = (
                lambda vspeed: (3.1 * np.log(np.abs(vspeed) + 1) - 0.12) * np.sign(vspeed) * self.height_scale
            )
        else:
            self.vspeed2heigth = lambda vspeed: vspeed * self.height_scale

        self.line_width1 = int(1 + self.size // 800)
        self.line_width2 = int(1 + self.size // 400)
        self.line_width3 = int(1 + self.size // 200)
        self.line_width4 = int(1 + self.size // 100)

        self.marks_font = pygame.font.SysFont("helvetica", int(self.size // 16.0))
        self.label_font = pygame.font.SysFont("helvetica", int(self.size // 20.0), bold=True)
        self.units_font = pygame.font.SysFont("helvetica", int(self.size // 26.0), bold=True)

        self.build_lines()

        self.update(0.0)

    def build_lines(self):
        self.long_lines = []
        self.nums_txt = []
        for num in self.long_lines_nums:
            posy = self.vmid - self.vspeed2heigth(num)
            self.long_lines.append([(self.width / 5, posy), (self.width / 5 + self.long_lines_length, posy)])
            num_txt = self.marks_font.render(f"{np.abs(num):.0f}", True, PFD_COLORS["text_primary"])
            num_txt_rect = num_txt.get_rect()
            num_txt_rect.midleft = (2, posy)
            self.nums_txt.append((num_txt, num_txt_rect))

        self.short_lines = []
        for num in self.short_lines_nums:
            posy = self.vmid - self.vspeed2heigth(num)
            self.short_lines.append([(self.width / 5, posy), (self.width / 5 + self.short_lines_length, posy)])

    def draw_lines(self):
        for yy in np.arange(self.height / 8, self.height, self.height / 8):
            pygame.draw.line(
                self.background,
                PFD_COLORS["text_dim"],
                (self.width / 5, yy),
                (self.width, yy),
                width=self.line_width1,
            )
        for kk, line in enumerate(self.long_lines):
            pygame.draw.line(self.background, PFD_COLORS["text_primary"], line[0], line[1], width=self.line_width3)
            self.background.blit(self.nums_txt[kk][0], self.nums_txt[kk][1])
        for line in self.short_lines:
            pygame.draw.line(self.background, PFD_COLORS["text_primary"], line[0], line[1], width=self.line_width3)

    def draw_hand(self):
        posy = self.vmid - self.vspeed2heigth(self.vspeed)
        pygame.draw.line(
            self.background,
            PFD_COLORS["text_primary"],
            (self.width, self.vmid),
            (self.long_lines[0][1][0], posy),
            width=self.line_width4,
        )

    def draw_label(self) -> None:
        label = self.label_font.render("VSI", True, PFD_COLORS["text_dim"])
        label_rect = label.get_rect()
        label_rect.midtop = (self.background_rect.centerx, self.background_rect.top + self.height / 30)
        self.screen.blit(label, label_rect)

        units = self.units_font.render("FT MIN", True, PFD_COLORS["text_dim"])
        units_rect = units.get_rect()
        units_rect.midbottom = (self.background_rect.centerx, self.background_rect.bottom - self.height / 30)
        self.screen.blit(units, units_rect)

    def update(self, vspeed: float):
        self.vspeed = vspeed / 1000.0

    def draw(self) -> pygame.Rect:
        self.background.fill(self.background_color)
        self.draw_lines()
        self.draw_hand()
        self.screen.blit(self.background, self.background_rect)
        return self.background_rect
