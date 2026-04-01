from display import DisplayPFD
from modes import (
    JoystickManualSource,
    MODE_JOYSTICK,
    MODE_MSP,
    MODE_XPLANE,
    MSPRealtimeSource,
    XPlaneRealtimeSource,
)

def prompt_text(label: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{label}{suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    raise ValueError(f"{label} is required")


def prompt_int(label: str, default: int | None = None) -> int:
    while True:
        value = prompt_text(label, str(default) if default is not None else None)
        try:
            return int(value)
        except ValueError:
            print("Please enter a valid integer.")


def choose_mode() -> int:
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


def run_pfd_loop(pfd: DisplayPFD, source, mode: int) -> None:
    state = {
        "airspeed": 0.0,
        "altitude": 0.0,
        "vertical_speed": 0.0,
        "heading": 0.0,
        "tas": 0.0,
        "course": 0.0,
        "pitch": 0.0,
        "roll": 0.0,
    }

    while True:
        if mode == MODE_JOYSTICK:
            data = source.poll()
        else:
            data = source.poll(timeout=0.05)

        if data is not None:
            state.update(data)

        pfd.update_display(
            state["airspeed"],
            state["altitude"],
            state["heading"],
            state["vertical_speed"],
            state["pitch"],
            state["roll"],
            state["course"],
        )


def main() -> None:
    mode = choose_mode()
    pfd = DisplayPFD()
    data_source = build_source(mode)

    try:
        run_pfd_loop(pfd, data_source, mode)
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    finally:
        if hasattr(data_source, "stop"):
            data_source.stop()


if __name__ == "__main__":
    main()