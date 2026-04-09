from display import DisplayPFD
import threading
import time
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


class Com1RotaryTuner:
    """Read a quadrature rotary encoder on Raspberry Pi GPIO to tune COM1."""

    def __init__(self, pin_a: int = 17, pin_b: int = 27, pin_sw: int = 22, pin_aux: int = 4) -> None:
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.pin_sw = pin_sw
        self.pin_aux = pin_aux

        self.fine_step_mhz = 0.001
        self.coarse_step_mhz = 0.001
        self._pending_steps = 0
        self._active = GPIO is not None
        self._gpio = GPIO
        self._last_a = 1
        self._last_b = 1
        self._last_snapshot = (1, 1, 1, 1)
        self._last_diag_t = 0.0
        self._debug = True
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
            print(f"GPIO init A={a} B={b} SW={sw} AUX={aux}")

    @property
    def available(self) -> bool:
        return self._active

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

    def _step_mhz(self) -> float:
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
                print(f"GPIO A={a} B={b} SW={sw} AUX={aux}")
                self._last_snapshot = snapshot
            now = time.monotonic()
            if now - self._last_diag_t >= 3.0:
                self._last_diag_t = now
                a, b, sw, aux = self._last_snapshot
                print(f"GPIO idle A={a} B={b} SW={sw} AUX={aux} steps={self._pending_steps}")

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
        debug: bool = True,
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
            print("GPIO switch panel init: " + details)

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

    def poll_changed(self) -> dict[str, int] | None:
        if not self._active:
            return None

        current = self.read_states()
        if current != self._last_states:
            self._last_states = current
            if self._debug:
                pretty = ", ".join(f"{key}={value}" for key, value in sorted(current.items()))
                print("GPIO switches -> " + pretty)
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
    com_min = 118.000
    com_max = 136.975

    tuned = current + steps * step_mhz
    tuned = max(com_min, min(com_max, tuned))
    return round(tuned, 3)


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


def choose_mode() -> int:
    """Present mode selection menu and return user's choice.

    Returns:
        MODE_JOYSTICK (1), MODE_XPLANE (2), or MODE_MSP (3).
    """
    print("Primary Flight Display")
    print("1 - Manual control via joystick Saitek X52")
    print("2 - Real-time data from X-Plane (UDP)")
    print("3 - IMU data from flight controller via MSP")
    while True:
        mode = prompt_int("Choose mode", 2)
        if mode in (MODE_JOYSTICK, MODE_XPLANE, MODE_MSP):
            return mode
        print("Mode must be 1, 2, or 3.")


def build_source(mode: int):
    """Create and configure telemetry source based on selected mode.

    Args:
        mode: Operating mode (1=Joystick, 2=X-Plane, 3=MSP).

    Returns:
        Initialized telemetry source (JoystickManualSource, XPlaneRealtimeSource, or MSPRealtimeSource).
    """
    if mode == MODE_JOYSTICK:
        joystick_name = prompt_text("Joystick name hint", "X52")
        source = JoystickManualSource(joystick_name_hint=joystick_name)
        print("Mode 1 active: joystick manual control")
        return source

    if mode == MODE_XPLANE:
        xplane_ip = prompt_text("X-Plane IP address", "127.0.0.1")
        xplane_port = prompt_int("X-Plane UDP port", 49000)
        source = XPlaneRealtimeSource(ip=xplane_ip, port=xplane_port)
        source.start()
        print("Mode 2 active: X-Plane UDP real-time")
        return source

    msp_port = prompt_text("MSP serial port", "/dev/tty.usbserial")
    msp_baud = prompt_int("MSP baud rate", 115200)
    source = MSPRealtimeSource(port=msp_port, baudrate=msp_baud)
    source.start()
    print("Mode 3 active: MSP IMU real-time")
    return source


def run_pfd_loop(
    pfd: DisplayPFD,
    source,
    mode: int,
    com1_tuner: Com1RotaryTuner | None = None,
    xplane_switch_panel: XPlaneGPIOSwitchPanel | None = None,
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
        "nav1_freq": 111.70,
        "nav2_freq": 111.70,
        "com1_freq": 121.800,
        "com2_freq": 121.800,
        "ap_gps": True,
        "ap_ap": True,
        "ap_alt": True,
        "ap_vs": False,
        "bug_heading": 0.0,
        "bug_bearing": 0.0,
    }

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
                print(f"COM1 -> {state['com1_freq']:.3f}")

        if mode == MODE_XPLANE and xplane_switch_panel is not None and hasattr(source, "update_switch_states"):
            switch_states = xplane_switch_panel.poll_changed()
            if switch_states is not None:
                source.update_switch_states(switch_states)

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


def main() -> None:
    """Main entry point: initialize configuration, select mode, and run display loop."""
    mode = choose_mode()
    pfd = DisplayPFD()
    data_source = build_source(mode)
    com1_tuner = Com1RotaryTuner(pin_a=4, pin_b=17, pin_sw=27, pin_aux=22)
    xplane_switch_panel = XPlaneGPIOSwitchPanel() if mode == MODE_XPLANE else None

    if com1_tuner.available:
        print("COM1 rotary tuning active on GPIO BCM A=4 B=17 SW=27 AUX=22")
    else:
        print("RPi.GPIO not available: COM1 rotary tuning disabled")

    if xplane_switch_panel is not None:
        if xplane_switch_panel.available:
            print("Mode 2 GPIO switches active: battery/beacon/landing/taxi/nav/strobe/pitot")
            if isinstance(data_source, XPlaneRealtimeSource):
                data_source.update_switch_states(xplane_switch_panel.read_states())
        else:
            print("RPi.GPIO not available: mode 2 GPIO switches disabled")

    try:
        run_pfd_loop(
            pfd,
            data_source,
            mode,
            com1_tuner=com1_tuner,
            xplane_switch_panel=xplane_switch_panel,
        )
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    finally:
        if hasattr(data_source, "stop"):
            data_source.stop()
        if xplane_switch_panel is not None:
            xplane_switch_panel.stop()
        com1_tuner.stop()


if __name__ == "__main__":
    main()
