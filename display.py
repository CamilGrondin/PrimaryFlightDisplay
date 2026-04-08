import math
import time
from pfd import AircraftState, PrimaryFlightDisplay


class DisplayPFD:
    """Wrapper for Primary Flight Display rendering.

    Manages screen configuration and aircraft state visualization.
    """

    def __init__(self):
        """Initialize display with default screen dimensions."""
        SCREEN_WIDTH = 1000
        SCREEN_HEIGHT = 800

        self.PFD = PrimaryFlightDisplay((SCREEN_WIDTH, SCREEN_HEIGHT), masked=True, max_fps=60)
        self.t0 = time.time()

    def update_display(
        self,
        airspeed: float,
        altitude: float,
        heading: float,
        vertical_speed: float,
        pitch: float,
        roll: float = 0.0,
        course: float | None = None,
        nav1_freq: float = 111.70,
        nav2_freq: float = 111.70,
        com1_freq: float = 121.800,
        com2_freq: float = 121.800,
        ap_gps: bool = True,
        ap_ap: bool = True,
        ap_alt: bool = True,
        ap_vs: bool = False,
        bug_heading: float = 0.0,
        bug_bearing: float = 0.0,
    ) -> None:
        """Update and render the Primary Flight Display with current aircraft state.

        Args:
            airspeed: True airspeed in knots.
            altitude: Altitude in feet.
            heading: Magnetic heading in degrees (0-360).
            vertical_speed: Vertical speed in feet per minute.
            pitch: Aircraft pitch angle in degrees.
            roll: Aircraft roll angle in degrees (default: 0).
            course: Wind course in degrees; defaults to heading if None.
            nav1_freq: NAV1 frequency in MHz (default: 111.70).
            nav2_freq: NAV2 frequency in MHz (default: 111.70).
            com1_freq: COM1 frequency in MHz (default: 121.800).
            com2_freq: COM2 frequency in MHz (default: 121.800).
            ap_gps: Autopilot GPS mode active (default: True).
            ap_ap: Autopilot mode active (default: True).
            ap_alt: Autopilot altitude hold active (default: True).
            ap_vs: Autopilot vertical speed mode active (default: False).
            bug_heading: Heading bug position in degrees (default: 0).
            bug_bearing: Bearing bug position in degrees (default: 0).
        """
        t = time.time() - self.t0
        if course is None:
            course = heading
        if bug_heading == 0.0:
            bug_heading = heading
        if bug_bearing == 0.0:
            bug_bearing = course

        state = AircraftState(
            pitch=pitch,
            roll=roll,
            airspeed=airspeed,
            airspeed_cmd=250.0,
            vspeed=vertical_speed,
            altitude=altitude,
            altitude_cmd=38000.0,
            heading=heading,
            heading_cmd=bug_heading,
            course=course,
            nav1_freq=nav1_freq,
            nav2_freq=nav2_freq,
            com1_freq=com1_freq,
            com2_freq=com2_freq,
            ap_gps=ap_gps,
            ap_ap=ap_ap,
            ap_alt=ap_alt,
            ap_vs=ap_vs,
            bug_heading=bug_heading,
            bug_bearing=bug_bearing,
        )

        self.PFD.update(state, t)
        self.PFD.draw()
        self.PFD.render()


if __name__ == "__main__":
    pfd = DisplayPFD()

    def simulate_data():
        airspeed = 130
        altitude = 2000
        vsi = 500
        pitch = -10

        while True:
            pfd.update_display(airspeed, altitude, 0, vsi, pitch)
            airspeed = (airspeed + 1) % 400
            altitude = (altitude + 5) % 10000
            vsi = 2000 * math.sin(time.time())
            pitch = 10 * math.sin(time.time())
            time.sleep(0.1)

    from threading import Thread

    Thread(target=simulate_data).start()
