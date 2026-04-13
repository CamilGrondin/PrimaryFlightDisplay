import math
import queue
import struct
import threading
import time
import logging
from dataclasses import dataclass
from typing import Dict, Optional

import pygame

from config import Config
from simulator import Simulator


logger = logging.getLogger(__name__)


TelemetryValue = float | int | bool | str
TelemetryDict = Dict[str, TelemetryValue]

try:
    import serial  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    serial = None

MODE_JOYSTICK = 1
MODE_XPLANE = 2
MODE_MSP = 3


@dataclass
class Telemetry:
    """Aircraft telemetry data structure.

    Contains all flight parameters: attitude, speed, altitude, heading,
    radio frequencies, and autopilot settings.
    """
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
    next_point: str = "DIRECT"
    next_distance_nm: float = 0.0
    next_bearing_deg: float = 0.0
    baro_hpa: float = 1013.0

    def as_dict(self) -> TelemetryDict:
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
            "next_point": self.next_point,
            "next_distance_nm": self.next_distance_nm,
            "next_bearing_deg": self.next_bearing_deg,
            "baro_hpa": self.baro_hpa,
        }


def _normalize_heading(value: float) -> float:
    """Normalize heading angle to [0, 360) range.

    Args:
        value: Heading angle in degrees.

    Returns:
        Normalized heading in [0, 360) degrees.
    """
    return value % 360.0


class JoystickManualSource:
    """Manual flight control via joystick or keyboard input.

    Reads joystick axes and simulates realistic aircraft dynamics
    including bank-to-turn calculation and speed ramping.
    """

    def __init__(self, joystick_name_hint: str | None = None, control_device: str = "auto") -> None:
        """Initialize joystick input handler.

        Args:
            joystick_name_hint: Substring to match joystick name (default from config).
            control_device: Input preference for mode 1: auto, joystick, keyboard.
        """
        joystick_cfg = Config.joystick
        command_cfg = Config.commands
        name_hint = joystick_name_hint or joystick_cfg.name_hint

        device = control_device.strip().lower()
        if device not in {"auto", "joystick", "keyboard"}:
            raise ValueError("control_device must be one of: auto, joystick, keyboard")

        pygame.joystick.init()
        count = pygame.joystick.get_count()

        selected = None
        if device != "keyboard" and count > 0:
            for idx in range(count):
                candidate = pygame.joystick.Joystick(idx)
                candidate.init()
                if name_hint.lower() in candidate.get_name().lower():
                    selected = candidate
                    break
                if selected is None:
                    selected = candidate

        if device == "joystick" and selected is None:
            logger.warning("No joystick detected. Falling back to keyboard controls for mode 1.")

        self.joystick = selected
        self.input_mode = "joystick" if self.joystick is not None else "keyboard"
        self._keyboard_throttle = 0.5
        self.keyboard_throttle_rate = 0.6
        self.telemetry = Telemetry(
            airspeed=joystick_cfg.default_airspeed,
            altitude=joystick_cfg.default_altitude,
            heading=0.0,
            tas=joystick_cfg.default_airspeed,
            nav1_freq=Config.frequencies.nav1,
            nav2_freq=Config.frequencies.nav2,
            com1_freq=Config.frequencies.com1,
            com2_freq=Config.frequencies.com2,
            next_point=Config.commands.next_point,
            next_distance_nm=float(Config.commands.next_distance_nm),
            next_bearing_deg=float(Config.commands.next_bearing_deg),
            baro_hpa=float(Config.commands.baro_hpa),
        )
        self.last_t = time.monotonic()
        self.bank_deadzone_deg = joystick_cfg.bank_deadzone_deg
        self.max_turn_rate_deg_s = joystick_cfg.max_turn_rate_deg_s
        self.speed_tau = joystick_cfg.speed_tau
        self.max_accel_kts_s = joystick_cfg.max_accel_kts_s
        self.ap_vs_threshold = command_cfg.ap_vs_threshold
        self.heading_offset_deg = command_cfg.heading_offset_deg
        self.bearing_offset_deg = command_cfg.bearing_offset_deg

        if self.input_mode == "joystick" and self.joystick is not None:
            logger.info("Manual mode joystick: %s", self.joystick.get_name())
        else:
            logger.info("Manual mode keyboard active")

    def _axis(self, index: int, default: float = 0.0) -> float:
        """Read joystick axis value with bounds checking.

        Args:
            index: Axis index number.
            default: Value if axis index out of range.

        Returns:
            Axis value in [-1.0, 1.0] or default if missing.
        """
        if self.joystick is None:
            return default
        if index >= self.joystick.get_numaxes():
            return default
        return float(self.joystick.get_axis(index))

    def _read_joystick_controls(self) -> tuple[float, float, float]:
        pygame.event.pump()

        roll_axis = self._axis(0)
        pitch_axis = self._axis(1)
        throttle_axis = -self._axis(2)
        throttle = (throttle_axis + 1.0) / 2.0
        return roll_axis, pitch_axis, throttle

    def _read_keyboard_controls(self, dt: float) -> tuple[float, float, float]:
        pygame.event.pump()
        keys = pygame.key.get_pressed()

        roll_axis = 0.0
        if keys[pygame.K_a] or keys[pygame.K_q] or keys[pygame.K_LEFT]:
            roll_axis -= 1.0
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            roll_axis += 1.0

        pitch_axis = 0.0
        if keys[pygame.K_w] or keys[pygame.K_z] or keys[pygame.K_UP]:
            pitch_axis -= 1.0
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            pitch_axis += 1.0

        if keys[pygame.K_r] or keys[pygame.K_PAGEUP]:
            self._keyboard_throttle = min(1.0, self._keyboard_throttle + self.keyboard_throttle_rate * dt)
        if keys[pygame.K_f] or keys[pygame.K_PAGEDOWN]:
            self._keyboard_throttle = max(0.0, self._keyboard_throttle - self.keyboard_throttle_rate * dt)
        if keys[pygame.K_HOME]:
            self._keyboard_throttle = 1.0
        if keys[pygame.K_END]:
            self._keyboard_throttle = 0.0

        return roll_axis, pitch_axis, self._keyboard_throttle

    def poll(self) -> TelemetryDict:
        """Poll joystick and compute simulated aircraft state.

        Processes joystick input and applies physics-based aircraft dynamics.

        Returns:
            Dictionary with telemetry data (airspeed, altitude, heading, etc.).
        """
        now = time.monotonic()
        dt = max(0.001, now - self.last_t)
        self.last_t = now

        if self.input_mode == "joystick" and self.joystick is not None:
            roll_axis, pitch_axis, throttle = self._read_joystick_controls()
        else:
            roll_axis, pitch_axis, throttle = self._read_keyboard_controls(dt)

        self.telemetry.roll = 60.0 * roll_axis
        self.telemetry.pitch = 30.0 * pitch_axis

        target_airspeed = 60.0 + 280.0 * throttle
        speed_alpha = min(1.0, dt / self.speed_tau)
        smoothed_target = self.telemetry.airspeed + (target_airspeed - self.telemetry.airspeed) * speed_alpha
        speed_step = smoothed_target - self.telemetry.airspeed
        max_step = self.max_accel_kts_s * dt
        speed_step = max(-max_step, min(max_step, speed_step))
        self.telemetry.airspeed += speed_step
        self.telemetry.tas = self.telemetry.airspeed

        bank_deg = self.telemetry.roll
        if abs(bank_deg) < self.bank_deadzone_deg:
            turn_rate_deg_s = 0.0
        else:
            speed_ms = max(self.telemetry.tas * 0.514444, 15.0)
            turn_rate_deg_s = math.degrees(9.80665 * math.tan(math.radians(bank_deg)) / speed_ms)
            turn_rate_deg_s = max(-self.max_turn_rate_deg_s, min(self.max_turn_rate_deg_s, turn_rate_deg_s))
        self.telemetry.heading = _normalize_heading(self.telemetry.heading + turn_rate_deg_s * dt)
        self.telemetry.course = self.telemetry.heading

        speed_fts = self.telemetry.tas * 1.6878098571
        self.telemetry.vertical_speed = speed_fts * math.sin(math.radians(self.telemetry.pitch)) * 60.0
        self.telemetry.altitude = max(0.0, self.telemetry.altitude + (self.telemetry.vertical_speed / 60.0) * dt)

        self.telemetry.ap_vs = abs(self.telemetry.vertical_speed) > self.ap_vs_threshold
        self.telemetry.bug_heading = _normalize_heading(self.telemetry.heading + self.heading_offset_deg)
        self.telemetry.bug_bearing = _normalize_heading(self.telemetry.course + self.bearing_offset_deg)

        return self.telemetry.as_dict()

    def stop(self) -> None:
        if self.joystick is not None:
            try:
                self.joystick.quit()
            except Exception:
                pass


class XPlaneRealtimeSource:
    """Real-time telemetry from X-Plane simulator via UDP.

    Connects to X-Plane on a local or remote host and receives aircraft
    state updates via UDP protocol.
    """

    def __init__(self, ip: str, port: int) -> None:
        """Initialize X-Plane connection parameters.

        Args:
            ip: X-Plane host IP address.
            port: X-Plane UDP port (typically 49000).
        """
        self.ip = ip
        self.port = port
        self.data_queue: "queue.Queue[TelemetryDict]" = queue.Queue(maxsize=200)
        self.error_queue: "queue.Queue[Exception]" = queue.Queue(maxsize=1)
        self.thread: Optional[threading.Thread] = None
        self.simulator: Optional[Simulator] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start background thread to receive X-Plane UDP data."""
        if self.thread is not None and self.thread.is_alive():
            return
        self._stop_event.clear()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        logger.info("X-Plane mode connected to %s:%s", self.ip, self.port)

    def _worker(self) -> None:
        """Background worker thread receiving X-Plane data."""
        try:
            self.simulator = Simulator(ip=self.ip, port=self.port)
            self.simulator.run(self.data_queue)
        except Exception as exc:
            if self.error_queue.empty() and not self._stop_event.is_set():
                self.error_queue.put(exc)
        finally:
            self.simulator = None

    def poll(self, timeout: float = 0.05) -> Optional[TelemetryDict]:
        """Poll latest X-Plane data from queue.

        Args:
            timeout: Queue timeout in seconds.

        Returns:
            Latest telemetry dict or None if queue empty.

        Raises:
            RuntimeError: If X-Plane connection failed.
        """
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
        enriched.setdefault("nav1_freq", Config.frequencies.nav1)
        enriched.setdefault("nav2_freq", Config.frequencies.nav2)
        enriched.setdefault("com1_freq", Config.frequencies.com1)
        enriched.setdefault("com2_freq", Config.frequencies.com2)
        enriched.setdefault("ap_gps", True)
        enriched.setdefault("ap_ap", True)
        enriched.setdefault("ap_alt", True)
        enriched.setdefault("ap_vs", abs(vertical_speed) > Config.commands.ap_vs_threshold)
        enriched.setdefault("bug_heading", _normalize_heading(heading + Config.commands.heading_offset_deg))
        enriched.setdefault("bug_bearing", _normalize_heading(course + Config.commands.bearing_offset_deg))
        enriched.setdefault("next_point", Config.commands.next_point)
        enriched.setdefault("next_distance_nm", float(Config.commands.next_distance_nm))
        enriched.setdefault("next_bearing_deg", course)
        enriched.setdefault("baro_hpa", float(Config.commands.baro_hpa))
        return enriched

    def update_switch_states(self, states: Dict[str, int]) -> None:
        """Push GPIO switch states to the X-Plane simulator worker thread."""
        simulator = self.simulator
        if simulator is not None:
            simulator.set_switch_states(states)

    def stop(self) -> None:
        self._stop_event.set()
        simulator = self.simulator
        if simulator is not None:
            simulator.stop()
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        self.thread = None


class MSPClient:
    """MultiWii Serial Protocol (MSP) communication client.

    Sends commands to and receives telemetry from flight controllers
    using the MSP protocol over serial connection.
    """

    MSP_ATTITUDE = 108      # Request attitude (roll, pitch, yaw)
    MSP_ALTITUDE = 109      # Request altitude and vertical speed

    def __init__(self, port: str, baudrate: int, timeout: float = 0.25) -> None:
        """Initialize MSP serial connection.

        Args:
            port: Serial port path (e.g., '/dev/ttyUSB0').
            baudrate: Serial baudrate (typically 115200).
            timeout: Read timeout in seconds.

        Raises:
            RuntimeError: If pyserial is not installed.
        """
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
        """Calculate MSP frame checksum (XOR of all payload bytes).

        Args:
            payload: Frame payload bytes.

        Returns:
            XOR checksum value.
        """
        crc = 0
        for b in payload:
            crc ^= b
        return crc

    def _request(self, cmd: int) -> None:
        """Send MSP command request.

        Args:
            cmd: MSP command code.
        """
        frame_body = bytes([0, cmd])
        frame = b"$M<" + frame_body + bytes([self._checksum(frame_body)])
        self.conn.write(frame)

    def _read_frame(self) -> Optional[tuple[int, bytes]]:
        """Read and validate MSP frame from serial.

        Returns:
            Tuple of (command, payload) or None if timeout/invalid.
        """
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
        """Send command and receive response.

        Args:
            cmd: MSP command code.

        Returns:
            Response payload or None if timeout/mismatch.
        """
        self._request(cmd)
        frame = self._read_frame()
        if frame is None:
            return None
        frame_cmd, payload = frame
        if frame_cmd != cmd:
            return None
        return payload


class MSPRealtimeSource:
    """Real-time telemetry from flight controllers via MSP serial.

    Polls MultiWii-compatible flight controllers and extracts attitude,
    altitude, and vertical speed via serial MSP protocol.
    """

    def __init__(self, port: str, baudrate: int, timeout: float | None = None) -> None:
        """Initialize MSP connection parameters.

        Args:
            port: Serial port path.
            baudrate: Serial baudrate (typically 115200).
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = Config.msp.timeout if timeout is None else timeout
        self.data_queue: "queue.Queue[TelemetryDict]" = queue.Queue(maxsize=200)
        self.error_queue: "queue.Queue[Exception]" = queue.Queue(maxsize=1)
        self.thread: Optional[threading.Thread] = None
        self._running = threading.Event()

    def start(self) -> None:
        """Start background thread to poll MSP data."""
        if self.thread is not None and self.thread.is_alive():
            return
        self._running.set()
        self.thread = threading.Thread(target=self._worker, daemon=True)
        self.thread.start()
        logger.info("MSP mode listening on %s @ %s baud", self.port, self.baudrate)

    def stop(self) -> None:
        """Stop MSP polling thread."""
        self._running.clear()
        if self.thread is not None:
            self.thread.join(timeout=2.0)
        self.thread = None

    def _worker(self) -> None:
        client = None
        try:
            client = MSPClient(self.port, self.baudrate, timeout=self.timeout)
            telemetry = Telemetry(
                airspeed=100.0,
                altitude=0.0,
                heading=0.0,
                tas=100.0,
                nav1_freq=Config.frequencies.nav1,
                nav2_freq=Config.frequencies.nav2,
                com1_freq=Config.frequencies.com1,
                com2_freq=Config.frequencies.com2,
                next_point=Config.commands.next_point,
                next_distance_nm=float(Config.commands.next_distance_nm),
                next_bearing_deg=float(Config.commands.next_bearing_deg),
                baro_hpa=float(Config.commands.baro_hpa),
            )

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

                telemetry.ap_vs = abs(telemetry.vertical_speed) > Config.commands.ap_vs_threshold
                telemetry.bug_heading = _normalize_heading(telemetry.heading + Config.commands.heading_offset_deg)
                telemetry.bug_bearing = _normalize_heading(telemetry.course + Config.commands.bearing_offset_deg)

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

    def poll(self, timeout: float = 0.05) -> Optional[TelemetryDict]:
        """Poll latest MSP data from queue.

        Args:
            timeout: Queue timeout in seconds.

        Returns:
            Latest telemetry dict or None if queue empty.

        Raises:
            RuntimeError: If MSP connection failed.
        """
        if not self.error_queue.empty():
            raise RuntimeError("MSP source stopped: " + str(self.error_queue.get()))
        try:
            return self.data_queue.get(timeout=timeout)
        except queue.Empty:
            return None
