import numpy as np
import pygame

from .common import PFD_COLORS, clip_angle_360, diff_angle_180


class NavigationRoseIndicator:
    def __init__(self, screen: pygame.Surface, **kwargs) -> None:
        self.screen = screen
        self.screen_rect = self.screen.get_rect()

        self.size = kwargs.get("size", 230)
        self.radius = self.size / 2
        self.position = kwargs.get("position", self.screen_rect.center)

        self.surface = pygame.Surface((self.size, self.size), pygame.SRCALPHA)
        self.surface_rect = self.surface.get_rect()
        self.surface_rect.center = self.position

        self.line_width1 = max(1, int(self.size // 200))
        self.line_width2 = max(1, int(self.size // 120))
        self.line_width3 = max(1, int(self.size // 80))

        self.marks_font = pygame.font.SysFont("helvetica", int(self.size // 12.8), bold=True)
        self.small_font = pygame.font.SysFont("helvetica", int(self.size // 18.0), bold=True)

        self.update(0.0, 0.0, 0.0)

    def update(self, heading: float, course: float, command: float | None = None) -> None:
        self.heading = clip_angle_360(heading)
        self.course = clip_angle_360(course)
        if command is None:
            self.command = None
        else:
            self.command = clip_angle_360(command)

    def _polar_point(self, center: tuple[float, float], radius: float, deg: float) -> tuple[int, int]:
        rad = np.deg2rad(deg)
        return (int(center[0] + radius * np.sin(rad)), int(center[1] - radius * np.cos(rad)))

    def draw_compass_card(self) -> None:
        center = (self.radius, self.radius)
        for mark in range(0, 360, 5):
            relative = diff_angle_180(mark, self.heading)
            p1 = self._polar_point(center, self.radius * 0.92, relative)
            if mark % 30 == 0:
                p2 = self._polar_point(center, self.radius * 0.76, relative)
                pygame.draw.line(self.surface, PFD_COLORS["text_primary"], p1, p2, width=self.line_width2)
                label = None
                if mark == 0:
                    label = "N"
                elif mark == 90:
                    label = "E"
                elif mark == 180:
                    label = "S"
                elif mark == 270:
                    label = "W"
                else:
                    label = f"{int(mark / 10):02d}"
                txt = self.marks_font.render(label, True, PFD_COLORS["text_primary"])
                txt_rect = txt.get_rect()
                txt_rect.center = self._polar_point(center, self.radius * 0.60, relative)
                self.surface.blit(txt, txt_rect)
            elif mark % 10 == 0:
                p2 = self._polar_point(center, self.radius * 0.82, relative)
                pygame.draw.line(self.surface, PFD_COLORS["text_primary"], p1, p2, width=self.line_width2)
            else:
                p2 = self._polar_point(center, self.radius * 0.87, relative)
                pygame.draw.line(self.surface, PFD_COLORS["text_dim"], p1, p2, width=self.line_width1)

    def draw_course_bug(self) -> None:
        center = (self.radius, self.radius)
        relative = diff_angle_180(self.course, self.heading)
        tip = self._polar_point(center, self.radius * 0.84, relative)
        tail = self._polar_point(center, self.radius * 0.22, relative + 180)

        pygame.draw.line(self.surface, PFD_COLORS["magenta"], center, tip, width=self.line_width3)
        pygame.draw.line(self.surface, PFD_COLORS["magenta"], center, tail, width=self.line_width2)

        left = self._polar_point(tip, self.radius * 0.08, relative - 150)
        right = self._polar_point(tip, self.radius * 0.08, relative + 150)
        pygame.draw.polygon(self.surface, PFD_COLORS["magenta"], [tip, left, right], width=0)

    def draw_command_bug(self) -> None:
        if self.command is None:
            return
        center = (self.radius, self.radius)
        relative = diff_angle_180(self.command, self.heading)
        tip = self._polar_point(center, self.radius * 0.97, relative)
        left = self._polar_point(center, self.radius * 0.88, relative - 4)
        right = self._polar_point(center, self.radius * 0.88, relative + 4)
        pygame.draw.polygon(self.surface, PFD_COLORS["green"], [tip, left, right], width=0)

    def draw_aircraft_symbol(self) -> None:
        center = (self.radius, self.radius)
        wing = self.radius * 0.14
        pygame.draw.line(
            self.surface,
            PFD_COLORS["text_primary"],
            (center[0] - wing, center[1]),
            (center[0] + wing, center[1]),
            width=self.line_width3,
        )
        pygame.draw.line(
            self.surface,
            PFD_COLORS["text_primary"],
            (center[0], center[1] - wing * 0.6),
            (center[0], center[1] + wing * 1.2),
            width=self.line_width2,
        )

    def draw_labels(self) -> None:
        mode_txt = self.small_font.render("GPS  TERM", True, PFD_COLORS["magenta"])
        mode_rect = mode_txt.get_rect()
        mode_rect.center = (self.radius, self.radius + self.radius * 0.15)
        self.surface.blit(mode_txt, mode_rect)

    def draw(self) -> pygame.Rect:
        self.surface.fill((0, 0, 0, 0))

        pygame.draw.circle(self.surface, (86, 70, 46, 215), (self.radius, self.radius), self.radius)
        pygame.draw.circle(
            self.surface,
            PFD_COLORS["text_primary"],
            (self.radius, self.radius),
            self.radius * 0.95,
            width=self.line_width2,
        )

        self.draw_compass_card()
        self.draw_course_bug()
        self.draw_command_bug()
        self.draw_aircraft_symbol()
        self.draw_labels()

        self.screen.blit(self.surface, self.surface_rect)
        return self.surface_rect
