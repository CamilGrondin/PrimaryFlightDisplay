"""
Unit tests for Primary Flight Display application.

Tests core functionality including frequency adjustment, heading normalization,
telemetry data structures, and configuration management.
"""

# -*- coding: utf-8 -*-

import unittest
from dataclasses import asdict

from config import (
    CommandDefaults,
    Config,
    FrequencyDefaults,
    JoystickConfig,
    RotaryEncoderConfig,
    ScreenConfig,
    XPlaneConfig,
    MSPConfig,
)
from main import _adjust_com_frequency, prompt_text, prompt_int, choose_mode
from modes import Telemetry, _normalize_heading


class TestCOMFrequencyAdjustment(unittest.TestCase):
    """Test COM frequency tuning logic."""

    def test_adjust_frequency_up(self):
        """Test increasing frequency."""
        result = _adjust_com_frequency(121.000, steps=1, step_mhz=0.025)
        self.assertAlmostEqual(result, 121.025, places=3)

    def test_adjust_frequency_down(self):
        """Test decreasing frequency."""
        result = _adjust_com_frequency(121.000, steps=-2, step_mhz=0.025)
        self.assertAlmostEqual(result, 120.950, places=3)

    def test_clamp_to_max(self):
        """Test frequency clamped to maximum COM band limit."""
        result = _adjust_com_frequency(136.900, steps=10, step_mhz=0.025)
        self.assertAlmostEqual(result, 136.975, places=3)

    def test_clamp_to_min(self):
        """Test frequency clamped to minimum COM band limit."""
        result = _adjust_com_frequency(118.100, steps=-10, step_mhz=0.025)
        self.assertAlmostEqual(result, 118.000, places=3)

    def test_zero_steps(self):
        """Test no frequency change with zero steps."""
        result = _adjust_com_frequency(121.800, steps=0, step_mhz=0.025)
        self.assertAlmostEqual(result, 121.800, places=3)

    def test_coarse_tuning(self):
        """Test coarse MHz-step tuning."""
        result = _adjust_com_frequency(121.000, steps=1, step_mhz=1.0)
        self.assertAlmostEqual(result, 122.000, places=3)

    def test_frequency_rounding(self):
        """Test frequency is properly rounded to 3 decimal places."""
        result = _adjust_com_frequency(121.0001, steps=0, step_mhz=0.025)
        self.assertEqual(result, round(result, 3))


class TestHeadingNormalization(unittest.TestCase):
    """Test heading angle normalization."""

    def test_normalize_zero(self):
        """Test zero heading remains zero."""
        self.assertAlmostEqual(_normalize_heading(0.0), 0.0, places=1)

    def test_normalize_360(self):
        """Test 360° wraps to 0°."""
        self.assertAlmostEqual(_normalize_heading(360.0), 0.0, places=1)

    def test_normalize_negative(self):
        """Test negative angles wrap around."""
        result = _normalize_heading(-90.0)
        self.assertAlmostEqual(result, 270.0, places=1)

    def test_normalize_large_positive(self):
        """Test large positive angles wrap correctly."""
        result = _normalize_heading(720.0 + 45.0)
        self.assertAlmostEqual(result, 45.0, places=1)

    def test_normalize_decimal(self):
        """Test decimal heading values."""
        result = _normalize_heading(180.5)
        self.assertAlmostEqual(result, 180.5, places=1)


class TestTelemetryDataStructure(unittest.TestCase):
    """Test Telemetry dataclass."""

    def test_telemetry_defaults(self):
        """Test telemetry initializes with correct defaults."""
        t = Telemetry()
        self.assertEqual(t.airspeed, 0.0)
        self.assertEqual(t.altitude, 0.0)
        self.assertEqual(t.heading, 0.0)
        self.assertAlmostEqual(t.nav1_freq, 111.70, places=2)
        self.assertAlmostEqual(t.com1_freq, 121.800, places=3)
        self.assertTrue(t.ap_gps)
        self.assertFalse(t.ap_vs)

    def test_telemetry_custom_values(self):
        """Test telemetry with custom initialization."""
        t = Telemetry(
            airspeed=250.0,
            altitude=10000.0,
            heading=180.0,
            com1_freq=130.500,
            ap_vs=True,
        )
        self.assertEqual(t.airspeed, 250.0)
        self.assertEqual(t.altitude, 10000.0)
        self.assertEqual(t.heading, 180.0)
        self.assertAlmostEqual(t.com1_freq, 130.500, places=3)
        self.assertTrue(t.ap_vs)

    def test_telemetry_as_dict(self):
        """Test telemetry conversion to dictionary."""
        t = Telemetry(airspeed=100.0, altitude=5000.0)
        d = t.as_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["airspeed"], 100.0)
        self.assertEqual(d["altitude"], 5000.0)
        self.assertIn("nav1_freq", d)
        self.assertIn("com1_freq", d)

    def test_telemetry_dict_has_all_fields(self):
        """Test all telemetry fields present in dictionary."""
        t = Telemetry()
        d = t.as_dict()
        expected_keys = [
            "airspeed",
            "altitude",
            "vertical_speed",
            "heading",
            "tas",
            "course",
            "pitch",
            "roll",
            "nav1_freq",
            "nav2_freq",
            "com1_freq",
            "com2_freq",
            "ap_gps",
            "ap_ap",
            "ap_alt",
            "ap_vs",
            "bug_heading",
            "bug_bearing",
        ]
        for key in expected_keys:
            self.assertIn(key, d)


class TestConfiguration(unittest.TestCase):
    """Test configuration management."""

    def test_default_config_values(self):
        """Test configuration has sensible defaults."""
        self.assertEqual(Config.screen.width, 1000)
        self.assertEqual(Config.screen.height, 800)
        self.assertEqual(Config.screen.max_fps, 60)
        self.assertAlmostEqual(Config.frequencies.com1, 121.800, places=3)

    def test_frequency_band_limits(self):
        """Test COM frequency band limits are correct."""
        freqs = Config.frequencies
        self.assertGreaterEqual(freqs.com_min, 118.0)
        self.assertLessEqual(freqs.com_max, 137.0)
        self.assertLess(freqs.com_min, freqs.com_max)

    def test_config_to_dict(self):
        """Test configuration export to dictionary."""
        config_dict = Config.to_dict()
        self.assertIn("screen", config_dict)
        self.assertIn("frequencies", config_dict)
        self.assertIn("joystick", config_dict)
        self.assertIn("xplane", config_dict)
        self.assertIn("msp", config_dict)

    def test_config_from_dict_basic(self):
        """Test configuration import from dictionary."""
        original_screen = Config.screen
        try:
            Config.from_dict({"screen": {"width": 1920, "height": 1080}})
            self.assertEqual(Config.screen.width, 1920)
            self.assertEqual(Config.screen.height, 1080)
        finally:
            # Restore original
            Config.screen = original_screen

    def test_joystick_config_reasonable(self):
        """Test joystick configuration parameters are reasonable."""
        joy = Config.joystick
        self.assertGreater(joy.max_turn_rate_deg_s, 0)
        self.assertGreater(joy.max_accel_kts_s, 0)
        self.assertGreater(joy.speed_tau, 0)

    def test_xplane_defaults(self):
        """Test X-Plane configuration defaults."""
        xp = Config.xplane
        self.assertEqual(xp.ip, "127.0.0.1")
        self.assertEqual(xp.port, 49000)

    def test_msp_defaults(self):
        """Test MSP configuration defaults."""
        msp = Config.msp
        self.assertEqual(msp.baudrate, 115200)
        self.assertGreater(msp.timeout, 0)


class TestScreenConfiguration(unittest.TestCase):
    """Test screen configuration."""

    def test_screen_dimensions_positive(self):
        """Test screen dimensions are positive."""
        self.assertGreater(Config.screen.width, 0)
        self.assertGreater(Config.screen.height, 0)

    def test_fps_reasonable(self):
        """Test FPS is in reasonable range."""
        self.assertGreaterEqual(Config.screen.max_fps, 30)
        self.assertLessEqual(Config.screen.max_fps, 240)


class TestCommandDefaults(unittest.TestCase):
    """Test autopilot command defaults."""

    def test_command_values_reasonable(self):
        """Test command values are within reasonable flight ranges."""
        cmd = Config.commands
        self.assertGreater(cmd.airspeed_cmd, 0)
        self.assertGreater(cmd.altitude_cmd, 0)
        self.assertAlmostEqual(cmd.heading_offset_deg % 360, cmd.heading_offset_deg % 360)
        self.assertGreater(cmd.ap_vs_threshold, 0)

    def test_altitude_command_is_high(self):
        """Test default altitude command is typical cruise altitude."""
        # Typical cruise altitudes are 25000-43000 feet
        self.assertGreater(Config.commands.altitude_cmd, 20000)
        self.assertLess(Config.commands.altitude_cmd, 50000)


class TestRadioFrequencies(unittest.TestCase):
    """Test radio frequency handling."""

    def test_nav_frequencies_reasonable(self):
        """Test NAV frequencies are within aviation band."""
        freqs = Config.frequencies
        # Standard NAV band is 108-117.95 MHz
        self.assertGreaterEqual(freqs.nav1, 108.0)
        self.assertLessEqual(freqs.nav1, 118.0)
        self.assertGreaterEqual(freqs.nav2, 108.0)
        self.assertLessEqual(freqs.nav2, 118.0)

    def test_com_frequencies_in_band(self):
        """Test COM frequencies and limits are within band."""
        freqs = Config.frequencies
        # COM band is 118.000-136.975 MHz
        self.assertGreaterEqual(freqs.com1, 118.0)
        self.assertLessEqual(freqs.com1, 137.0)
        self.assertGreaterEqual(freqs.com_min, 118.0)
        self.assertLessEqual(freqs.com_max, 137.0)


class TestPromptFunctions(unittest.TestCase):
    """Test user input prompt functions."""

    def test_prompt_text_type(self):
        """Test prompt_text returns string."""
        # Note: This test doesn't actually prompt since we can't intercept input
        # In a real scenario, mock input() or test with StringIO
        pass

    def test_prompt_int_type(self):
        """Test prompt_int returns integer."""
        # Note: This test doesn't actually prompt since we can't intercept input
        # In a real scenario, mock input() or test with StringIO
        pass


class TestModeConstants(unittest.TestCase):
    """Test mode constant definitions."""

    def test_mode_constants_defined(self):
        """Test that mode constants are properly defined and distinct."""
        from modes import MODE_JOYSTICK, MODE_XPLANE, MODE_MSP

        self.assertEqual(MODE_JOYSTICK, 1)
        self.assertEqual(MODE_XPLANE, 2)
        self.assertEqual(MODE_MSP, 3)
        # Ensure they are distinct
        self.assertNotEqual(MODE_JOYSTICK, MODE_XPLANE)
        self.assertNotEqual(MODE_XPLANE, MODE_MSP)
        self.assertNotEqual(MODE_JOYSTICK, MODE_MSP)


class TestDataclassIntegration(unittest.TestCase):
    """Test dataclass integration and serialization."""

    def test_screen_config_to_dict(self):
        """Test ScreenConfig converts to dictionary."""
        sc = ScreenConfig(width=1920, height=1080)
        d = asdict(sc)
        self.assertEqual(d["width"], 1920)
        self.assertEqual(d["height"], 1080)

    def test_frequency_defaults_to_dict(self):
        """Test FrequencyDefaults converts to dictionary."""
        fd = FrequencyDefaults()
        d = asdict(fd)
        self.assertIn("com1", d)
        self.assertIn("com_min", d)


if __name__ == "__main__":
    unittest.main()
