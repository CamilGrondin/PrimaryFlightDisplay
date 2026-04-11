import argparse
import json
import logging
import threading
import time

from config import Config
from display import DisplayPFD
from modes import (
    JoystickManualSource,
    MODE_JOYSTICK,
    MODE_MSP,
    MODE_XPLANE,
    MSPRealtimeSource,
    XPlaneRealtimeSource,
)

try:
    import RPi.GPIO as GPIO  # type: ignore
except Exception:  # pragma: no cover - optional dependency on non-RPi hosts
    GPIO = None


logger = logging.getLogger(__name__)


class Com1RotaryTuner:
    """Read a quadrature rotary encoder on Raspberry Pi GPIO to tune COM1."""

    def __init__(
        self,
        pin_a: int = 17,
        pin_b: int = 27,
        pin_sw: int = 22,
        pin_aux: int = 4,
        fine_step_mhz: float = 0.025,
        coarse_step_mhz: float = 1.0,
        debug: bool = False,
    ) -> None:
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.pin_sw = pin_sw
        self.pin_aux = pin_aux

        self.fine_step_mhz = fine_step_mhz
        self.coarse_step_mhz = coarse_step_mhz
        self._pending_steps = 0
        self._active = GPIO is not None
        self._gpio = GPIO
        self._last_a = 1
        self._last_b = 1
        self._last_snapshot = (1, 1, 1, 1)
        self._last_diag_t = 0.0
        self._debug = debug
        self._lock = threading.Lock()

        if not self._active:
            return

        gpio = self._gpio
        if gpio is None:
            self._active = False
            return

        gpio.setwarnings(False)
        gpio.setmode(gpio.BCM)
        gpio.setup(self.pin_a, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.setup(self.pin_b, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.setup(self.pin_sw, gpio.IN, pull_up_down=gpio.PUD_UP)
        gpio.setup(self.pin_aux, gpio.IN, pull_up_down=gpio.PUD_UP)
        self._last_snapshot = self._read_snapshot()
        self._last_a, self._last_b = self._last_snapshot[0], self._last_snapshot[1]

        # Edge interrupts avoid missing fast transitions between render frames.
        gpio.add_event_detect(self.pin_a, gpio.BOTH, callback=self._on_edge, bouncetime=1)
        gpio.add_event_detect(self.pin_b, gpio.BOTH, callback=self._on_edge, bouncetime=1)

        if self._debug:
            a, b, sw, aux = self._last_snapshot
            logger.debug("GPIO init A=%s B=%s SW=%s AUX=%s", a, b, sw, aux)

    @property
    def available(self) -> bool:
        return self._active

    def read_snapshot(self) -> dict[str, int]:
        if not self._active:
            return {}
        with self._lock:
            a, b, sw, aux = self._read_snapshot()
        return {"a": a, "b": b, "sw": sw, "aux": aux}

    def _read_ab_state(self) -> int:
        gpio = self._gpio
        if gpio is None:
            return 0
        a = gpio.input(self.pin_a)
        b = gpio.input(self.pin_b)
        return (a << 1) | b

    def _read_snapshot(self) -> tuple[int, int, int, int]:
        gpio = self._gpio
        if gpio is None:
            return (1, 1, 1, 1)
        return (
            int(gpio.input(self.pin_a)),
            int(gpio.input(self.pin_b)),
            int(gpio.input(self.pin_sw)),
            int(gpio.input(self.pin_aux)),
        )

    @staticmethod
    def _is_coarse_selected(sw: int, aux: int) -> bool:
        # Inputs use pull-up resistors: 0 means pressed.
        return sw == 0 or aux == 0

    def _step_mhz(self) -> float:
        if not self._active:
            return self.fine_step_mhz

        _, _, sw, aux = self._read_snapshot()
        if self._is_coarse_selected(sw, aux):
            return self.coarse_step_mhz
        return self.fine_step_mhz

    def _on_edge(self, _channel: int) -> None:
        if not self._active:
            return

        a, b, _, _ = self._read_snapshot()
        with self._lock:
            self._decode_step(a, b)

    def _decode_step(self, a: int, b: int) -> None:
        step = 0
        # Count one step on A rising edge, use B phase to determine direction.
        if a != self._last_a and a == 1:
            step = 1 if b == 1 else -1
        self._last_a = a
        self._last_b = b
        self._pending_steps += step

    def poll(self) -> tuple[int, float]:
        if not self._active:
            return 0, self.fine_step_mhz

        # Software fallback decode in case edge callbacks are throttled/missed.
        current_state = self._read_ab_state()
        a = (current_state >> 1) & 1
        b = current_state & 1
        with self._lock:
            self._decode_step(a, b)

        if self._debug:
            snapshot = self._read_snapshot()
            if snapshot != self._last_snapshot:
                a, b, sw, aux = snapshot
                logger.debug("GPIO A=%s B=%s SW=%s AUX=%s", a, b, sw, aux)
                self._last_snapshot = snapshot
            now = time.monotonic()
            if now - self._last_diag_t >= 3.0:
                self._last_diag_t = now
                a, b, sw, aux = self._last_snapshot
                logger.debug(
                    "GPIO idle A=%s B=%s SW=%s AUX=%s steps=%s step_mhz=%.3f",
                    a,
                    b,
                    sw,
                    aux,
                    self._pending_steps,
                    self._step_mhz(),
                )

        with self._lock:
            steps = self._pending_steps
            self._pending_steps = 0

        return steps, self._step_mhz()

    def stop(self) -> None:
        gpio = self._gpio
        if self._active and gpio is not None:
            try:
                gpio.remove_event_detect(self.pin_a)
                gpio.remove_event_detect(self.pin_b)
            except Exception:
                pass
            gpio.cleanup((self.pin_a, self.pin_b, self.pin_sw, self.pin_aux))


class XPlaneGPIOSwitchPanel:
    """Read GPIO button states and expose X-Plane-compatible switch values."""

    def __init__(
        self,
        pin_map: dict[str, int] | None = None,
        active_low: bool = True,
        debug: bool = False,
    ) -> None:
        self.pin_map = pin_map or {
            "battery_switch": 5,
            "beacon_lights": 6,
            "landing_lights": 13,
            "taxi_lights": 19,
            "nav_lights": 26,
            "strobe_lights": 20,
            "pitot_heat": 21,
        }
        self.active_low = active_low
        self._debug = debug
        self._active = GPIO is not None
        self._gpio = GPIO
        self._last_states: dict[str, int] = {}

        if not self._active:
            return

        gpio = self._gpio
        if gpio is None:
            self._active = False
            return

        gpio.setwarnings(False)
        gpio.setmode(gpio.BCM)
        pull_mode = gpio.PUD_UP if self.active_low else gpio.PUD_DOWN
        for pin in self.pin_map.values():
            gpio.setup(pin, gpio.IN, pull_up_down=pull_mode)

        self._last_states = self.read_states()
        if self._debug:
            details = ", ".join(f"{name}=GPIO{pin}" for name, pin in self.pin_map.items())
            logger.debug("GPIO switch panel init: %s", details)

    @property
    def available(self) -> bool:
        return self._active

    def read_states(self) -> dict[str, int]:
        gpio = self._gpio
        if not self._active or gpio is None:
            return {}

        states: dict[str, int] = {}
        for name, pin in self.pin_map.items():
            raw = int(gpio.input(pin))
            states[name] = 1 if (raw == 0 if self.active_low else raw == 1) else 0
        return states

    def read_raw_states(self) -> dict[str, int]:
        gpio = self._gpio
        if not self._active or gpio is None:
            return {}

        return {name: int(gpio.input(pin)) for name, pin in self.pin_map.items()}

    def poll_changed(self) -> dict[str, int] | None:
        if not self._active:
            return None

        current = self.read_states()
        if current != self._last_states:
            self._last_states = current
            if self._debug:
                pretty = ", ".join(f"{key}={value}" for key, value in sorted(current.items()))
                logger.debug("GPIO switches -> %s", pretty)
            return current
        return None

    def stop(self) -> None:
        gpio = self._gpio
        if self._active and gpio is not None:
            gpio.cleanup(tuple(self.pin_map.values()))


def _adjust_com_frequency(current: float, steps: int, step_mhz: float) -> float:
    """Adjust COM1 frequency within valid aviation band range.

    Args:
        current: Current COM frequency in MHz.
        steps: Number of steps to adjust (positive or negative).
        step_mhz: Size of each step in MHz.

    Returns:
        Adjusted frequency, clamped to [118.000, 136.975] MHz range.
    """
    com_min = Config.frequencies.com_min
    com_max = Config.frequencies.com_max

    tuned = current + steps * step_mhz
    tuned = max(com_min, min(com_max, tuned))
    return round(tuned, 3)


def _print_all_gpio_states(
    com1_tuner: Com1RotaryTuner | None,
    xplane_switch_panel: XPlaneGPIOSwitchPanel | None,
) -> None:
    chunks: list[str] = []

    if com1_tuner is not None and com1_tuner.available:
        snapshot = com1_tuner.read_snapshot()
        if snapshot:
            chunks.append(
                "COM1 "
                f"A(GPIO{com1_tuner.pin_a})={snapshot['a']} "
                f"B(GPIO{com1_tuner.pin_b})={snapshot['b']} "
                f"SW(GPIO{com1_tuner.pin_sw})={snapshot['sw']} "
                f"AUX(GPIO{com1_tuner.pin_aux})={snapshot['aux']}"
            )

    if xplane_switch_panel is not None and xplane_switch_panel.available:
        raw_states = xplane_switch_panel.read_raw_states()
        logical_states = xplane_switch_panel.read_states()
        if raw_states:
            switch_chunks = []
            for name, pin in xplane_switch_panel.pin_map.items():
                raw_value = raw_states.get(name, -1)
                logical_value = logical_states.get(name, 0)
                switch_chunks.append(f"{name}(GPIO{pin})={raw_value}/logic={logical_value}")
            chunks.append("SWITCH " + ", ".join(switch_chunks))

    if chunks:
        logger.debug("GPIO states -> %s", " | ".join(chunks))


def prompt_text(label: str, default: str | None = None) -> str:
    """Prompt user for text input with optional default value.

    Args:
        label: Prompt message display text.
        default: Default value if user enters nothing.

    Returns:
        User input or default value.

    Raises:
        ValueError: If value is required but not provided.
    """
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    raise ValueError(f"{label} is required")


def prompt_int(label: str, default: int | None = None) -> int:
    """Prompt user for integer input with optional default value.

    Args:
        label: Prompt message display text.
        default: Default value if user enters nothing.

    Returns:
        Parsed integer value.
    """
    while True:
        value = prompt_text(label, str(default) if default is not None else None)
        try:
            return int(value)
        except ValueError:
            print("Please enter a valid integer.")


def choose_mode(selected_mode: int | None = None) -> int:
    """Present mode selection menu and return user's choice.

    Args:
        selected_mode: Optional pre-selected mode from CLI.

    Returns:
        MODE_JOYSTICK (1), MODE_XPLANE (2), or MODE_MSP (3).
    """
    if selected_mode is not None:
        if selected_mode in (MODE_JOYSTICK, MODE_XPLANE, MODE_MSP):
            return selected_mode
        raise ValueError("Mode must be 1, 2, or 3.")

    print("Primary Flight Display")
    print("1 - Manual control via joystick Saitek X52")
    print("2 - Real-time data from X-Plane (UDP)")
    print("3 - IMU data from flight controller via MSP")
    while True:
        mode = prompt_int("Choose mode", 2)
        if mode in (MODE_JOYSTICK, MODE_XPLANE, MODE_MSP):
            return mode
        print("Mode must be 1, 2, or 3.")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Interactive prompts are used as fallback when an argument is omitted.
    """
    parser = argparse.ArgumentParser(description="Primary Flight Display")
    parser.add_argument("--mode", type=int, choices=[MODE_JOYSTICK, MODE_XPLANE, MODE_MSP])
    parser.add_argument("--config", help="Path to a JSON configuration file")

    parser.add_argument("--joystick-name", help="Joystick name hint for mode 1")
    parser.add_argument("--xplane-ip", help="X-Plane IP address for mode 2")
    parser.add_argument("--xplane-port", type=int, help="X-Plane UDP port for mode 2")
    parser.add_argument("--msp-port", help="MSP serial port for mode 3")
    parser.add_argument("--msp-baud", type=int, help="MSP baud rate for mode 3")

    parser.add_argument("--screen-width", type=int, help="Override screen width")
    parser.add_argument("--screen-height", type=int, help="Override screen height")
    parser.add_argument("--max-fps", type=int, help="Override display max FPS")
    parser.add_argument("--little", action="store_true", help="Use little instrument scale")

    parser.add_argument("--no-gpio-print", action="store_true", help="Disable periodic GPIO state logging")
    parser.add_argument("--gpio-print-interval", type=float, help="GPIO print interval in seconds")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    return parser.parse_args(argv)


def _load_config_file(config_path: str | None) -> None:
    if config_path is None:
        return
    with open(config_path, "r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise ValueError("Configuration file must contain a JSON object")
    Config.from_dict(loaded)


def _apply_config_overrides(args: argparse.Namespace) -> None:
    if args.screen_width is not None:
        Config.screen.width = args.screen_width
    if args.screen_height is not None:
        Config.screen.height = args.screen_height
    if args.max_fps is not None:
        Config.screen.max_fps = args.max_fps
    if args.little:
        Config.screen.little = True

    if args.xplane_ip is not None:
        Config.xplane.ip = args.xplane_ip
    if args.xplane_port is not None:
        Config.xplane.port = args.xplane_port
    if args.msp_port is not None:
        Config.msp.port = args.msp_port
    if args.msp_baud is not None:
        Config.msp.baudrate = args.msp_baud

    if args.gpio_print_interval is not None:
        Config.runtime.gpio_print_interval_s = args.gpio_print_interval
    if args.no_gpio_print:
        Config.runtime.print_gpio_states = False


def configure_logging(verbose: bool = False) -> None:
    """Configure application-wide logging."""
    configured_level = str(getattr(Config.runtime, "log_level", "INFO")).upper()
    level = logging.DEBUG if verbose else getattr(logging, configured_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def build_source(mode: int, args: argparse.Namespace):
    """Create and configure telemetry source based on selected mode.

    Args:
        mode: Operating mode (1=Joystick, 2=X-Plane, 3=MSP).
        args: Parsed CLI arguments.

    Returns:
        Initialized telemetry source (JoystickManualSource, XPlaneRealtimeSource, or MSPRealtimeSource).
    """
    if mode == MODE_JOYSTICK:
        joystick_name = args.joystick_name or prompt_text("Joystick name hint", Config.joystick.name_hint)
        source = JoystickManualSource(joystick_name_hint=joystick_name)
        logger.info("Mode 1 active: joystick manual control")
        return source

    if mode == MODE_XPLANE:
        xplane_ip = args.xplane_ip or prompt_text("X-Plane IP address", Config.xplane.ip)
        xplane_port = args.xplane_port if args.xplane_port is not None else prompt_int("X-Plane UDP port", Config.xplane.port)
        source = XPlaneRealtimeSource(ip=xplane_ip, port=xplane_port)
        source.start()
        logger.info("Mode 2 active: X-Plane UDP real-time")
        return source

    msp_port = args.msp_port or prompt_text("MSP serial port", Config.msp.port)
    msp_baud = args.msp_baud if args.msp_baud is not None else prompt_int("MSP baud rate", Config.msp.baudrate)
    source = MSPRealtimeSource(port=msp_port, baudrate=msp_baud, timeout=Config.msp.timeout)
    source.start()
    logger.info("Mode 3 active: MSP IMU real-time")
    return source


def run_pfd_loop(
    pfd: DisplayPFD,
    source,
    mode: int,
    com1_tuner: Com1RotaryTuner | None = None,
    xplane_switch_panel: XPlaneGPIOSwitchPanel | None = None,
    print_gpio_states: bool = True,
    gpio_print_interval_s: float = 0.5,
) -> None:
    """Main display loop: poll telemetry, update PFD, process COM1 tuning.

    Continuously polls the telemetry source, updates aircraft state, and renders
    the primary flight display. Handles COM1 frequency adjustment via rotary encoder.

    Args:
        pfd: DisplayPFD instance for rendering.
        source: Telemetry source (joystick, X-Plane, or MSP).
        mode: Operating mode constant.
        com1_tuner: Optional Com1RotaryTuner for GPIO-based frequency adjustment.
        xplane_switch_panel: Optional GPIO button reader for mode 2 switch states.
        print_gpio_states: If True, prints all GPIO states in loop.
        gpio_print_interval_s: Interval in seconds between GPIO state prints.

    Raises:
        RuntimeError: If telemetry source encounters an error.
    """
    state = {
        "airspeed": 0.0,
        "altitude": 0.0,
        "vertical_speed": 0.0,
        "heading": 0.0,
        "tas": 0.0,
        "course": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
        "nav1_freq": Config.frequencies.nav1,
        "nav2_freq": Config.frequencies.nav2,
        "com1_freq": Config.frequencies.com1,
        "com2_freq": Config.frequencies.com2,
        "ap_gps": True,
        "ap_ap": True,
        "ap_alt": True,
        "ap_vs": False,
        "bug_heading": 0.0,
        "bug_bearing": 0.0,
    }
    last_gpio_print_t = 0.0

    while True:
        if mode == MODE_JOYSTICK:
            data = source.poll()
        else:
            data = source.poll(timeout=0.05)

        if data is not None:
            for key, value in data.items():
                # COM1 is controlled locally by the encoder; avoid source overwrite.
                if key == "com1_freq":
                    continue
                state[key] = value

        if com1_tuner is not None:
            steps, step_mhz = com1_tuner.poll()
            if steps != 0:
                state["com1_freq"] = _adjust_com_frequency(state["com1_freq"], steps, step_mhz)
                logger.info("COM1 -> %.3f", state["com1_freq"])

        if mode == MODE_XPLANE and xplane_switch_panel is not None and hasattr(source, "update_switch_states"):
            switch_states = xplane_switch_panel.poll_changed()
            if switch_states is not None:
                source.update_switch_states(switch_states)

        if print_gpio_states:
            now = time.monotonic()
            if now - last_gpio_print_t >= gpio_print_interval_s:
                last_gpio_print_t = now
                _print_all_gpio_states(com1_tuner, xplane_switch_panel)

        pfd.update_display(
            state["airspeed"],
            state["altitude"],
            state["heading"],
            state["vertical_speed"],
            state["pitch"],
            state["roll"],
            state["course"],
            state["nav1_freq"],
            state["nav2_freq"],
            state["com1_freq"],
            state["com2_freq"],
            state["ap_gps"],
            state["ap_ap"],
            state["ap_alt"],
            state["ap_vs"],
            state["bug_heading"],
            state["bug_bearing"],
        )


def main(argv: list[str] | None = None) -> None:
    """Main entry point: initialize configuration, select mode, and run display loop."""
    args = parse_args(argv)
    _load_config_file(args.config)
    _apply_config_overrides(args)
    configure_logging(verbose=args.verbose)

    mode = choose_mode(args.mode)
    pfd = DisplayPFD(
        screen_config=Config.screen,
        frequency_defaults=Config.frequencies,
        command_defaults=Config.commands,
    )
    data_source = build_source(mode, args)

    rotary_gpio = Config.rotary.gpio
    com1_tuner = Com1RotaryTuner(
        pin_a=rotary_gpio.pin_a,
        pin_b=rotary_gpio.pin_b,
        pin_sw=rotary_gpio.pin_sw,
        pin_aux=rotary_gpio.pin_aux,
        fine_step_mhz=Config.rotary.fine_step_mhz,
        coarse_step_mhz=Config.rotary.coarse_step_mhz,
        debug=Config.rotary.debug,
    )

    switch_cfg = Config.xplane_switch_panel
    switch_pin_map = {
        "battery_switch": switch_cfg.battery_switch,
        "beacon_lights": switch_cfg.beacon_lights,
        "landing_lights": switch_cfg.landing_lights,
        "taxi_lights": switch_cfg.taxi_lights,
        "nav_lights": switch_cfg.nav_lights,
        "strobe_lights": switch_cfg.strobe_lights,
        "pitot_heat": switch_cfg.pitot_heat,
    }
    xplane_switch_panel = (
        XPlaneGPIOSwitchPanel(
            pin_map=switch_pin_map,
            active_low=switch_cfg.active_low,
            debug=switch_cfg.debug,
        )
        if mode == MODE_XPLANE
        else None
    )

    if com1_tuner.available:
        logger.info(
            "COM1 rotary tuning active on GPIO BCM A=%s B=%s SW=%s AUX=%s",
            com1_tuner.pin_a,
            com1_tuner.pin_b,
            com1_tuner.pin_sw,
            com1_tuner.pin_aux,
        )
    else:
        logger.info("RPi.GPIO not available: COM1 rotary tuning disabled")

    if xplane_switch_panel is not None:
        if xplane_switch_panel.available:
            logger.info("Mode 2 GPIO switches active: battery/beacon/landing/taxi/nav/strobe/pitot")
            if isinstance(data_source, XPlaneRealtimeSource):
                data_source.update_switch_states(xplane_switch_panel.read_states())
        else:
            logger.info("RPi.GPIO not available: mode 2 GPIO switches disabled")

    print_gpio_states = Config.runtime.print_gpio_states
    gpio_print_interval_s = Config.runtime.gpio_print_interval_s

    try:
        if print_gpio_states:
            logger.info("GPIO state print loop active (interval %.2fs)", gpio_print_interval_s)
        run_pfd_loop(
            pfd,
            data_source,
            mode,
            com1_tuner=com1_tuner,
            xplane_switch_panel=xplane_switch_panel,
            print_gpio_states=print_gpio_states,
            gpio_print_interval_s=gpio_print_interval_s,
        )
    except KeyboardInterrupt:
        logger.info("Program interrupted by user")
    finally:
        if hasattr(data_source, "stop"):
            data_source.stop()
        if xplane_switch_panel is not None:
            xplane_switch_panel.stop()
        com1_tuner.stop()


if __name__ == "__main__":
    main()
