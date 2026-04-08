"""
Example demonstrating the new configuration and documentation improvements.

This script shows how to:
1. Access centralized configuration
2. Modify settings for different scenarios  
3. Run the test suite
"""

from config import Config, ScreenConfig, XPlaneConfig
from modes import Telemetry, _normalize_heading, MODE_JOYSTICK, MODE_XPLANE, MODE_MSP
from main import _adjust_com_frequency


def demo_configuration():
    """Demonstrate configuration management."""
    print("=" * 60)
    print("1. CONFIGURATION DEMO")
    print("=" * 60)

    # Display current configuration
    print(f"\n📺 Screen Configuration:")
    print(f"   Resolution: {Config.screen.width}x{Config.screen.height}")
    print(f"   Max FPS: {Config.screen.max_fps}")

    print(f"\n📻 Radio Frequencies (Default):")
    print(f"   COM1: {Config.frequencies.com1:.3f} MHz")
    print(f"   COM2: {Config.frequencies.com2:.3f} MHz")
    print(f"   COM Band: {Config.frequencies.com_min}-{Config.frequencies.com_max} MHz")
    print(f"   NAV1: {Config.frequencies.nav1:.2f} MHz")

    print(f"\n🎮 Joystick Configuration:")
    print(f"   Joystick hint: {Config.joystick.name_hint}")
    print(f"   Bank deadzone: {Config.joystick.bank_deadzone_deg}°")
    print(f"   Max turn rate: {Config.joystick.max_turn_rate_deg_s}°/s")

    print(f"\n✈️  X-Plane Connection:")
    print(f"   IP:Port: {Config.xplane.ip}:{Config.xplane.port}")

    print(f"\n🔧 MSP/Flight Controller:")
    print(f"   Port: {Config.msp.port}")
    print(f"   Baudrate: {Config.msp.baudrate}")

    print(f"\n⚙️  Autopilot Commands:")
    print(f"   Altitude command: {Config.commands.altitude_cmd} ft")
    print(f"   Airspeed command: {Config.commands.airspeed_cmd} kts")
    print(f"   Heading offset: {Config.commands.heading_offset_deg}°")


def demo_frequency_tuning():
    """Demonstrate COM frequency tuning."""
    print("\n" + "=" * 60)
    print("2. COM FREQUENCY TUNING DEMO")
    print("=" * 60)

    freq = 121.800
    print(f"\nStarting frequency: {freq:.3f} MHz")

    # Fine tuning (25 kHz steps)
    freq = _adjust_com_frequency(freq, steps=4, step_mhz=0.025)
    print(f"After +4 fine steps (25 kHz each): {freq:.3f} MHz")

    # Coarse tuning (1 MHz steps)
    freq = _adjust_com_frequency(freq, steps=-1, step_mhz=1.0)
    print(f"After -1 coarse step (1 MHz): {freq:.3f} MHz")

    # Hit max limit
    freq = _adjust_com_frequency(136.900, steps=10, step_mhz=0.025)
    print(f"Attempting to go above max: {freq:.3f} MHz (clamped to max)")

    # Hit min limit
    freq = _adjust_com_frequency(118.100, steps=-10, step_mhz=0.025)
    print(f"Attempting to go below min: {freq:.3f} MHz (clamped to min)")


def demo_heading_normalization():
    """Demonstrate heading angle normalization."""
    print("\n" + "=" * 60)
    print("3. HEADING NORMALIZATION DEMO")
    print("=" * 60)

    test_headings = [0, 90, 180, 270, 360, 450, -90, 720.5]
    print("\nNormalizing heading angles to [0, 360) range:")
    for heading in test_headings:
        normalized = _normalize_heading(heading)
        print(f"   {heading:7.1f}° → {normalized:6.1f}°")


def demo_telemetry():
    """Demonstrate telemetry data structure."""
    print("\n" + "=" * 60)
    print("4. TELEMETRY DATA STRUCTURE DEMO")
    print("=" * 60)

    # Create telemetry with default values
    telem1 = Telemetry()
    print(f"\nDefault telemetry:")
    print(f"   Airspeed: {telem1.airspeed} kts")
    print(f"   Altitude: {telem1.altitude} ft")
    print(f"   Heading: {telem1.heading}°")
    print(f"   AP GPS: {telem1.ap_gps}")

    # Create telemetry with custom values
    telem2 = Telemetry(
        airspeed=250.0,
        altitude=10000.0,
        heading=180.0,
        pitch=5.0,
        roll=15.0,
        vertical_speed=500.0,
        com1_freq=130.500,
        nav1_freq=114.30,
    )
    print(f"\nCustom flight state:")
    print(f"   Aircraft state: {telem2.pitch:+.1f}° pitch, {telem2.roll:+.1f}° roll")
    print(f"   Performance: {telem2.airspeed} kts, {telem2.altitude} ft, {telem2.vertical_speed:+.0f} fpm")
    print(f"   Heading/Course: {telem2.heading}° / {telem2.course}°")
    print(f"   Radios: COM1={telem2.com1_freq:.3f}, NAV1={telem2.nav1_freq:.2f}")

    # Convert to dictionary
    telem_dict = telem2.as_dict()
    print(f"\nTelemetry as dictionary (serializable):")
    print(f"   Keys: {list(telem_dict.keys())}")


def demo_config_customization():
    """Demonstrate configuration customization."""
    print("\n" + "=" * 60)
    print("5. CONFIGURATION CUSTOMIZATION DEMO")
    print("=" * 60)

    print(f"\nCurrent configuration state:")
    current_config = Config.to_dict()
    print(f"   Screen: {current_config['screen']}")

    # Create a custom configuration (simulator scenario)
    custom_config = {
        "screen": {"width": 1920, "height": 1080, "max_fps": 120},
        "xplane": {"ip": "192.168.1.100", "port": 49000},
        "joystick": {"name_hint": "Thrustmaster", "max_turn_rate_deg_s": 15.0},
    }

    print(f"\nApplying custom configuration for simulator setup...")
    Config.from_dict(custom_config)
    print(f"   Screen: {Config.screen.width}x{Config.screen.height} @ {Config.screen.max_fps} FPS")
    print(f"   X-Plane: {Config.xplane.ip}:{Config.xplane.port}")
    print(f"   Joystick: {Config.joystick.name_hint}, turn rate: {Config.joystick.max_turn_rate_deg_s}°/s")

    # Restore defaults by recreating
    print(f"\nRestoring defaults...")
    Config.screen = ScreenConfig()
    Config.xplane = XPlaneConfig()
    print(f"   Restored to: {Config.screen.width}x{Config.screen.height}")


def demo_operation_modes():
    """Show available operation modes."""
    print("\n" + "=" * 60)
    print("6. OPERATION MODES")
    print("=" * 60)

    modes = {
        MODE_JOYSTICK: "Manual control via joystick Saitek X52",
        MODE_XPLANE: "Real-time data from X-Plane (UDP)",
        MODE_MSP: "IMU data from flight controller via MSP (serial)",
    }

    print("\nAvailable operation modes:\n")
    for mode_id, description in modes.items():
        print(f"   Mode {mode_id}: {description}")


def main():
    """Run all demonstrations."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 10 + "PRIMARY FLIGHT DISPLAY - IMPROVEMENTS DEMO" + " " * 5 + "║")
    print("╚" + "=" * 58 + "╝")

    demo_configuration()
    demo_frequency_tuning()
    demo_heading_normalization()
    demo_telemetry()
    demo_config_customization()
    demo_operation_modes()

    print("\n" + "=" * 60)
    print("✅ IMPROVEMENTS SUMMARY")
    print("=" * 60)
    print("""
✨ Configuration Management:
   - All parameters centralized in config.py
   - Easy customization via Config.from_dict()
   - Supports serialization for saving/loading

📚 Documentation:
   - Comprehensive docstrings on all functions
   - Full type hints for IDE support
   - Clear parameter and return documentation

🧪 Unit Tests:
   - 34 regression tests
   - All critical functions covered
   - Run: python -m unittest test_pfd -v

📖 Learn more:
   - See IMPROVEMENTS.md for detailed guide
   - Check docstrings in source code
""")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
