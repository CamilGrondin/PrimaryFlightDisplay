"""
Configuration module for Primary Flight Display application.

Centralizes all configurable parameters like screen dimensions, default frequencies,
GPIO pins, and communication settings.
"""

from dataclasses import asdict, dataclass


@dataclass
class ScreenConfig:
    """Screen display configuration."""
    width: int = 1000
    height: int = 800
    max_fps: int = 60
    masked: bool = True
    little: bool = False


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
class XPlaneSwitchPanelConfig:
    """GPIO mapping for the optional X-Plane switch panel."""
    battery_switch: int = 5
    beacon_lights: int = 6
    landing_lights: int = 13
    taxi_lights: int = 19
    nav_lights: int = 26
    strobe_lights: int = 20
    pitot_heat: int = 21
    active_low: bool = True
    debug: bool = False


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


@dataclass
class RuntimeConfig:
    """Runtime verbosity and diagnostics behavior."""
    print_gpio_states: bool = True
    gpio_print_interval_s: float = 0.5
    log_level: str = "INFO"


class Config:
    """Main configuration singleton for the application."""

    screen: ScreenConfig = ScreenConfig()
    frequencies: FrequencyDefaults = FrequencyDefaults()
    joystick: JoystickConfig = JoystickConfig()
    xplane: XPlaneConfig = XPlaneConfig()
    xplane_switch_panel: XPlaneSwitchPanelConfig = XPlaneSwitchPanelConfig()
    msp: MSPConfig = MSPConfig()
    rotary: RotaryEncoderConfig = RotaryEncoderConfig()
    commands: CommandDefaults = CommandDefaults()
    runtime: RuntimeConfig = RuntimeConfig()

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
        if "xplane_switch_panel" in config_dict:
            cls.xplane_switch_panel = XPlaneSwitchPanelConfig(**config_dict["xplane_switch_panel"])
        if "msp" in config_dict:
            cls.msp = MSPConfig(**config_dict["msp"])
        if "rotary" in config_dict:
            rotary_cfg = dict(config_dict["rotary"])
            gpio_cfg = rotary_cfg.get("gpio")
            if isinstance(gpio_cfg, dict):
                rotary_cfg["gpio"] = GPIOConfig(**gpio_cfg)
            cls.rotary = RotaryEncoderConfig(**rotary_cfg)
        if "commands" in config_dict:
            cls.commands = CommandDefaults(**config_dict["commands"])
        if "runtime" in config_dict:
            cls.runtime = RuntimeConfig(**config_dict["runtime"])

    @classmethod
    def to_dict(cls) -> dict:
        """
        Export configuration to dictionary.

        Returns:
            Dictionary representation of all configuration.
        """
        return {
            "screen": asdict(cls.screen),
            "frequencies": asdict(cls.frequencies),
            "joystick": asdict(cls.joystick),
            "xplane": asdict(cls.xplane),
            "xplane_switch_panel": asdict(cls.xplane_switch_panel),
            "msp": asdict(cls.msp),
            "rotary": asdict(cls.rotary),
            "commands": asdict(cls.commands),
            "runtime": asdict(cls.runtime),
        }
