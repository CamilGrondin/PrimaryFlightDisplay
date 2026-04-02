import pygame

from .common import PFD_COLORS, clip_angle_360


class TopBarIndicator:
    def __init__(self, screen: pygame.Surface, **kwargs) -> None:
        self.screen = screen
        self.screen_rect = self.screen.get_rect()

        self.width = int(kwargs.get("width", self.screen_rect.w * 0.72))
        self.height = int(kwargs.get("height", self.screen_rect.h * 0.09))
        self.position = kwargs.get("position", self.screen_rect.midtop)

        self.surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        self.surface_rect = self.surface.get_rect()
        self.surface_rect.midtop = self.position

        self.border_width = max(1, int(self.height // 24))

        self.label_font = pygame.font.SysFont("helvetica", int(self.height // 3.7), bold=True)
        self.value_font = pygame.font.SysFont("helvetica", int(self.height // 3.3), bold=True)
        self.mode_font = pygame.font.SysFont("helvetica", int(self.height // 3.0), bold=True)

        self.update()

    def update(
        self,
        nav1_freq: float = 111.70,
        nav2_freq: float = 111.70,
        com1_freq: float = 121.800,
        com2_freq: float = 121.800,
        ap_gps: bool = True,
        ap_ap: bool = True,
        ap_alt: bool = True,
        ap_vs: bool = False,
        bug_heading: float = 0.0,
        bug_bearing: float = 0.0,
    ) -> None:
        self.nav1_freq = nav1_freq
        self.nav2_freq = nav2_freq
        self.com1_freq = com1_freq
        self.com2_freq = com2_freq

        self.ap_gps = ap_gps
        self.ap_ap = ap_ap
        self.ap_alt = ap_alt
        self.ap_vs = ap_vs

        self.bug_heading = clip_angle_360(bug_heading)
        self.bug_bearing = clip_angle_360(bug_bearing)

    @staticmethod
    def _fmt_nav(value: float) -> str:
        return f"{value:06.2f}"

    @staticmethod
    def _fmt_com(value: float) -> str:
        return f"{value:07.3f}"

    @staticmethod
    def _mode_color(active: bool) -> tuple[int, int, int]:
        return PFD_COLORS["green"] if active else PFD_COLORS["text_dim"]

    def draw_modes(self) -> None:
        modes = [
            ("GPS", self.ap_gps),
            ("AP", self.ap_ap),
            ("ALT", self.ap_alt),
            ("VS", self.ap_vs),
        ]

        center_x = self.width * 0.5
        spacing = self.width * 0.08
        start_x = center_x - spacing * (len(modes) - 1) * 0.5

        for idx, (label, active) in enumerate(modes):
            txt = self.mode_font.render(label, True, self._mode_color(active))
            txt_rect = txt.get_rect()
            txt_rect.midtop = (int(start_x + idx * spacing), int(self.height * 0.53))
            self.surface.blit(txt, txt_rect)

    def draw_heading_block(self) -> None:
        hdg_txt = self.label_font.render("HDG", True, PFD_COLORS["cyan"])
        hdg_val = self.value_font.render(f"{self.bug_heading:03.0f}", True, PFD_COLORS["cyan"])
        brg_txt = self.label_font.render("BRG", True, PFD_COLORS["magenta"])
        brg_val = self.value_font.render(f"{self.bug_bearing:03.0f}", True, PFD_COLORS["magenta"])

        x0 = int(self.width * 0.40)
        y0 = int(self.height * 0.12)

        self.surface.blit(hdg_txt, hdg_txt.get_rect(topleft=(x0, y0)))
        self.surface.blit(hdg_val, hdg_val.get_rect(topleft=(int(x0 + self.width * 0.05), y0)))
        self.surface.blit(brg_txt, brg_txt.get_rect(topleft=(int(x0 + self.width * 0.14), y0)))
        self.surface.blit(brg_val, brg_val.get_rect(topleft=(int(x0 + self.width * 0.19), y0)))

    def draw(self) -> pygame.Rect:
        self.surface.fill((24, 24, 24, 220))
        pygame.draw.rect(
            self.surface,
            PFD_COLORS["text_dim"],
            pygame.Rect(0, 0, self.width, self.height),
            width=self.border_width,
        )

        nav1_title = self.label_font.render("NAV1", True, PFD_COLORS["text_dim"])
        nav1_value = self.value_font.render(self._fmt_nav(self.nav1_freq), True, PFD_COLORS["text_primary"])
        nav2_title = self.label_font.render("NAV2", True, PFD_COLORS["text_dim"])
        nav2_value = self.value_font.render(self._fmt_nav(self.nav2_freq), True, PFD_COLORS["text_primary"])

        self.surface.blit(nav1_title, nav1_title.get_rect(topleft=(int(self.width * 0.02), int(self.height * 0.15))))
        self.surface.blit(nav1_value, nav1_value.get_rect(topleft=(int(self.width * 0.10), int(self.height * 0.15))))
        self.surface.blit(nav2_title, nav2_title.get_rect(topleft=(int(self.width * 0.20), int(self.height * 0.15))))
        self.surface.blit(nav2_value, nav2_value.get_rect(topleft=(int(self.width * 0.28), int(self.height * 0.15))))

        self.draw_heading_block()

        com1_title = self.label_font.render("COM1", True, PFD_COLORS["text_dim"])
        com1_value = self.value_font.render(self._fmt_com(self.com1_freq), True, PFD_COLORS["text_primary"])
        com2_title = self.label_font.render("COM2", True, PFD_COLORS["text_dim"])
        com2_value = self.value_font.render(self._fmt_com(self.com2_freq), True, PFD_COLORS["text_primary"])

        rbase = int(self.width * 0.98)
        self.surface.blit(com1_title, com1_title.get_rect(topright=(int(rbase - self.width * 0.17), int(self.height * 0.15))))
        self.surface.blit(com1_value, com1_value.get_rect(topright=(rbase, int(self.height * 0.15))))
        self.surface.blit(com2_title, com2_title.get_rect(topright=(int(rbase - self.width * 0.17), int(self.height * 0.52))))
        self.surface.blit(com2_value, com2_value.get_rect(topright=(rbase, int(self.height * 0.52))))

        self.draw_modes()

        self.screen.blit(self.surface, self.surface_rect)
        return self.surface_rect
