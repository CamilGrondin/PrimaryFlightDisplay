import math
import time

from config import CommandDefaults, Config, FrequencyDefaults, ScreenConfig
from pfd import AircraftState, PrimaryFlightDisplay


class DisplayPFD:
    """Wrapper for Primary Flight Display rendering.

    Manages screen configuration and aircraft state visualization.
    """

    def __init__(
        self,
        screen_config: ScreenConfig | None = None,
        frequency_defaults: FrequencyDefaults | None = None,
        command_defaults: CommandDefaults | None = None,
    ):
        """Initialize display with configurable screen and aircraft defaults."""
        self.screen_config = screen_config or Config.screen
        self.frequency_defaults = frequency_defaults or Config.frequencies
        self.command_defaults = command_defaults or Config.commands

        self.PFD = PrimaryFlightDisplay(
            (self.screen_config.width, self.screen_config.height),
            masked=self.screen_config.masked,
            max_fps=self.screen_config.max_fps,
            little=self.screen_config.little,
        )
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
        nav1_freq: float | None = None,
        nav2_freq: float | None = None,
        com1_freq: float | None = None,
        com2_freq: float | None = None,
        ap_gps: bool = True,
        ap_ap: bool = True,
        ap_alt: bool = True,
        ap_vs: bool = False,
        bug_heading: float | None = None,
        bug_bearing: float | None = None,
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
            nav1_freq: NAV1 frequency in MHz (default from config).
            nav2_freq: NAV2 frequency in MHz (default from config).
            com1_freq: COM1 frequency in MHz (default from config).
            com2_freq: COM2 frequency in MHz (default from config).
            ap_gps: Autopilot GPS mode active (default: True).
            ap_ap: Autopilot mode active (default: True).
            ap_alt: Autopilot altitude hold active (default: True).
            ap_vs: Autopilot vertical speed mode active (default: False).
            bug_heading: Heading bug position in degrees (defaults to heading).
            bug_bearing: Bearing bug position in degrees (defaults to course).
        """
        t = time.time() - self.t0
        if course is None:
            course = heading
        if bug_heading is None:
            bug_heading = heading
        if bug_bearing is None:
            bug_bearing = course

        if nav1_freq is None:
            nav1_freq = self.frequency_defaults.nav1
        if nav2_freq is None:
            nav2_freq = self.frequency_defaults.nav2
        if com1_freq is None:
            com1_freq = self.frequency_defaults.com1
        if com2_freq is None:
            com2_freq = self.frequency_defaults.com2

        state = AircraftState(
            pitch=pitch,
            roll=roll,
            airspeed=airspeed,
            airspeed_cmd=self.command_defaults.airspeed_cmd,
            vspeed=vertical_speed,
            altitude=altitude,
            altitude_cmd=self.command_defaults.altitude_cmd,
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
