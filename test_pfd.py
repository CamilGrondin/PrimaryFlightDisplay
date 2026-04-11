"""
Unit tests for Primary Flight Display application.

Tests core functionality including frequency adjustment, heading normalization,
telemetry data structures, and configuration management.
"""

# -*- coding: utf-8 -*-

import unittest
from unittest.mock import patch
from dataclasses import asdict
import time

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
from main import Com1RotaryTuner, _adjust_com_frequency, parse_args, prompt_text, prompt_int, choose_mode
from modes import JoystickManualSource, MSPRealtimeSource, Telemetry, XPlaneRealtimeSource, _normalize_heading
from simulator import Simulator


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
        self.assertEqual(t.next_point, "DIRECT")
        self.assertEqual(t.next_distance_nm, 0.0)
        self.assertEqual(t.next_bearing_deg, 0.0)
        self.assertEqual(int(t.baro_hpa), 1013)

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
            "next_point",
            "next_distance_nm",
            "next_bearing_deg",
            "baro_hpa",
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
        self.assertIn("xplane_switch_panel", config_dict)
        self.assertIn("msp", config_dict)
        self.assertIn("rotary", config_dict)
        self.assertIn("runtime", config_dict)

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

    def test_rotary_nested_gpio_from_dict(self):
        """Test nested GPIO config loading for rotary settings."""
        original_rotary = Config.rotary
        try:
            Config.from_dict(
                {
                    "rotary": {
                        "fine_step_mhz": 0.05,
                        "coarse_step_mhz": 0.5,
                        "gpio": {"pin_a": 10, "pin_b": 11, "pin_sw": 12, "pin_aux": 13},
                    }
                }
            )
            self.assertAlmostEqual(Config.rotary.fine_step_mhz, 0.05, places=3)
            self.assertAlmostEqual(Config.rotary.coarse_step_mhz, 0.5, places=3)
            self.assertEqual(Config.rotary.gpio.pin_a, 10)
            self.assertEqual(Config.rotary.gpio.pin_b, 11)
            self.assertEqual(Config.rotary.gpio.pin_sw, 12)
            self.assertEqual(Config.rotary.gpio.pin_aux, 13)
        finally:
            Config.rotary = original_rotary


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
        self.assertTrue(cmd.next_point)
        self.assertGreaterEqual(cmd.next_distance_nm, 0)
        self.assertGreaterEqual(cmd.next_bearing_deg, 0)
        self.assertLess(cmd.next_bearing_deg, 360)
        self.assertGreaterEqual(cmd.baro_hpa, 900)
        self.assertLessEqual(cmd.baro_hpa, 1100)

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
        with patch("builtins.input", return_value="abc"):
            self.assertEqual(prompt_text("Label"), "abc")

    def test_prompt_text_uses_default(self):
        """Test prompt_text returns default when input is empty."""
        with patch("builtins.input", return_value=""):
            self.assertEqual(prompt_text("Label", "fallback"), "fallback")

    def test_prompt_int_type(self):
        """Test prompt_int returns integer."""
        with patch("builtins.input", side_effect=["bad", "42"]):
            with patch("builtins.print"):
                self.assertEqual(prompt_int("Number"), 42)

    def test_choose_mode_preselected(self):
        """Test choose_mode accepts a valid preselected mode."""
        self.assertEqual(choose_mode(2), 2)

    def test_choose_mode_invalid_preselected(self):
        """Test choose_mode rejects invalid preselected mode."""
        with self.assertRaises(ValueError):
            choose_mode(99)


class TestCliParsing(unittest.TestCase):
    """Test command-line argument parsing."""

    def test_parse_args_mode2_with_udp_options(self):
        args = parse_args(["--mode", "2", "--xplane-ip", "10.0.0.8", "--xplane-port", "49001"])
        self.assertEqual(args.mode, 2)
        self.assertEqual(args.xplane_ip, "10.0.0.8")
        self.assertEqual(args.xplane_port, 49001)

    def test_parse_args_gpio_flags(self):
        args = parse_args(["--no-gpio-print", "--gpio-print-interval", "0.25"])
        self.assertTrue(args.no_gpio_print)
        self.assertAlmostEqual(args.gpio_print_interval, 0.25, places=2)

    def test_parse_args_control_device_keyboard(self):
        args = parse_args(["--mode", "1", "--control-device", "keyboard"])
        self.assertEqual(args.control_device, "keyboard")


class TestMode1InputSelection(unittest.TestCase):
    """Test joystick/keyboard input selection behavior for mode 1."""

    def test_keyboard_mode_fallback_when_no_joystick(self):
        with patch("modes.pygame.joystick.get_count", return_value=0):
            source = JoystickManualSource(control_device="keyboard")
            self.assertEqual(source.input_mode, "keyboard")

    def test_joystick_mode_requires_joystick(self):
        with patch("modes.pygame.joystick.get_count", return_value=0):
            with self.assertRaises(RuntimeError):
                JoystickManualSource(control_device="joystick")


class TestCom1RotarySelection(unittest.TestCase):
    """Test rotary encoder step mode selection."""

    def test_coarse_selected_when_switch_pressed(self):
        self.assertTrue(Com1RotaryTuner._is_coarse_selected(sw=0, aux=1))

    def test_coarse_selected_when_aux_pressed(self):
        self.assertTrue(Com1RotaryTuner._is_coarse_selected(sw=1, aux=0))

    def test_fine_selected_when_no_button_pressed(self):
        self.assertFalse(Com1RotaryTuner._is_coarse_selected(sw=1, aux=1))


class _FakeSimulator:
    """Simple fake simulator for source lifecycle tests."""

    last_instance = None

    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.stop_called = False
        _FakeSimulator.last_instance = self

    def set_switch_states(self, _states):
        return None

    def run(self, _data_queue):
        while not self.stop_called:
            time.sleep(0.01)

    def stop(self):
        self.stop_called = True


class TestSourceLifecycle(unittest.TestCase):
    """Test start/stop lifecycle for realtime sources."""

    def test_xplane_source_start_stop(self):
        with patch("modes.Simulator", _FakeSimulator):
            source = XPlaneRealtimeSource(ip="127.0.0.1", port=49000)
            source.start()
            time.sleep(0.05)
            source.stop()
            self.assertIsNone(source.thread)
            self.assertIsNotNone(_FakeSimulator.last_instance)
            self.assertTrue(_FakeSimulator.last_instance.stop_called)

    def test_msp_stop_without_start(self):
        source = MSPRealtimeSource(port="/dev/null", baudrate=115200)
        source.stop()
        self.assertIsNone(source.thread)


class TestXPlaneDataRefs(unittest.TestCase):
    """Regression tests for X-Plane dataref subscriptions."""

    def test_roll_dataref_is_subscribed(self):
        simulator = Simulator(ip="127.0.0.1", port=49000)
        try:
            self.assertIn("roll", simulator.datarefs)
            self.assertEqual(simulator.datarefs["roll"][1], b"sim/flightmodel/position/phi\0")
            self.assertIn("gps_distance_nm", simulator.datarefs)
            self.assertIn("gps_bearing_deg_mag", simulator.datarefs)
            self.assertIn("gps2_distance_nm", simulator.datarefs)
            self.assertIn("gps2_bearing_deg_mag", simulator.datarefs)
            self.assertIn("baro_inhg", simulator.datarefs)
            self.assertIn("gps_nav_id_0", simulator.datarefs)
            self.assertIn("gps2_nav_id_0", simulator.datarefs)
            self.assertIn("gps_dme_id_0", simulator.datarefs)
            self.assertIn("gps2_dme_id_0", simulator.datarefs)
            self.assertIn("ap_servos_on", simulator.datarefs)
            self.assertIn("ap_nav_status", simulator.datarefs)
            self.assertIn("ap_gpss_status", simulator.datarefs)
            self.assertIn("ap_heading_is_gpss", simulator.datarefs)
            self.assertIn("ap_altitude_hold_status", simulator.datarefs)
            self.assertIn("ap_alts_armed", simulator.datarefs)
            self.assertIn("ap_alts_captured", simulator.datarefs)
            self.assertIn("ap_vvi_status", simulator.datarefs)
            self.assertIn("ap_alt_vvi_is_showing_vvi", simulator.datarefs)
        finally:
            simulator.stop()


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
