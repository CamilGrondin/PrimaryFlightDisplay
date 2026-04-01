"""
 Copyright (c) 2022 Pablo Ramirez Escudero
 
 This software is released under the MIT License.
 https://opensource.org/licenses/MIT
"""


import numpy as np


PFD_COLORS = {
    "text_primary": (240, 240, 240),
    "text_dim": (185, 185, 185),
    "panel_bg": (78, 78, 78, 220),
    "panel_bg_dark": (16, 16, 16),
    "sky": (26, 92, 224),
    "ground": (112, 60, 0),
    "magenta": (240, 0, 255),
    "green": (35, 255, 0),
    "cyan": (0, 220, 255),
    "warning": (255, 218, 0),
    "danger": (255, 64, 64),
}


def quit_out_range(a: np.ndarray, min_val: float, max_val: float):
    return a[np.where((a >= min_val) & (a <= max_val))]


def get_digit(number, n):
    return number // 10**n % 10


def clip_angle_pi(angle: float) -> float:
    if angle > +np.pi:
        return angle % -np.pi
    if angle < -np.pi:
        return angle % +np.pi
    return angle


def clip_angle_180(angle: float) -> float:
    angle %= 360
    if angle > +180.0:
        return angle % -180.0
    
    return angle

def clip_angle_360(angle: float) -> float:
    angle %= 360
    if angle == 0.0:
        return 360.0
    return angle


def diff_angle_pi(angle1: float, angle2: float) -> float:
    while angle1 - angle2 > +np.pi:
        angle1 = angle1 - 2.0 * np.pi
    while angle1 - angle2 < -np.pi:
        angle1 = angle1 + 2.0 * np.pi
    return angle1 - angle2


def diff_angle_180(angle1: float, angle2: float) -> float:
    while angle1 - angle2 > +180.0:
        angle1 = angle1 - 360.0
    while angle1 - angle2 < -180.0:
        angle1 = angle1 + 360.0
    return angle1 - angle2
