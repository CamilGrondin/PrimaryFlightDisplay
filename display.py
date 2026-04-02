import math
import time
from pfd import AircraftState, PrimaryFlightDisplay


class DisplayPFD:
    def __init__(self):
        SCREEN_WIDTH = 1000
        SCREEN_HEIGHT = 800

        self.PFD = PrimaryFlightDisplay((SCREEN_WIDTH, SCREEN_HEIGHT), masked=True, max_fps=60)
        self.t0 = time.time()

    def update_display(
        self,
        airspeed,
        altitude,
        heading,
        vertical_speed,
        pitch,
        roll=0.0,
        course=None,
        nav1_freq=111.70,
        nav2_freq=111.70,
        com1_freq=121.800,
        com2_freq=121.800,
        ap_gps=True,
        ap_ap=True,
        ap_alt=True,
        ap_vs=False,
        bug_heading=0.0,
        bug_bearing=0.0,
    ):
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
