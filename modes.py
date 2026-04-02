import math
import queue
import struct
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

import pygame

from simulator import Simulator

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    serial = None

MODE_JOYSTICK = 1
MODE_XPLANE = 2
MODE_MSP = 3


@dataclass
class Telemetry:
    airspeed: float = 0.0
    altitude: float = 0.0
    vertical_speed: float = 0.0
    heading: float = 0.0
    tas: float = 0.0
    course: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0

    nav1_freq: float = 111.70
    nav2_freq: float = 111.70
    com1_freq: float = 121.800
    com2_freq: float = 121.800

    ap_gps: bool = True
    ap_ap: bool = True
    ap_alt: bool = True
    ap_vs: bool = False

    bug_heading: float = 0.0
    bug_bearing: float = 0.0

    def as_dict(self) -> Dict[str, float | bool]:
        return {
            "airspeed": self.airspeed,
            "altitude": self.altitude,
            "vertical_speed": self.vertical_speed,
            "heading": self.heading,
            "tas": self.tas,
            "course": self.course,
            "pitch": self.pitch,
            "roll": self.roll,
            "nav1_freq": self.nav1_freq,
            "nav2_freq": self.nav2_freq,
            "com1_freq": self.com1_freq,
            "com2_freq": self.com2_freq,
            "ap_gps": self.ap_gps,
            "ap_ap": self.ap_ap,
            "ap_alt": self.ap_alt,
            "ap_vs": self.ap_vs,
            "bug_heading": self.bug_heading,
            "bug_bearing": self.bug_bearing,
        }


def _normalize_heading(value: float) -> float:
    return value % 360.0


class JoystickManualSource:
    def __init__(self, joystick_name_hint: str = "X52") -> None:
        pygame.joystick.init()
        count = pygame.joystick.get_count()
        if count <= 0:
            raise RuntimeError("No joystick detected. Connect a joystick and restart.")

        selected = None
        for idx in range(count):
            candidate = pygame.joystick.Joystick(idx)
            candidate.init()
            if joystick_name_hint.lower() in candidate.get_name().lower():
                selected = candidate
                break
            if selected is None:
                selected = candidate

        if selected is None:
            raise RuntimeError("Unable to initialize joystick.")

        self.joystick = selected
        self.telemetry = Telemetry(airspeed=120.0, altitude=1500.0, heading=0.0, tas=120.0)
        self.last_t = time.monotonic()
        self.yaw_deadzone = 0.08
        self.speed_tau = 1.4
        self.max_accel_kts_s = 18.0

        print("Manual mode joystick: " + self.joystick.get_name())

    def _axis(self, index: int, default: float = 0.0) -> float:
        if index >= self.joystick.get_numaxes():
            return default
        return float(self.joystick.get_axis(index))

    def poll(self) -> Dict[str, float | bool]:
        pygame.event.pump()

        now = time.monotonic()
        dt = max(0.001, now - self.last_t)
        self.last_t = now

        roll_axis = self._axis(0)
        pitch_axis = self._axis(1)
        throttle_axis = -self._axis(2)
        yaw_axis = self._axis(3)

        throttle = (throttle_axis + 1.0) / 2.0

        self.telemetry.roll = 60.0 * roll_axis
        self.telemetry.pitch = 30.0 * pitch_axis

        if abs(yaw_axis) < self.yaw_deadzone:
            yaw_rate = 0.0
        else:
            yaw_input = (abs(yaw_axis) - self.yaw_deadzone) / (1.0 - self.yaw_deadzone)
            yaw_rate = math.copysign(yaw_input, yaw_axis) * 45.0
        self.telemetry.heading = _normalize_heading(self.telemetry.heading + yaw_rate * dt)

        target_airspeed = 60.0 + 280.0 * throttle
        speed_alpha = min(1.0, dt / self.speed_tau)
        smoothed_target = self.telemetry.airspeed + (target_airspeed - self.telemetry.airspeed) * speed_alpha
        speed_step = smoothed_target - self.telemetry.airspeed
        max_step = self.max_accel_kts_s * dt
        speed_step = max(-max_step, min(max_step, speed_step))
        self.telemetry.airspeed += speed_step
        self.telemetry.tas = self.telemetry.airspeed
        self.telemetry.course = self.telemetry.heading

        speed_fts = self.telemetry.tas * 1.6878098571
        self.telemetry.vertical_speed = speed_fts * math.sin(math.radians(self.telemetry.pitch)) * 60.0
        self.telemetry.altitude = max(0.0, self.telemetry.altitude + (self.telemetry.vertical_speed / 60.0) * dt)

        self.telemetry.ap_vs = abs(self.telemetry.vertical_speed) > 300.0
        self.telemetry.bug_heading = _normalize_heading(self.telemetry.heading + 8.0)
        self.telemetry.bug_bearing = _normalize_heading(self.telemetry.course + 95.0)

        return self.telemetry.as_dict()

    def stop(self) -> None:
        try:
            self.joystick.quit()
        except Exception:
            pass


class XPlaneRealtimeSource:
    def __init__(self, ip: str, port: int) -> None:
        self.ip = ip
        self.port = port
        self.data_queue: "queue.Queue[Dict[str, float]]" = queue.Queue(maxsize=200)
        self.error_queue: "queue.Queue[Exception]" = queue.Queue(maxsize=1)
        self.thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.thread is not None:
            return
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        print(f"X-Plane mode connected to {self.ip}:{self.port}")

    def _worker(self) -> None:
        try:
            simulator = Simulator(ip=self.ip, port=self.port)
            simulator.run(self.data_queue)
        except Exception as exc:
            if self.error_queue.empty():
                self.error_queue.put(exc)

    def poll(self, timeout: float = 0.05) -> Optional[Dict[str, float | bool]]:
        if not self.error_queue.empty():
            raise RuntimeError("X-Plane source stopped: " + str(self.error_queue.get()))
        try:
            data = self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None

        heading = _normalize_heading(float(data.get("heading", 0.0)))
        course = _normalize_heading(float(data.get("course", heading)))
        vertical_speed = float(data.get("vertical_speed", 0.0))

        enriched = dict(data)
        enriched.setdefault("nav1_freq", 111.70)
        enriched.setdefault("nav2_freq", 111.70)
        enriched.setdefault("com1_freq", 121.800)
        enriched.setdefault("com2_freq", 121.800)
        enriched.setdefault("ap_gps", True)
        enriched.setdefault("ap_ap", True)
        enriched.setdefault("ap_alt", True)
        enriched.setdefault("ap_vs", abs(vertical_speed) > 200.0)
        enriched.setdefault("bug_heading", _normalize_heading(heading + 8.0))
        enriched.setdefault("bug_bearing", _normalize_heading(course + 95.0))
        return enriched

    def stop(self) -> None:
        pass


class MSPClient:
    MSP_ATTITUDE = 108
    MSP_ALTITUDE = 109

    def __init__(self, port: str, baudrate: int, timeout: float = 0.25) -> None:
        if serial is None:
            raise RuntimeError("pyserial is required for MSP mode. Install with: pip install pyserial")
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.conn = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def _checksum(self, payload: bytes) -> int:
        crc = 0
        for b in payload:
            crc ^= b
        return crc

    def _request(self, cmd: int) -> None:
        frame_body = bytes([0, cmd])
        frame = b"$M<" + frame_body + bytes([self._checksum(frame_body)])
        self.conn.write(frame)

    def _read_frame(self) -> Optional[tuple[int, bytes]]:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.conn.read(1) != b"$":
                continue
            if self.conn.read(1) != b"M":
                continue
            direction = self.conn.read(1)
            if direction not in (b">", b"!"):
                continue

            size_raw = self.conn.read(1)
            cmd_raw = self.conn.read(1)
            if len(size_raw) != 1 or len(cmd_raw) != 1:
                return None

            size = size_raw[0]
            cmd = cmd_raw[0]
            payload = self.conn.read(size)
            crc_raw = self.conn.read(1)
            if len(payload) != size or len(crc_raw) != 1:
                return None

            frame_body = size_raw + cmd_raw + payload
            if self._checksum(frame_body) != crc_raw[0]:
                continue
            if direction == b"!":
                return None
            return cmd, payload
        return None

    def request(self, cmd: int) -> Optional[bytes]:
        self._request(cmd)
        frame = self._read_frame()
        if frame is None:
            return None
        frame_cmd, payload = frame
        if frame_cmd != cmd:
            return None
        return payload


class MSPRealtimeSource:
    def __init__(self, port: str, baudrate: int) -> None:
        self.port = port
        self.baudrate = baudrate
        self.data_queue: "queue.Queue[Dict[str, float]]" = queue.Queue(maxsize=200)
        self.error_queue: "queue.Queue[Exception]" = queue.Queue(maxsize=1)
        self.thread: Optional[threading.Thread] = None
        self._running = threading.Event()

    def start(self) -> None:
        if self.thread is not None:
            return
        self._running.set()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        print(f"MSP mode listening on {self.port} @ {self.baudrate} baud")

    def stop(self) -> None:
        self._running.clear()

    def _worker(self) -> None:
        client = None
        try:
            client = MSPClient(self.port, self.baudrate)
            telemetry = Telemetry(airspeed=100.0, altitude=0.0, heading=0.0, tas=100.0)

            while self._running.is_set():
                att_payload = client.request(MSPClient.MSP_ATTITUDE)
                if att_payload is not None and len(att_payload) >= 6:
                    angx, angy, heading = struct.unpack("<hhh", att_payload[:6])
                    telemetry.roll = float(angx) / 10.0
                    telemetry.pitch = float(angy) / 10.0
                    telemetry.heading = _normalize_heading(float(heading))
                    telemetry.course = telemetry.heading

                alt_payload = client.request(MSPClient.MSP_ALTITUDE)
                if alt_payload is not None and len(alt_payload) >= 6:
                    est_alt_cm, vario_cms = struct.unpack("<ih", alt_payload[:6])
                    telemetry.altitude = float(est_alt_cm) / 30.48
                    telemetry.vertical_speed = float(vario_cms) * 1.96850394

                synthetic_airspeed = 80.0 + min(80.0, abs(telemetry.vertical_speed) / 40.0)
                telemetry.airspeed = synthetic_airspeed
                telemetry.tas = synthetic_airspeed

                telemetry.ap_vs = abs(telemetry.vertical_speed) > 300.0
                telemetry.bug_heading = _normalize_heading(telemetry.heading + 8.0)
                telemetry.bug_bearing = _normalize_heading(telemetry.course + 95.0)

                if self.data_queue.full():
                    try:
                        self.data_queue.get_nowait()
                    except queue.Empty:
                        pass
                self.data_queue.put(telemetry.as_dict())
                time.sleep(0.05)

        except Exception as exc:
            if self.error_queue.empty():
                self.error_queue.put(exc)
        finally:
            if client is not None:
                client.close()

    def poll(self, timeout: float = 0.05) -> Optional[Dict[str, float | bool]]:
        if not self.error_queue.empty():
            raise RuntimeError("MSP source stopped: " + str(self.error_queue.get()))
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None
