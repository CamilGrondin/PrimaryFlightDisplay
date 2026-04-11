import struct
import socket
import threading
import logging


logger = logging.getLogger(__name__)

class Simulator:
    def __init__(self, ip, port, socket_timeout_s=1.0):
        """
        Initialize the simulator with IP and port for UDP communication.
        """
        self.ip = ip
        self.port = port
        self.sock, self.address = self.initialize_socket(ip, port, socket_timeout_s)
        self._switch_lock = threading.Lock()
        self._running = threading.Event()
        self._running.set()

        self.datarefs = {
            "airspeed": (0, b'sim/flightmodel/position/indicated_airspeed\0'),
            "true_airspeed": (1, b'sim/flightmodel/position/indicated_airspeed\0'),

            "vertical_speed": (2, b'sim/cockpit2/gauges/indicators/vvi_fpm_pilot\0'),

            "altitude": (3, b'sim/cockpit2/gauges/indicators/altitude_ft_pilot\0'),

            "heading": (4, b'sim/cockpit2/gauges/indicators/heading_electric_deg_mag_pilot\0'),

            "pitch": (5, b'sim/cockpit2/gauges/indicators/pitch_electric_deg_pilot\0'),

            "battery_switch": (6, b'sim/cockpit/electrical/battery_on\0'),

            "autopilot_warning": (7, b'sim/cockpit/warnings/annunciators/autopilot\0'),
            "low_voltage_warning": (8, b'sim/cockpit/warnings/annunciators/low_voltage\0'),

            "beacon_lights": (9, b'sim/cockpit2/switches/beacon_on\0'),
            "landing_lights": (10, b'sim/cockpit2/switches/landing_lights_on\0'),
            "taxi_lights": (11, b'sim/cockpit2/switches/taxi_light_on\0'),
            "nav_lights": (12, b'sim/cockpit2/switches/navigation_lights_on\0'),
            "strobe_lights": (13, b'sim/cockpit2/switches/strobe_lights_on\0'),
            "pitot_heat": (14, b'sim/cockpit/switches/pitot_heat_on\0'),
        }

        self.breaker_states = {
            "PWR": 0,
        }

        self.switch_states_irl = {
            "battery_switch": 1,
            "beacon_lights": 0,
            "landing_lights": 0,
            "taxi_lights": 0,
            "nav_lights": 0,
            "strobe_lights": 0,
            "pitot_heat": 0,
        }

        self.switch_states_calculated = {
            "battery_switch": 0,
            "beacon_lights": 0,
            "landing_lights": 0,
            "taxi_lights": 0,
            "nav_lights": 0,
            "strobe_lights": 0,
            "pitot_heat": 0,
        }

    def initialize_socket(self, ip, port, socket_timeout_s):
        """Initialize and return a UDP socket."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(float(socket_timeout_s))
        return sock, (ip, port)

    def pack_dataref_command(self, command, frequency, index, path):
        """Pack a command for subscribing to or unsubscribing from a DataRef."""
        return struct.pack("<4sxii400s", command, frequency, index, path)

    def pack_dref_message(self, command, value, path):
        """Pack a message to set the value of a DataRef."""
        return struct.pack("<4sxf500s", command, value, path)

    def subscribe_datarefs(self):
        """Subscribe to the required DataRefs."""
        commands = [
            self.pack_dataref_command(b'RREF', 1, idx, path)
            for idx, path in self.datarefs.values()
        ]
        self.send_commands(commands)

    def unsubscribe_datarefs(self):
        """Unsubscribe from all DataRefs."""
        commands = [
            self.pack_dataref_command(b'RREF', 0, idx, path)
            for idx, path in self.datarefs.values()
        ]
        self.send_commands(commands)

    def send_commands(self, commands):
        """Send multiple commands to the simulator."""
        for cmd in commands:
            self.sock.sendto(cmd, self.address)

    def stop(self):
        """Request the simulator loop to stop and unblock socket reads."""
        self._running.clear()
        try:
            self.sock.close()
        except OSError:
            pass

    def set_switch_states(self, states):
        """Update simulator switch states from external GPIO inputs."""
        if not isinstance(states, dict):
            return
        with self._switch_lock:
            for name, value in states.items():
                if name in self.switch_states_irl:
                    self.switch_states_irl[name] = 1 if bool(value) else 0

    def _snapshot_switch_states(self):
        with self._switch_lock:
            return dict(self.switch_states_irl)

    def _refresh_calculated_switches(self, irl_states):
        """Apply breaker logic and compute outgoing switch states."""
        battery_enabled = int(self.breaker_states.get("PWR", 0) == 0 and irl_states.get("battery_switch", 0))
        self.switch_states_calculated["battery_switch"] = battery_enabled

        for switch_name in (
            "beacon_lights",
            "landing_lights",
            "taxi_lights",
            "nav_lights",
            "strobe_lights",
            "pitot_heat",
        ):
            self.switch_states_calculated[switch_name] = int(battery_enabled and irl_states.get(switch_name, 0))

    def receive_and_process_data(self):
        """Receive and process data from the simulator."""
        try:
            data, _ = self.sock.recvfrom(2048)
        except socket.timeout:
            return None
        except OSError:
            if self._running.is_set():
                raise
            return None

        header = data[:4]
        if header != b'RREF':
            logger.debug("Unknown packet header received: %s", header)
            return None
        
        results = {}
        for i in range(5, len(data), 8):
            chunk = data[i:i + 8]
            if len(chunk) != 8:
                continue
            idx, value = struct.unpack("<if", chunk)
            results[idx] = value
        return results

    def run(self, data_queue):
        """
        Run the simulation loop, continuously receiving data from X-Plane.
        
        Args:
            data_queue: Queue to send simulation data to the main thread.
        """
        self.subscribe_datarefs()
        try:
            while self._running.is_set():
                irl_states = self._snapshot_switch_states()
                self._refresh_calculated_switches(irl_states)

                beacon_command = [
                    self.pack_dref_message(b'DREF', self.switch_states_calculated["beacon_lights"], self.datarefs["beacon_lights"][1]),
                    self.pack_dref_message(b'DREF', self.switch_states_calculated["landing_lights"], self.datarefs["landing_lights"][1]),
                    self.pack_dref_message(b'DREF', self.switch_states_calculated["taxi_lights"], self.datarefs["taxi_lights"][1]),
                    self.pack_dref_message(b'DREF', self.switch_states_calculated["nav_lights"], self.datarefs["nav_lights"][1]),
                    self.pack_dref_message(b'DREF', self.switch_states_calculated["strobe_lights"], self.datarefs["strobe_lights"][1]),
                    self.pack_dref_message(b'DREF', self.switch_states_calculated["pitot_heat"], self.datarefs["pitot_heat"][1]),
                    self.pack_dref_message(b'DREF', self.switch_states_calculated["battery_switch"], self.datarefs["battery_switch"][1]),
                ]
                self.send_commands(beacon_command)

                results = self.receive_and_process_data()
                if results is None:
                    continue
                
                airspeed = max(round(results.get(self.datarefs["airspeed"][0], 0)), 0)
                altitude = round(results.get(self.datarefs["altitude"][0], 0))
                vertical_speed = round(results.get(self.datarefs["vertical_speed"][0], 0))
                heading = max(round(results.get(self.datarefs["heading"][0], 0)), 0)
                tas = max(round(results.get(self.datarefs["true_airspeed"][0], 0)), 0)
                course = max(round(results.get(self.datarefs["heading"][0], 0)), 0)
                pitch = round(results.get(self.datarefs["pitch"][0], 0))
                roll = 0
                
                # Send results to the queue
                data = {"airspeed": airspeed, "altitude": altitude, "vertical_speed": vertical_speed, "heading": heading, "tas": tas, "course": course, "pitch": pitch, "roll": roll}
                if data_queue.full():
                    try:
                        data_queue.get_nowait()
                    except Exception:
                        pass
                data_queue.put_nowait(data)
                logger.debug(
                    "X-Plane data airspeed=%s altitude=%s vertical_speed=%s heading=%s tas=%s course=%s pitch=%s roll=%s",
                    airspeed,
                    altitude,
                    vertical_speed,
                    heading,
                    tas,
                    course,
                    pitch,
                    roll,
                )
        except (OSError, TimeoutError) as e:
            if self._running.is_set():
                logger.warning("Connection error in simulator: %s", e)
                raise
        except Exception as e:
            logger.exception("Error in simulator: %s", e)
            raise
        finally:
            self._running.clear()
            logger.info("Unsubscribing from DataRefs and closing socket")
            try:
                self.unsubscribe_datarefs()
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass