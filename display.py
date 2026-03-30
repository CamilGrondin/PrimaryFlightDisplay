import math
import time
from pfd import AircraftState, PrimaryFlightDisplay

class DisplayPFD:
    def __init__(self):
        FPS = 1000
        SCREEN_WIDTH = 1000
        SCREEN_HEIGHT = 800

        self.PFD = PrimaryFlightDisplay((SCREEN_WIDTH, SCREEN_HEIGHT), masked=True, max_fps=60)

        f1 = 1 / 90
        f2 = 1 / 60

        self.t0 = time.time()

    def update_display(self, airspeed, altitude, heading, vertical_speed, pitch, roll=0.0, course=None):
        print("Updating PFD with new data...")
        t = time.time() - self.t0
        if course is None:
            course = heading
        state = AircraftState(
            pitch = pitch,
            roll = roll,
            airspeed = airspeed,  # knots
            airspeed_cmd=250.0,
            vspeed = vertical_speed,  # feets per minute
            altitude = altitude,  # feets
            altitude_cmd=38000.0,
            heading=heading,
            heading_cmd=20.0,
            course=course,
        )
        
        self.PFD.update(state, t)
        self.PFD.draw()
        self.PFD.render()

        print(
            f"t={t:.2f}s fps={self.PFD.fps:.0f} Pitch={state.pitch:.2f}deg Roll={state.roll:.2f}deg Airspeed={state.airspeed:.2f}kt"
            f" Vspeed={state.vspeed:.2f}ft/min Altitude={state.altitude:.2f}ft Heading={state.heading:.2f}deg"
        )


if __name__ == "__main__":
    pfd = DisplayPFD()

    # Simulated Data Update Loop
    def simulate_data():
        airspeed = 130
        altitude = 2000
        vsi = 500
        pitch = -10  # Start with negative pitch

        while True:
            pfd.update_display(airspeed, altitude, 0, vsi, pitch)
            airspeed = (airspeed + 1) % 400
            altitude = (altitude + 5) % 10000
            vsi = 2000 * math.sin(time.time())
            pitch = 10 * math.sin(time.time())  # Simulate pitch movement
            time.sleep(0.1)
            pfd.root.update()

    from threading import Thread
    Thread(target=simulate_data).start()
    pfd.run()
