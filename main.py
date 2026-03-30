import argparse

from display import DisplayPFD
from modes import (
    JoystickManualSource,
    MODE_JOYSTICK,
    MODE_MSP,
    MODE_XPLANE,
    MSPRealtimeSource,
    XPlaneRealtimeSource,
)

# Create an instance of the DisplayPFD class
pfd = DisplayPFD()

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Primary Flight Display mode selector")
    parser.add_argument("--mode", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument("--xplane-ip", default="127.0.0.1")
    parser.add_argument("--xplane-port", type=int, default=49000)
    parser.add_argument("--msp-port", default="/dev/tty.usbserial")
    parser.add_argument("--msp-baud", type=int, default=115200)
    parser.add_argument("--joystick-name", default="X52")
    return parser


def start_source(args: argparse.Namespace):
    if args.mode == MODE_JOYSTICK:
        source = JoystickManualSource(joystick_name_hint=args.joystick_name)
        print("Mode 1 active: joystick manual control")
        return source

    if args.mode == MODE_XPLANE:
        source = XPlaneRealtimeSource(ip=args.xplane_ip, port=args.xplane_port)
        source.start()
        print("Mode 2 active: X-Plane UDP real-time")
        return source

    source = MSPRealtimeSource(port=args.msp_port, baudrate=args.msp_baud)
    source.start()
    print("Mode 3 active: MSP IMU real-time")
    return source


def run_pfd_loop(source, mode: int) -> None:
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


if __name__ == "__main__":
    cli_args = build_parser().parse_args()
    data_source = start_source(cli_args)

    try:
        run_pfd_loop(data_source, cli_args.mode)
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    finally:
        if hasattr(data_source, "stop"):
            data_source.stop()