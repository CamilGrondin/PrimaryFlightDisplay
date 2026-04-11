import math

import pygame

from .common import PFD_COLORS


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

        self.label_font = pygame.font.SysFont("helvetica", int(self.height // 3.9), bold=True)
        self.value_font = pygame.font.SysFont("helvetica", int(self.height // 3.2), bold=True)
        self.mode_font = pygame.font.SysFont("helvetica", int(self.height // 3.0), bold=True)
        self.meta_font = pygame.font.SysFont("helvetica", int(self.height // 3.45), bold=True)

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
        next_point: str = "DIRECT",
        next_distance_nm: float = 0.0,
        next_bearing_deg: float = 0.0,
        baro_hpa: float = 1013.0,
    ) -> None:
        self.nav1_freq = nav1_freq
        self.nav2_freq = nav2_freq
        self.com1_freq = com1_freq
        self.com2_freq = com2_freq

        self.ap_gps = ap_gps
        self.ap_ap = ap_ap
        self.ap_alt = ap_alt
        self.ap_vs = ap_vs

        # Kept for backward compatibility with existing state payloads.
        self.bug_heading = bug_heading
        self.bug_bearing = bug_bearing

        point = str(next_point).strip().upper()
        self.next_point = point[:8] if point else "DIRECT"
        self.next_distance_nm = float(next_distance_nm)
        self.next_bearing_deg = float(next_bearing_deg)
        self.baro_hpa = int(round(float(baro_hpa)))

    @staticmethod
    def _fmt_nav(value: float) -> str:
        return f"{value:06.2f}"

    @staticmethod
    def _fmt_com(value: float) -> str:
        return f"{value:07.3f}"

    @staticmethod
    def _mode_color(active: bool) -> tuple[int, int, int]:
        return PFD_COLORS["green"] if active else PFD_COLORS["text_dim"]

    @staticmethod
    def _fmt_distance(value: float) -> str:
        if not math.isfinite(value) or value <= 0.0:
            return "---"
        if value >= 100.0:
            return f"{int(round(value)):03d}"
        return f"{value:04.1f}"

    @staticmethod
    def _fmt_bearing(value: float) -> str:
        if not math.isfinite(value):
            return "---"
        return f"{int(round(value)) % 360:03d}"

    def draw_section_separators(self) -> None:
        sep_color = (95, 95, 95)
        x_left_sep = int(self.width * 0.33)
        x_right_sep = int(self.width * 0.73)
        pygame.draw.line(self.surface, sep_color, (x_left_sep, 0), (x_left_sep, self.height), width=1)
        pygame.draw.line(self.surface, sep_color, (x_right_sep, 0), (x_right_sep, self.height), width=1)

    def draw_nav_block(self) -> None:
        row1_y = int(self.height * 0.16)
        row2_y = int(self.height * 0.56)

        nav1_title = self.label_font.render("NAV1", True, PFD_COLORS["text_dim"])
        nav1_value = self.value_font.render(self._fmt_nav(self.nav1_freq), True, PFD_COLORS["text_primary"])
        nav2_title = self.label_font.render("NAV2", True, PFD_COLORS["text_dim"])
        nav2_value = self.value_font.render(self._fmt_nav(self.nav2_freq), True, PFD_COLORS["text_primary"])

        self.surface.blit(nav1_title, nav1_title.get_rect(topleft=(int(self.width * 0.018), row1_y)))
        self.surface.blit(nav1_value, nav1_value.get_rect(topleft=(int(self.width * 0.10), row1_y)))
        self.surface.blit(nav2_title, nav2_title.get_rect(topleft=(int(self.width * 0.018), row2_y)))
        self.surface.blit(nav2_value, nav2_value.get_rect(topleft=(int(self.width * 0.10), row2_y)))

    def draw_com_block(self) -> None:
        row1_y = int(self.height * 0.16)
        row2_y = int(self.height * 0.56)

        com1_title = self.label_font.render("COM1", True, PFD_COLORS["text_dim"])
        com1_value = self.value_font.render(self._fmt_com(self.com1_freq), True, PFD_COLORS["text_primary"])
        com2_title = self.label_font.render("COM2", True, PFD_COLORS["text_dim"])
        com2_value = self.value_font.render(self._fmt_com(self.com2_freq), True, PFD_COLORS["text_primary"])

        right_edge = int(self.width * 0.985)
        self.surface.blit(com1_title, com1_title.get_rect(topright=(int(self.width * 0.84), row1_y)))
        self.surface.blit(com1_value, com1_value.get_rect(topright=(right_edge, row1_y)))
        self.surface.blit(com2_title, com2_title.get_rect(topright=(int(self.width * 0.84), row2_y)))
        self.surface.blit(com2_value, com2_value.get_rect(topright=(right_edge, row2_y)))

    def draw_nextpoint_block(self) -> None:
        y_top = int(self.height * 0.13)

        title = self.label_font.render("NEXT", True, PFD_COLORS["text_dim"])
        value = self.value_font.render(self.next_point, True, PFD_COLORS["magenta"])

        self.surface.blit(title, title.get_rect(topleft=(int(self.width * 0.375), y_top)))
        self.surface.blit(value, value.get_rect(topleft=(int(self.width * 0.455), y_top)))

        meta_rect = pygame.Rect(
            int(self.width * 0.59),
            int(self.height * 0.13),
            int(self.width * 0.13),
            int(self.height * 0.38),
        )
        pygame.draw.rect(self.surface, (22, 22, 28), meta_rect)
        pygame.draw.rect(self.surface, (95, 95, 95), meta_rect, width=1)

        y_hdr = meta_rect.top + int(self.height * 0.03)
        y_val = meta_rect.top + int(self.height * 0.19)
        x_dis = meta_rect.left + int(self.width * 0.008)
        x_brg = meta_rect.left + int(self.width * 0.067)

        dis_label = self.label_font.render("DIS", True, PFD_COLORS["text_dim"])
        dis_value = self.meta_font.render(self._fmt_distance(self.next_distance_nm), True, PFD_COLORS["green"])
        brg_label = self.label_font.render("BRG", True, PFD_COLORS["text_dim"])
        brg_value = self.meta_font.render(self._fmt_bearing(self.next_bearing_deg), True, PFD_COLORS["magenta"])

        self.surface.blit(dis_label, dis_label.get_rect(topleft=(x_dis, y_hdr)))
        self.surface.blit(dis_value, dis_value.get_rect(topleft=(x_dis, y_val)))
        self.surface.blit(brg_label, brg_label.get_rect(topleft=(x_brg, y_hdr)))
        self.surface.blit(brg_value, brg_value.get_rect(topleft=(x_brg, y_val)))

    def draw_modes(self) -> None:
        y_modes = int(self.height * 0.56)
        start_x = self.width * 0.36
        spacing = self.width * 0.072

        active_modes: list[str] = []
        if self.ap_gps:
            active_modes.append("GPS")
        if self.ap_ap:
            active_modes.append("AP")
        if self.ap_vs:
            active_modes.append("VS")
        if self.ap_alt:
            active_modes.append("ALTS" if self.ap_vs else "ALT")
        if not active_modes:
            active_modes.append("OFF")

        for idx, label in enumerate(active_modes):
            color = PFD_COLORS["green"] if label != "OFF" else PFD_COLORS["text_dim"]
            txt = self.mode_font.render(label, True, color)
            txt_rect = txt.get_rect()
            txt_rect.topleft = (int(start_x + idx * spacing), y_modes)
            self.surface.blit(txt, txt_rect)

    def draw(self) -> pygame.Rect:
        self.surface.fill((18, 18, 22, 225))
        pygame.draw.rect(
            self.surface,
            PFD_COLORS["text_dim"],
            pygame.Rect(0, 0, self.width, self.height),
            width=self.border_width,
        )

        self.draw_section_separators()
        self.draw_nav_block()
        self.draw_nextpoint_block()
        self.draw_modes()
        self.draw_com_block()

        self.screen.blit(self.surface, self.surface_rect)
        return self.surface_rect
