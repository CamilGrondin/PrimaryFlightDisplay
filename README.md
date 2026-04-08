# PrimaryFlightDisplay

A Primary Flight Display (PFD) interface created with Pygame for real-time visualization of aircraft attitude, speed, and altitude. The interface supports two versions tailored for different aircraft characteristics.

![screenshot](screenshot.png)

## Features

- Real-time display and update of aircraft state parameters
- Smooth animation of flight dynamics
- Customizable screen dimensions and frame rates
- Two versions of the interface with different ranges and units:
  - Standard version for commercial aircraft
  - Alternative version (`little=True` in object instantiation) for drones or small aircrafts

## Getting Started

1. Clone the repository:
    ```bash
    git clone https://github.com/pabloramesc/PrimaryFlightDisplay.git
    ```

2. Open the project folder:
    ```bash
    cd PrimaryFlightDisplay
    ```

3. Install the required packages:
    ```bash
    pip install numpy pygame
    ```

    On Raspberry Pi, for COM1 tuning with a GPIO rotary encoder, also install:
    ```bash
    pip install RPi.GPIO
    ```

    For MSP mode (mode 3), also install:
    ```bash
    pip install pyserial
    ```

4. Run an example:
    ```bash
    python example.py
    ```

## Usage

### Mode Selector

The application now supports three runtime modes:

- Mode 1: Manual control with joystick (Saitek X52 preferred)
- Mode 2: Real-time X-Plane data through UDP
- Mode 3: IMU data from a flight controller through MSP (serial)

### COM1 Tuning From Raspberry Pi GPIO

The main loop can tune COM1 with a PT65 301 rotary encoder on BCM GPIO pins:

- A (CLK): GPIO 17
- B (DT): GPIO 27
- SW: GPIO 22
- AUX: GPIO 4

Rotation updates COM1 frequency in 25 kHz steps by default. Holding SW (22) or AUX (4) enables coarse 1 MHz steps.

Examples:

```bash
# Mode 1: Joystick
python main.py --mode 1 --joystick-name X52

# Mode 2: X-Plane UDP
python main.py --mode 2 --xplane-ip 127.0.0.1 --xplane-port 49000

# Mode 3: MSP serial
python main.py --mode 3 --msp-port /dev/tty.usbserial --msp-baud 115200
```

Below is an example demonstrating how to use the PFD interface with `AircraftState` and `PrimaryFlightDisplay`:

```python
from pfd import AircraftState, PrimaryFlightDisplay

# Create a PrimaryFlightDisplay object
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 800
PFD = PrimaryFlightDisplay(
    (SCREEN_WIDTH, SCREEN_HEIGHT),
    masked=True,
    max_fps=60,
    little=False
)

# Create an AircraftState object
state = AircraftState(
    pitch=10.0,             # degrees
    roll=20.0,              # degrees
    airspeed=250.0,         # knots
    airspeed_cmd=250.0,     # knots
    vspeed=1000.0,          # feets per minute
    altitude=30000.0,       # feets
    altitude_cmd=30000.0,   # feets
    heading=180.0,          # degrees
    heading_cmd=180.0,      # degrees
    course=185.0            # degrees
)

# Update the PFD with the current AircraftState
elapsed_time = 10.0  # Simulating 10 seconds of elapsed time
PFD.update(state, elapsed_time)

# Draw the updated PFD display
PFD.draw()

# Render the Pygame display
PFD.render()

```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
