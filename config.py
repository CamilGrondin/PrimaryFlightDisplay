"""
Configuration module for Primary Flight Display application.

Centralizes all configurable parameters like screen dimensions, default frequencies,
GPIO pins, and communication settings.
"""

from dataclasses import dataclass


@dataclass
class ScreenConfig:
    """Screen display configuration."""
    width: int = 1000
    height: int = 800
    max_fps: int = 60
    masked: bool = True


@dataclass
class FrequencyDefaults:
    """Default radio frequencies."""
    nav1: float = 111.70
    nav2: float = 111.70
    com1: float = 121.800
    com2: float = 121.800
    com_min: float = 118.000
    com_max: float = 136.975


@dataclass
class GPIOConfig:
    """GPIO configuration for Raspberry Pi rotary encoder."""
    pin_a: int = 17          # CLK
    pin_b: int = 27          # DT
    pin_sw: int = 22         # Switch
    pin_aux: int = 4         # Auxiliary


@dataclass
class RotaryEncoderConfig:
    """Rotary encoder tuning configuration."""
    gpio: GPIOConfig = None  # Will be initialized in __post_init__
    fine_step_mhz: float = 0.025
    coarse_step_mhz: float = 1.0
    debug: bool = False

    def __post_init__(self):
        if self.gpio is None:
            self.gpio = GPIOConfig()


@dataclass
class JoystickConfig:
    """Joystick input configuration."""
    name_hint: str = "X52"
    bank_deadzone_deg: float = 1.5
    max_turn_rate_deg_s: float = 12.0
    speed_tau: float = 1.4
    max_accel_kts_s: float = 18.0
    default_airspeed: float = 120.0
    default_altitude: float = 1500.0


@dataclass
class XPlaneConfig:
    """X-Plane UDP connection configuration."""
    ip: str = "127.0.0.1"
    port: int = 49000


@dataclass
class MSPConfig:
    """MSP serial connection configuration."""
    port: str = "/dev/tty.usbserial"
    baudrate: int = 115200
    timeout: float = 0.25
    max_retries: int = 3


@dataclass
class CommandDefaults:
    """Default autopilot command values."""
    airspeed_cmd: float = 250.0
    altitude_cmd: float = 38000.0
    heading_offset_deg: float = 8.0      # Bug heading offset
    bearing_offset_deg: float = 95.0     # Bug bearing offset
    ap_vs_threshold: float = 300.0       # Vertical speed threshold for AP


class Config:
    """Main configuration singleton for the application."""

    screen: ScreenConfig = ScreenConfig()
    frequencies: FrequencyDefaults = FrequencyDefaults()
    joystick: JoystickConfig = JoystickConfig()
    xplane: XPlaneConfig = XPlaneConfig()
    msp: MSPConfig = MSPConfig()
    rotary: RotaryEncoderConfig = RotaryEncoderConfig()
    commands: CommandDefaults = CommandDefaults()

    @classmethod
    def from_dict(cls, config_dict: dict) -> None:
        """
        Load configuration from a dictionary.

        Args:
            config_dict: Dictionary with config sections like 'screen', 'frequencies', etc.
        """
        if "screen" in config_dict:
            cls.screen = ScreenConfig(**config_dict["screen"])
        if "frequencies" in config_dict:
            cls.frequencies = FrequencyDefaults(**config_dict["frequencies"])
        if "joystick" in config_dict:
            cls.joystick = JoystickConfig(**config_dict["joystick"])
        if "xplane" in config_dict:
            cls.xplane = XPlaneConfig(**config_dict["xplane"])
        if "msp" in config_dict:
            cls.msp = MSPConfig(**config_dict["msp"])
        if "commands" in config_dict:
            cls.commands = CommandDefaults(**config_dict["commands"])

    @classmethod
    def to_dict(cls) -> dict:
        """
        Export configuration to dictionary.

        Returns:
            Dictionary representation of all configuration.
        """
        return {
            "screen": cls.screen.__dict__,
            "frequencies": cls.frequencies.__dict__,
            "joystick": cls.joystick.__dict__,
            "xplane": cls.xplane.__dict__,
            "msp": cls.msp.__dict__,
            "commands": cls.commands.__dict__,
        }
