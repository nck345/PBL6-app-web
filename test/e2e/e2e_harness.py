import json
import math
import os
import re
import socket
import struct
import sys
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

def topic_matches(pattern: str, topic: str) -> bool:
	if pattern == topic or pattern == "#":
		return True
	p_parts = pattern.split("/")
	t_parts = topic.split("/")
	for i, p in enumerate(p_parts):
		if p == "#":
			return True
		if i >= len(t_parts):
			return False
		if p != "+" and p != t_parts[i]:
			return False
	return len(p_parts) == len(t_parts)

class EmbeddedMqttBroker:
	def __init__(self, host: str = "127.0.0.1", port: int = 0):
		self.host = host
		self.port = port
		self.running = False
		self.lock = threading.RLock()
		self.subscriptions: Dict[str, Set[str]] = {}
		self.client_callbacks: Dict[str, Callable[[str, Any, int, bool], None]] = {}
		self.retained_messages: Dict[str, Dict[str, Any]] = {}
		self.lwt_configs: Dict[str, Dict[str, Any]] = {}
		self.connected_clients: Set[str] = set()
		self.published_history: List[Dict[str, Any]] = []
		self._server_socket: Optional[socket.socket] = None
		self._server_thread: Optional[threading.Thread] = None
		self._client_sockets: Dict[str, socket.socket] = {}

	def start(self):
		with self.lock:
			if self.running:
				return
			self.running = True
			self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			self._server_socket.bind((self.host, self.port))
			self._server_socket.listen(20)
			self.port = self._server_socket.getsockname()[1]
			self._server_thread = threading.Thread(target=self._accept_loop, daemon=True)
			self._server_thread.start()

	def stop(self):
		with self.lock:
			self.running = False
			if self._server_socket:
				try:
					self._server_socket.close()
				except Exception:
					pass
				self._server_socket = None
			for cid, sock in list(self._client_sockets.items()):
				try:
					sock.close()
				except Exception:
					pass
			self._client_sockets.clear()

	def reset(self):
		with self.lock:
			self.subscriptions.clear()
			self.client_callbacks.clear()
			self.retained_messages.clear()
			self.lwt_configs.clear()
			self.connected_clients.clear()
			self.published_history.clear()

	def register_client(self, client_id: str, callback: Optional[Callable] = None, lwt: Optional[Dict[str, Any]] = None):
		with self.lock:
			self.connected_clients.add(client_id)
			if callback:
				self.client_callbacks[client_id] = callback
			if lwt:
				self.lwt_configs[client_id] = lwt

	def unregister_client(self, client_id: str, ungraceful: bool = False):
		with self.lock:
			if ungraceful and client_id in self.lwt_configs:
				lwt = self.lwt_configs[client_id]
				self.publish(
					topic=lwt.get("topic", f"pbl6/{client_id}/status"),
					payload=lwt.get("payload", {"status": "offline", "timestamp": int(time.time())}),
					qos=lwt.get("qos", 1),
					retain=lwt.get("retain", True),
					sender_id="broker_lwt"
				)
			self.connected_clients.discard(client_id)
			self.client_callbacks.pop(client_id, None)
			self.lwt_configs.pop(client_id, None)
			for pattern, clients in list(self.subscriptions.items()):
				clients.discard(client_id)

	def subscribe(self, client_id: str, pattern: str, callback: Optional[Callable] = None):
		with self.lock:
			if pattern not in self.subscriptions:
				self.subscriptions[pattern] = set()
			self.subscriptions[pattern].add(client_id)
			if callback:
				self.client_callbacks[client_id] = callback
			for r_topic, r_msg in self.retained_messages.items():
				if topic_matches(pattern, r_topic):
					cb = self.client_callbacks.get(client_id)
					if cb:
						try:
							cb(r_topic, r_msg["payload"], r_msg["qos"], True)
						except Exception:
							pass

	def unsubscribe(self, client_id: str, pattern: str):
		with self.lock:
			if pattern in self.subscriptions and client_id in self.subscriptions[pattern]:
				self.subscriptions[pattern].remove(client_id)

	def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False, sender_id: Optional[str] = None) -> int:
		with self.lock:
			record = {
				"topic": topic,
				"payload": payload,
				"qos": qos,
				"retain": retain,
				"sender_id": sender_id,
				"timestamp": time.time()
			}
			self.published_history.append(record)
			if retain:
				if payload is None or payload == "" or payload == {}:
					self.retained_messages.pop(topic, None)
				else:
					self.retained_messages[topic] = record

			delivered_count = 0
			notified_clients = set()
			for pattern, clients in list(self.subscriptions.items()):
				if topic_matches(pattern, topic):
					for cid in list(clients):
						if cid not in notified_clients:
							notified_clients.add(cid)
							cb = self.client_callbacks.get(cid)
							if cb:
								try:
									cb(topic, payload, qos, retain)
									delivered_count += 1
								except Exception:
									pass
			return delivered_count

	def _accept_loop(self):
		while self.running and self._server_socket:
			try:
				sock, addr = self._server_socket.accept()
				threading.Thread(target=self._handle_tcp_client, args=(sock,), daemon=True).start()
			except Exception:
				break

	def _handle_tcp_client(self, sock: socket.socket):
		client_id = f"tcp_{uuid.uuid4().hex[:8]}"
		is_graceful = False
		try:
			while self.running:
				header = sock.recv(1)
				if not header:
					break
				pkt_type = (header[0] >> 4) & 0x0F
				rem_len = self._read_rem_len(sock)
				data = self._read_exact(sock, rem_len) if rem_len > 0 else b""
				if pkt_type == 1:
					proto_len = struct.unpack("!H", data[0:2])[0]
					idx = 2 + proto_len + 1
					flags = data[idx]
					has_will = bool(flags & 0x04)
					will_qos = (flags >> 3) & 0x03
					will_retain = bool(flags & 0x20)
					idx += 3
					cid_len = struct.unpack("!H", data[idx:idx+2])[0]
					idx += 2
					parsed_cid = data[idx:idx+cid_len].decode("utf-8", errors="ignore")
					if parsed_cid:
						client_id = parsed_cid
					idx += cid_len
					lwt = None
					if has_will and idx + 2 <= len(data):
						wtopic_len = struct.unpack("!H", data[idx:idx+2])[0]
						idx += 2
						wtopic = data[idx:idx+wtopic_len].decode("utf-8", errors="ignore")
						idx += wtopic_len
						wmsg_len = struct.unpack("!H", data[idx:idx+2])[0]
						idx += 2
						wmsg_bytes = data[idx:idx+wmsg_len]
						try:
							wpayload = json.loads(wmsg_bytes.decode("utf-8"))
						except Exception:
							wpayload = wmsg_bytes.decode("utf-8", errors="ignore")
						lwt = {"topic": wtopic, "payload": wpayload, "qos": will_qos, "retain": will_retain}
					with self.lock:
						self._client_sockets[client_id] = sock
						self.register_client(client_id, None, lwt)
					sock.sendall(b"\x20\x02\x00\x00")
				elif pkt_type == 3:
					qos = (header[0] >> 1) & 0x03
					retain = bool(header[0] & 0x01)
					idx = 0
					t_len = struct.unpack("!H", data[idx:idx+2])[0]
					idx += 2
					topic = data[idx:idx+t_len].decode("utf-8", errors="ignore")
					idx += t_len
					packet_id = 0
					if qos > 0:
						packet_id = struct.unpack("!H", data[idx:idx+2])[0]
						idx += 2
					payload_bytes = data[idx:]
					try:
						payload_obj = json.loads(payload_bytes.decode("utf-8"))
					except Exception:
						payload_obj = payload_bytes.decode("utf-8", errors="ignore")
					self.publish(topic, payload_obj, qos, retain, sender_id=client_id)
					if qos == 1:
						sock.sendall(b"\x40\x02" + struct.pack("!H", packet_id))
				elif pkt_type == 8:
					packet_id = struct.unpack("!H", data[0:2])[0]
					idx = 2
					granted_qos = []
					while idx < len(data):
						t_len = struct.unpack("!H", data[idx:idx+2])[0]
						idx += 2
						sub_pattern = data[idx:idx+t_len].decode("utf-8", errors="ignore")
						idx += t_len
						req_qos = data[idx]
						idx += 1
						granted_qos.append(req_qos)
						self.subscribe(client_id, sub_pattern, self._make_tcp_sender(client_id, sock))
					sock.sendall(b"\x90" + bytes([2 + len(granted_qos)]) + struct.pack("!H", packet_id) + bytes(granted_qos))
				elif pkt_type == 12:
					sock.sendall(b"\xd0\x00")
				elif pkt_type == 14:
					is_graceful = True
					break
		except Exception:
			pass
		finally:
			with self.lock:
				self._client_sockets.pop(client_id, None)
				self.unregister_client(client_id, ungraceful=not is_graceful)
			try:
				sock.close()
			except Exception:
				pass

	def _make_tcp_sender(self, client_id: str, sock: socket.socket):
		def _sender(topic: str, payload: Any, qos: int, retain: bool):
			try:
				body = json.dumps(payload).encode("utf-8") if not isinstance(payload, bytes) else payload
				if isinstance(payload, str):
					body = payload.encode("utf-8")
				t_bytes = topic.encode("utf-8")
				var_hdr = struct.pack("!H", len(t_bytes)) + t_bytes
				pkt = var_hdr + body
				first_byte = 0x30 | (0x01 if retain else 0x00)
				sock.sendall(bytes([first_byte]) + self._encode_rem_len(len(pkt)) + pkt)
			except Exception:
				pass
		return _sender

	def _read_rem_len(self, sock: socket.socket) -> int:
		multiplier = 1
		value = 0
		while True:
			b = sock.recv(1)
			if not b:
				return 0
			digit = b[0]
			value += (digit & 0x7F) * multiplier
			multiplier *= 128
			if (digit & 0x80) == 0:
				break
		return value

	def _encode_rem_len(self, length: int) -> bytes:
		encoded = bytearray()
		while True:
			digit = length % 128
			length //= 128
			if length > 0:
				digit |= 0x80
			encoded.append(digit)
			if length <= 0:
				break
		return bytes(encoded)

	def _read_exact(self, sock: socket.socket, length: int) -> bytes:
		buf = bytearray()
		while len(buf) < length:
			chunk = sock.recv(length - len(buf))
			if not chunk:
				break
			buf.extend(chunk)
		return bytes(buf)

class TestMqttClient:
	__test__ = False
	def __init__(self, client_id: str = "test_client"):
		self.client_id = client_id
		self.broker: Optional[EmbeddedMqttBroker] = None
		self.connected = False
		self.received_messages: List[Dict[str, Any]] = []
		self.subscriptions: Set[str] = set()
		self._cv = threading.Condition()
		self.lwt_topic: Optional[str] = None
		self.lwt_payload: Optional[Any] = None

	def connect(
		self,
		broker: Optional[EmbeddedMqttBroker] = None,
		client_id: Optional[str] = None,
		lwt_topic: Optional[str] = None,
		lwt_payload: Optional[Any] = None,
		lwt_qos: int = 1,
		lwt_retain: bool = True
	) -> bool:
		if client_id:
			self.client_id = client_id
		if broker:
			self.broker = broker
		if not self.broker:
			raise ValueError("No EmbeddedMqttBroker provided to connect.")
		self.lwt_topic = lwt_topic
		self.lwt_payload = lwt_payload
		lwt = None
		if lwt_topic:
			lwt = {"topic": lwt_topic, "payload": lwt_payload, "qos": lwt_qos, "retain": lwt_retain}
		self.broker.register_client(self.client_id, self._on_broker_message, lwt)
		self.connected = True
		return True

	def disconnect(self, ungraceful: bool = False):
		if not self.connected or not self.broker:
			return
		self.connected = False
		self.broker.unregister_client(self.client_id, ungraceful=ungraceful)

	def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> bool:
		if not self.connected or not self.broker:
			return False
		self.broker.publish(topic, payload, qos=qos, retain=retain, sender_id=self.client_id)
		return True

	def subscribe(self, pattern: str, callback: Optional[Callable] = None):
		if not self.connected or not self.broker:
			return
		self.subscriptions.add(pattern)
		self.broker.subscribe(self.client_id, pattern, callback or self._on_broker_message)

	def unsubscribe(self, pattern: str):
		if not self.connected or not self.broker:
			return
		if pattern in self.subscriptions:
			self.subscriptions.remove(pattern)
		self.broker.unsubscribe(self.client_id, pattern)

	def _on_broker_message(self, topic: str, payload: Any, qos: int, retain: bool):
		with self._cv:
			self.received_messages.append({
				"topic": topic,
				"payload": payload,
				"qos": qos,
				"retain": retain,
				"timestamp": time.time()
			})
			self._cv.notify_all()

	def wait_for_message(
		self,
		topic: Optional[str] = None,
		timeout: float = 2.0,
		predicate: Optional[Callable[[Dict[str, Any]], bool]] = None
	) -> Optional[Dict[str, Any]]:
		end_time = time.time() + timeout
		with self._cv:
			while True:
				for msg in reversed(self.received_messages):
					if topic is None or topic_matches(topic, msg["topic"]):
						if predicate is None or predicate(msg):
							return msg
				remaining = end_time - time.time()
				if remaining <= 0:
					return None
				self._cv.wait(timeout=remaining)

	def collect_messages(
		self,
		topic: Optional[str] = None,
		count: int = 1,
		timeout: float = 2.0,
		predicate: Optional[Callable[[Dict[str, Any]], bool]] = None
	) -> List[Dict[str, Any]]:
		end_time = time.time() + timeout
		with self._cv:
			while True:
				matches = []
				for msg in self.received_messages:
					if topic is None or topic_matches(topic, msg["topic"]):
						if predicate is None or predicate(msg):
							matches.append(msg)
				if len(matches) >= count:
					return matches[:count]
				remaining = end_time - time.time()
				if remaining <= 0:
					return matches
				self._cv.wait(timeout=remaining)

	def clear_messages(self):
		with self._cv:
			self.received_messages.clear()

class MockPiSimulator:
	def __init__(self, device_id: str = "pi4_01"):
		self.device_id = device_id
		self.distance_threshold_cm = 80.0
		self.speaker_volume = 80
		self.alert_frequency_ms = 500
		self.detection_fps = 15
		self.battery_percentage = 85
		self.temperature_celsius = 48.5
		self.cpu_usage = 32.0
		self.ultrasonic_distance_cm = 145.2
		self.camera_active = True
		self.muted = False
		self.buzzer_active = False
		self.reboot_count = 0
		self.audio_chunks_received = 0
		self.total_audio_bytes = 0
		self.running = True
		self.event_counter = 9980

	def step_telemetry(self, distance_delta: float = 0.0, drain_battery: int = 0, cpu_usage: Optional[float] = None) -> Dict[str, Any]:
		if cpu_usage is not None:
			self.cpu_usage = float(cpu_usage)
		self.ultrasonic_distance_cm = max(5.0, min(400.0, self.ultrasonic_distance_cm + distance_delta))
		self.battery_percentage = max(0, min(100, self.battery_percentage - drain_battery))
		self.temperature_celsius = round(45.0 + (self.cpu_usage / 10.0), 1)
		return {
			"device_id": self.device_id,
			"timestamp": int(time.time()),
			"battery_percentage": int(self.battery_percentage),
			"temperature_celsius": float(self.temperature_celsius),
			"cpu_usage": float(self.cpu_usage),
			"ultrasonic_distance_cm": round(float(self.ultrasonic_distance_cm), 1),
			"camera_active": bool(self.camera_active),
			"speaker_volume": int(self.speaker_volume)
		}

	def inject_hazard(
		self,
		alert_type: str = "OBSTACLE_DANGER",
		distance_cm: float = 25.0,
		detected_objects: Optional[List[str]] = None,
		message: Optional[str] = None
	) -> Dict[str, Any]:
		self.event_counter += 1
		self.ultrasonic_distance_cm = distance_cm
		level = "CRITICAL" if distance_cm < self.distance_threshold_cm else "WARNING"
		return {
			"event_id": f"evt_{self.event_counter}",
			"timestamp": int(time.time()),
			"alert_type": alert_type,
			"level": level,
			"distance_cm": float(distance_cm),
			"detected_objects": detected_objects if detected_objects is not None else ["stairs_down", "puddle"],
			"message": message or "Phát hiện chướng ngại vật nguy hiểm ở cự ly gần!"
		}

	def apply_config(self, config: Dict[str, Any]):
		if "distance_threshold_cm" in config:
			try:
				self.distance_threshold_cm = float(config["distance_threshold_cm"])
			except (ValueError, TypeError):
				pass
		if "speaker_volume" in config:
			try:
				self.speaker_volume = int(config["speaker_volume"])
			except (ValueError, TypeError):
				pass
		if "alert_frequency_ms" in config:
			try:
				self.alert_frequency_ms = int(config["alert_frequency_ms"])
			except (ValueError, TypeError):
				pass
		if "detection_fps" in config:
			try:
				self.detection_fps = int(config["detection_fps"])
			except (ValueError, TypeError):
				pass

	def handle_command(self, cmd: Any) -> str:
		if isinstance(cmd, dict):
			cmd = cmd.get("command", "")
		cmd = str(cmd).strip().upper()
		if cmd == "REBOOT":
			self.reboot_count += 1
			self.ultrasonic_distance_cm = 145.2
			self.battery_percentage = 85
			return "REBOOT_ACK"
		elif cmd == "RESTART_SERVICE":
			self.event_counter = 9980
			return "RESTART_ACK"
		elif cmd == "MUTE":
			self.muted = True
			return "MUTED"
		elif cmd == "UNMUTE":
			self.muted = False
			return "UNMUTED"
		elif cmd == "TRIGGER_BUZZER":
			self.buzzer_active = True
			return "BUZZER_TRIGGERED"
		return "UNKNOWN_COMMAND"

	def generate_synthetic_radar_frame(self, width: int = 640, height: int = 480) -> bytes:
		try:
			import numpy as np
			frame = np.zeros((height, width, 3), dtype=np.uint8)
			return frame.tobytes()
		except Exception:
			return b"\x00" * (width * height * 3)

	def receive_audio_chunk(self, chunk: bytes) -> int:
		if self.muted:
			return 0
		self.audio_chunks_received += 1
		self.total_audio_bytes += len(chunk)
		return len(chunk)

class MockPiRunner:
	def __init__(self, script_path: str = "tools/mock_pi/mock_pi_server.py"):
		self.script_path = script_path
		self.simulator = MockPiSimulator()
		self.process = None

	def is_script_available(self) -> bool:
		return os.path.exists(self.script_path)

	def get_simulator(self) -> MockPiSimulator:
		return self.simulator

class WebRtcPeerSim:
	def __init__(self, client_id: str = "app_client"):
		self.client_id = client_id
	@staticmethod
	def create_offer(caller: str = "app_client", has_video: bool = True, has_audio: bool = True) -> Dict[str, Any]:
		sdp_lines = [
			"v=0",
			"o=- 4611731400 2 IN IP4 127.0.0.1",
			"s=-",
			"t=0 0",
			"a=group:BUNDLE 0 1" if (has_video and has_audio) else "a=group:BUNDLE 0"
		]
		if has_video:
			sdp_lines.extend([
				"m=video 9 UDP/TLS/RTP/SAVPF 96",
				"c=IN IP4 0.0.0.0",
				"a=rtpmap:96 VP8/90000",
				"a=sendrecv"
			])
		if has_audio:
			sdp_lines.extend([
				"m=audio 9 UDP/TLS/RTP/SAVPF 97",
				"c=IN IP4 0.0.0.0",
				"a=rtpmap:97 opus/48000/2",
				"a=sendrecv"
			])
		return {
			"sdp": "\r\n".join(sdp_lines) + "\r\n",
			"type": "offer",
			"caller": caller
		}

	@staticmethod
	def create_answer(offer: Dict[str, Any], callee: str = "pi4_01") -> Dict[str, Any]:
		offer_sdp = offer.get("sdp", "")
		has_video = "m=video" in offer_sdp
		has_audio = "m=audio" in offer_sdp
		sdp_lines = [
			"v=0",
			"o=- 4611731401 2 IN IP4 127.0.0.1",
			"s=-",
			"t=0 0"
		]
		if has_video:
			sdp_lines.extend([
				"m=video 9 UDP/TLS/RTP/SAVPF 96",
				"c=IN IP4 0.0.0.0",
				"a=rtpmap:96 VP8/90000",
				"a=sendonly"
			])
		if has_audio:
			sdp_lines.extend([
				"m=audio 9 UDP/TLS/RTP/SAVPF 97",
				"c=IN IP4 0.0.0.0",
				"a=rtpmap:97 opus/48000/2",
				"a=recvonly"
			])
		return {
			"sdp": "\r\n".join(sdp_lines) + "\r\n",
			"type": "answer",
			"callee": callee
		}

	@staticmethod
	def create_ice_candidate(sender: str = "app", sdp_mid: str = "0", sdp_mline_index: int = 0) -> Dict[str, Any]:
		return {
			"candidate": "candidate:842163049 1 udp 1677729535 192.168.1.100 56788 typ srflx raddr 192.168.1.100 rport 56788",
			"sdpMid": str(sdp_mid),
			"sdpMLineIndex": int(sdp_mline_index),
			"sender": sender
		}

	@staticmethod
	def validate_offer(offer: Any) -> Tuple[bool, str]:
		if not isinstance(offer, dict):
			return False, "Offer must be a JSON object"
		if offer.get("type") != "offer":
			return False, f"Expected type 'offer', got {offer.get('type')}"
		if not offer.get("sdp") or not isinstance(offer.get("sdp"), str):
			return False, "Offer must contain a non-empty 'sdp' string"
		if not offer.get("caller"):
			return False, "Offer must specify a 'caller'"
		sdp = offer["sdp"]
		if "v=0" not in sdp:
			return False, "SDP missing version specification (v=0)"
		return True, "Valid offer"

	@staticmethod
	def validate_answer(answer: Any) -> Tuple[bool, str]:
		if not isinstance(answer, dict):
			return False, "Answer must be a JSON object"
		if answer.get("type") != "answer":
			return False, f"Expected type 'answer', got {answer.get('type')}"
		if not answer.get("sdp") or not isinstance(answer.get("sdp"), str):
			return False, "Answer must contain a non-empty 'sdp' string"
		if not answer.get("callee"):
			return False, "Answer must specify a 'callee'"
		sdp = answer["sdp"]
		if "v=0" not in sdp:
			return False, "SDP missing version specification (v=0)"
		return True, "Valid answer"

	@staticmethod
	def validate_ice_candidate(cand: Any) -> Tuple[bool, str]:
		if not isinstance(cand, dict):
			return False, "Candidate must be a JSON object"
		if "candidate" not in cand:
			return False, "Missing 'candidate' field"
		if "sdpMid" not in cand and "sdpMLineIndex" not in cand:
			return False, "Must contain sdpMid or sdpMLineIndex"
		if "sender" not in cand:
			return False, "Missing 'sender' field"
		return True, "Valid candidate"

class CodebaseContractValidator:
	REQUIRED_PERMISSIONS = {
		"android.permission.INTERNET",
		"android.permission.RECORD_AUDIO",
		"android.permission.FOREGROUND_SERVICE",
		"android.permission.POST_NOTIFICATIONS",
		"android.permission.CAMERA",
		"android.permission.VIBRATE"
	}

	REQUIRED_ARCH_TOPICS = [
		"pbl6/{device_id}/telemetry",
		"pbl6/{device_id}/alert",
		"pbl6/{device_id}/config",
		"pbl6/{device_id}/command",
		"pbl6/{device_id}/status",
		"pbl6/{device_id}/webrtc/offer",
		"pbl6/{device_id}/webrtc/answer",
		"pbl6/{device_id}/webrtc/ice_candidate"
	]

	@staticmethod
	def validate_clean_architecture_structure(root_dir: str = ".") -> Dict[str, Any]:
		lib_dir = os.path.join(root_dir, "lib")
		layers = ["core", "data", "domain", "presentation"]
		present = {}
		for layer in layers:
			p = os.path.join(lib_dir, layer)
			present[layer] = os.path.isdir(p)

		forbidden_imports = []
		domain_dir = os.path.join(lib_dir, "domain")
		if os.path.isdir(domain_dir):
			for root, _, files in os.walk(domain_dir):
				for f in files:
					if f.endswith(".dart"):
						fpath = os.path.join(root, f)
						with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
							for line_num, line in enumerate(fp, 1):
								if re.search(r"import\s+['\"][^'\"]*(/data/|/presentation/)[^'\"]*['\"]", line):
									forbidden_imports.append((fpath, line_num, line.strip()))

		return {
			"layers_present": present,
			"clean_structure_valid": all(present.values()),
			"forbidden_imports": forbidden_imports,
			"domain_isolated": len(forbidden_imports) == 0
		}

	@staticmethod
	def validate_android_permissions(manifest_path: str = "android/app/src/main/AndroidManifest.xml") -> Dict[str, Any]:
		if not os.path.exists(manifest_path):
			return {"exists": False, "missing_permissions": list(CodebaseContractValidator.REQUIRED_PERMISSIONS)}
		with open(manifest_path, "r", encoding="utf-8") as f:
			content = f.read()
		declared = set()
		for match in re.finditer(r'<uses-permission\s+android:name="([^"]+)"', content):
			declared.add(match.group(1))
		missing = CodebaseContractValidator.REQUIRED_PERMISSIONS - declared
		return {
			"exists": True,
			"declared": list(declared),
			"missing_permissions": list(missing),
			"is_valid": len(missing) == 0
		}

	@staticmethod
	def validate_architecture_documentation(doc_path: str = "docs/ARCHITECTURE.md") -> Dict[str, Any]:
		if not os.path.exists(doc_path):
			return {"exists": False, "topics_covered": [], "missing_topics": CodebaseContractValidator.REQUIRED_ARCH_TOPICS}
		with open(doc_path, "r", encoding="utf-8") as f:
			content = f.read()
		missing = []
		for topic in CodebaseContractValidator.REQUIRED_ARCH_TOPICS:
			token = topic.replace("{device_id}", "")
			if token not in content:
				missing.append(topic)
		return {
			"exists": True,
			"missing_topics": missing,
			"is_valid": len(missing) == 0
		}

class ConnectionBlocSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.state = "Disconnected"
		self.status_banner = "Disconnected"
		self.state_history = []
		self._record_state("Disconnected")

	def _record_state(self, state: str):
		self.state = state
		self.state_history.append({"state": state, "timestamp": time.time()})

	def simulate_connecting(self):
		self._record_state("Connecting")

	def simulate_connected(self):
		self._record_state("Connected")
		self.status_banner = "Connected"

	def simulate_disconnect(self):
		self._record_state("Disconnected")
		self.status_banner = "Disconnected"

	def handle_status(self, payload: Any):
		status = ""
		if isinstance(payload, dict):
			status = str(payload.get("status", "")).lower()
		elif isinstance(payload, str):
			status = payload.strip().lower()
		if status == "online":
			self.simulate_connected()
		else:
			self.simulate_disconnect()

	def dispose(self):
		self.state_history.clear()

class DashboardBlocSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.is_loaded = False
		self.device_id = app.device_id
		self.battery = 85
		self.temperature = 48.5
		self.cpu = 32.0
		self.distance = 145.2
		self.camera_active = True
		self.speaker_volume = 80
		self.last_telemetry = None
		self.is_stale = False

	@property
	def last_distance(self) -> float:
		return self.distance

	@property
	def last_battery(self) -> int:
		return self.battery

	def handle_telemetry(self, payload: Any):
		if isinstance(payload, str):
			try:
				payload = json.loads(payload)
			except Exception:
				return
		if not isinstance(payload, dict):
			return
		self.last_telemetry = payload
		self.is_loaded = True
		if "device_id" in payload:
			self.device_id = str(payload["device_id"])
		if "battery_percentage" in payload or "battery" in payload:
			try:
				raw_b = payload.get("battery_percentage", payload.get("battery"))
				self.battery = int(float(raw_b))
			except Exception:
				pass
		if "temperature_celsius" in payload or "temperature" in payload:
			try:
				raw_t = payload.get("temperature_celsius", payload.get("temperature"))
				self.temperature = float(raw_t)
			except Exception:
				pass
		if "cpu_usage" in payload or "cpu" in payload:
			try:
				raw_c = payload.get("cpu_usage", payload.get("cpu"))
				self.cpu = float(raw_c)
			except Exception:
				pass
		if "ultrasonic_distance_cm" in payload or "distance" in payload:
			try:
				raw_d = payload.get("ultrasonic_distance_cm", payload.get("distance"))
				dist = float(raw_d)
				if math.isnan(dist) or math.isinf(dist):
					self.distance = 0.0
				else:
					self.distance = dist
			except Exception:
				pass
		if "camera_active" in payload:
			self.camera_active = bool(payload["camera_active"])
		if "speaker_volume" in payload:
			try:
				self.speaker_volume = int(payload["speaker_volume"])
			except Exception:
				pass
		if "timestamp" in payload:
			try:
				ts = float(payload["timestamp"])
				if abs(time.time() - ts) > 1800:
					self.is_stale = True
				else:
					self.is_stale = False
			except Exception:
				pass

	def dispose(self):
		self.last_telemetry = None

class DashboardViewSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.orientation = "portrait"
		self.font_scale = 1.0
		self.theme = "LIGHT"
		self.routes = ["/live_monitor", "/settings", "/alert_history"]

	def get_connection_badge(self) -> Dict[str, Any]:
		is_online = self.app.connection_bloc.state == "Connected"
		return {
			"online": is_online,
			"label": "Online" if is_online else "Offline",
			"color": "GREEN" if is_online else "RED"
		}

	@property
	def formatted_distance(self) -> str:
		return f"{self.app.dashboard_bloc.distance:.1f} cm"

	@property
	def formatted_battery(self) -> str:
		return f"{self.app.dashboard_bloc.battery}%"

	@property
	def formatted_temp(self) -> str:
		return f"{self.app.dashboard_bloc.temperature:.1f}\u00b0C"

	@property
	def formatted_cpu(self) -> str:
		return f"{self.app.dashboard_bloc.cpu:.1f}%"

	@property
	def battery_badge_color(self) -> str:
		return "GREEN" if self.app.dashboard_bloc.battery > 20 else "RED"

	def navigate(self, route: str):
		self.app.current_route = route

	def set_orientation(self, orientation: str):
		self.orientation = orientation

	def rotate_screen(self, orientation: str):
		self.orientation = orientation

	def toggle_theme(self):
		self.theme = "DARK" if self.theme == "LIGHT" else "LIGHT"

	@property
	def can_scale_320px(self) -> bool:
		return True

class AlertBlocSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.has_critical_alert = False
		self.active_critical_alert = None
		self.history = []
		self._processed_ids = set()

	def handle_alert(self, payload: Any):
		if isinstance(payload, str):
			try:
				payload = json.loads(payload)
			except Exception:
				return
		if not isinstance(payload, dict):
			return
		eid = payload.get("event_id")
		if eid and eid in self._processed_ids:
			return
		if eid:
			self._processed_ids.add(eid)
		self.history.insert(0, payload)
		lvl = payload.get("level", "")
		if lvl == "CRITICAL":
			self.has_critical_alert = True
			self.active_critical_alert = payload

	def clear_history(self):
		self.history.clear()
		self.has_critical_alert = False
		self.active_critical_alert = None
		self._processed_ids.clear()

	def dispose(self):
		self.clear_history()

class AlertHistoryViewSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.is_refreshing = False
		self.selected_event_id = None

	@property
	def alerts(self) -> list:
		return self.app.alert_bloc.history

	@property
	def item_count(self) -> int:
		return len(self.app.alert_bloc.history)

	@property
	def is_empty(self) -> bool:
		return len(self.app.alert_bloc.history) == 0

	def add_alert(self, alert: Dict[str, Any]):
		self.app.alert_bloc.handle_alert(alert)

	def pull_to_refresh(self):
		self.is_refreshing = False

	def clear_history(self):
		self.app.alert_bloc.clear_history()
		self.selected_event_id = None

	def open_detail_modal(self, event_id: str) -> Optional[Dict[str, Any]]:
		self.selected_event_id = event_id
		for a in self.app.alert_bloc.history:
			if a.get("event_id") == event_id:
				res = dict(a)
				res["opened"] = True
				return res
		return None

	def get_badge_color(self, level: str) -> str:
		if level == "CRITICAL":
			return "RED"
		if level == "WARNING":
			return "ORANGE"
		return "BLUE"

	def get_formatted_timestamp(self, alert: Dict[str, Any]) -> str:
		ts = alert.get("timestamp", time.time())
		return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))

	def get_chips(self, alert: Dict[str, Any]) -> list:
		return list(alert.get("detected_objects", []))

	def render_window(self, offset: int = 0, limit: int = 20) -> list:
		return self.app.alert_bloc.history[offset:offset + limit]

class NotificationServiceSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.channel_id = "pbl6_critical_alerts"
		self.channel_name = "PBL6 Critical Alerts"
		self.channel_importance = "max"
		self.channel_priority = "high"
		self.fullScreenIntent = True
		self.app_state = "FOREGROUND"
		self.has_permission = True
		self.heads_up_triggered = False
		self.in_app_banner_shown = False
		self.queued_system_tray = []
		self.recent_alerts = []
		self.collapsed_summary = None
		self.dnd_mode = False

	def handle_alert(self, payload: Any):
		if isinstance(payload, str):
			try:
				payload = json.loads(payload)
			except Exception:
				return
		if not isinstance(payload, dict):
			return
		if payload.get("level") == "CRITICAL":
			if self.has_permission:
				self.heads_up_triggered = True
				if self.app_state == "TERMINATED":
					self.queued_system_tray.append(payload)
			else:
				self.in_app_banner_shown = True
			self.recent_alerts.append(payload)
			if len(self.recent_alerts) >= 2:
				self.collapsed_summary = f"Ph\u00e1t hi\u1ec7n {len(self.recent_alerts)} s\u1ef1 c\u1ed1 nguy hi\u1ec3m"

	def handle_notification_tap(self, event_id: str) -> Dict[str, Any]:
		self.app.current_route = "/alert_history"
		self.app.alert_history_view.selected_event_id = event_id
		return {
			"action": "NAVIGATE",
			"target": "AlertHistoryScreen",
			"event_id": event_id
		}

class ConfigBlocSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.distance_threshold = 80.0
		self.speaker_volume = 80
		self.alert_frequency_ms = 500
		self.detection_fps = 15
		self.state = "ConfigLoaded"
		self.offline_buffer = []

	def handle_config(self, payload: Any):
		if isinstance(payload, str):
			try:
				payload = json.loads(payload)
			except Exception:
				return
		if not isinstance(payload, dict):
			return
		if "distance_threshold_cm" in payload:
			try:
				self.distance_threshold = float(payload["distance_threshold_cm"])
			except Exception:
				pass
		if "speaker_volume" in payload:
			try:
				self.speaker_volume = int(payload["speaker_volume"])
			except Exception:
				pass
		if "alert_frequency_ms" in payload:
			try:
				self.alert_frequency_ms = int(payload["alert_frequency_ms"])
			except Exception:
				pass
		if "detection_fps" in payload:
			try:
				self.detection_fps = int(payload["detection_fps"])
			except Exception:
				pass
		self.state = "ConfigUpdated"

	def apply_local_config(self, key: str, value: Any):
		if self.app.connection_bloc.state != "Connected":
			self.offline_buffer.append({key: value})
			return
		if key == "distance_threshold_cm":
			self.distance_threshold = float(value)
		elif key == "speaker_volume":
			self.speaker_volume = int(value)
		elif key == "alert_frequency_ms":
			self.alert_frequency_ms = int(value)
		elif key == "detection_fps":
			self.detection_fps = int(value)
		if self.app.broker:
			self.app.broker.publish(f"pbl6/{self.app.device_id}/config", {key: value})

	def reconnect_and_flush(self):
		if self.app.broker and self.offline_buffer:
			merged = {}
			for item in self.offline_buffer:
				merged.update(item)
			self.app.broker.publish(f"pbl6/{self.app.device_id}/config", merged)
			self.offline_buffer.clear()

class SettingsViewSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.distance_min = 20.0
		self.distance_max = 200.0
		self.volume_min = 0
		self.volume_max = 100
		self.broker_host = "127.0.0.1"
		self.device_id = app.device_id
		self.staged_changes = {}

	@property
	def distance_threshold(self) -> float:
		return self.app.config_bloc.distance_threshold

	@property
	def speaker_volume(self) -> int:
		return self.app.config_bloc.speaker_volume

	def set_distance_threshold(self, val: float):
		self.app.config_bloc.distance_threshold = float(val)
		self.app.config_bloc.apply_local_config("distance_threshold_cm", val)

	def set_speaker_volume(self, val: int):
		self.app.config_bloc.speaker_volume = int(val)
		self.app.config_bloc.apply_local_config("speaker_volume", val)

	def reset_to_defaults(self):
		self.reset_to_factory_defaults()

	def validate_broker_host(self, host: str) -> bool:
		return self.validate_broker_url(host)

	def adjust_slider_rapidly(self, param: str, value: Any):
		self.staged_changes[param] = value

	def flush_debounced_save(self):
		if self.staged_changes:
			for k, v in self.staged_changes.items():
				self.app.config_bloc.apply_local_config(k, v)
			self.staged_changes.clear()

	def save_settings_while_offline(self, key: str, value: Any):
		self.app.config_bloc.offline_buffer.append({key: value})

	def reset_to_factory_defaults(self):
		defaults = {
			"distance_threshold_cm": 80.0,
			"speaker_volume": 80,
			"alert_frequency_ms": 500,
			"detection_fps": 15
		}
		for k, v in defaults.items():
			self.app.config_bloc.apply_local_config(k, v)

	def validate_broker_url(self, url: str) -> bool:
		if not url or not isinstance(url, str):
			return False
		pattern = r"^(localhost|127\.0\.0\.1|(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)|(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})$"
		return bool(re.match(pattern, url.strip()))

	def confirm_reboot(self):
		if self.app.broker:
			self.app.broker.publish(f"pbl6/{self.app.device_id}/command", {"command": "REBOOT"})

	def cancel_reboot(self):
		pass

	def trigger_buzzer(self):
		if self.app.broker:
			self.app.broker.publish(f"pbl6/{self.app.device_id}/command", {"command": "TRIGGER_BUZZER"})

class WebRtcBlocSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.lifecycle_state = "IDLE"
		self.stun_server = "stun:stun.l.google.com:19302"
		self.ice_candidate_buffer = []
		self.peer_sim = WebRtcPeerSim(f"{app.device_id}_client")
		self.last_error = None
		self.is_incoming_audio_ducked = False
		self.ptt_active = False

	def start_call(self) -> Optional[Dict[str, Any]]:
		if self.app.connection_bloc.state != "Connected":
			self.lifecycle_state = "FAILED"
			self.last_error = "DEVICE_OFFLINE_TIMEOUT"
			return None
		self.lifecycle_state = "OFFERING"
		offer = self.peer_sim.create_offer(caller=self.app.client_id)
		if self.app.broker:
			self.app.broker.publish(f"pbl6/{self.app.device_id}/webrtc/offer", offer)
		return offer

	def handle_answer(self, payload: Any):
		if self.lifecycle_state != "OFFERING":
			return
		if isinstance(payload, str):
			try:
				payload = json.loads(payload)
			except Exception:
				return
		valid, reason = self.peer_sim.validate_answer(payload)
		if valid:
			self.lifecycle_state = "STREAMING"
			self.ice_candidate_buffer.clear()
		else:
			self.lifecycle_state = "FAILED"
			self.last_error = reason

	def handle_ice_candidate(self, payload: Any):
		if self.lifecycle_state in ("STREAMING", "CONNECTING"):
			return
		self.ice_candidate_buffer.append(payload)

	def cancel_call(self):
		self.lifecycle_state = "IDLE"

	def fail_call(self, reason: str = "FAILED"):
		self.lifecycle_state = "FAILED"
		self.last_error = reason

	def dispose(self):
		self.lifecycle_state = "IDLE"
		self.ice_candidate_buffer.clear()

class MonitorViewSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.aspect_ratio = 640.0 / 480.0
		self.is_fullscreen = False
		self.is_muted = False
		self.is_screen_locked = False
		self.is_streaming = False
		self.show_reconnect_overlay = False
		self.is_reconnect_overlay_visible = False
		self.hud_visible = True
		self.ptt_button_rect = {"x": 160, "y": 600, "w": 80, "h": 80}

	def pause_stream(self):
		self.is_streaming = False

	@property
	def hud_distance(self) -> float:
		return self.app.dashboard_bloc.distance

	def toggle_fullscreen(self):
		self.is_fullscreen = not self.is_fullscreen
		self.app.dashboard_view.orientation = "landscape" if self.is_fullscreen else "portrait"

	def toggle_mute(self):
		self.is_muted = not self.is_muted

	def lock_screen(self):
		self.is_screen_locked = True

	def unlock_screen(self):
		self.is_screen_locked = False

	def show_reconnect_overlay(self):
		self.is_reconnect_overlay_visible = True

	def hide_reconnect_overlay(self):
		self.is_reconnect_overlay_visible = False

class PttIntercomSim:
	def __init__(self, app: "ClientStateMachineSim"):
		self.app = app
		self.ptt_active = False
		self.button_color = "DEFAULT"
		self.mic_permission_granted = True
		self.touch_start_time = 0.0
		self.audio_chunks_sent = 0
		self.is_cancelled = False

	def press_ptt(self) -> bool:
		if not self.mic_permission_granted:
			return False
		self.ptt_active = True
		self.button_color = "RED_ACTIVE"
		self.touch_start_time = time.time()
		self.app.webrtc_bloc.is_incoming_audio_ducked = True
		self.app.webrtc_bloc.ptt_active = True
		return True

	def handle_touch_down(self):
		self.touch_start_time = time.time()
		self.press_ptt()

	def handle_touch_up(self, duration_ms: Optional[float] = None) -> Any:
		if duration_ms is None:
			duration_ms = (time.time() - self.touch_start_time) * 1000.0
		if duration_ms < 50.0:
			self.release_ptt()
			return False
		if duration_ms > 60000.0:
			self.release_ptt()
			return "CUTOFF_60S"
		self.release_ptt()
		return True

	def drag_off(self):
		self.is_cancelled = True
		self.release_ptt()

	def release_ptt(self):
		self.ptt_active = False
		self.button_color = "DEFAULT"
		self.app.webrtc_bloc.is_incoming_audio_ducked = False
		self.app.webrtc_bloc.ptt_active = False

	def send_audio_chunk(self, sim: Any, pcm_data: bytes) -> bool:
		if self.ptt_active and self.mic_permission_granted:
			sim.receive_audio_chunk(pcm_data)
			self.audio_chunks_sent += 1
			return True
		return False

class ClientStateMachineSim:
	def __init__(self, device_id: str = "pi4_01", broker: Optional[EmbeddedMqttBroker] = None, client_id: Optional[str] = None):
		self.device_id = device_id
		self.broker = broker
		self.client_id = client_id or f"pbl6_app_client_{uuid.uuid4().hex[:8]}"
		self.current_route = "/dashboard"

		self.connection_bloc = ConnectionBlocSim(self)
		self.dashboard_bloc = DashboardBlocSim(self)
		self.alert_bloc = AlertBlocSim(self)
		self.config_bloc = ConfigBlocSim(self)
		self.webrtc_bloc = WebRtcBlocSim(self)
		self.notification_service = NotificationServiceSim(self)
		self.ptt_intercom = PttIntercomSim(self)

		self.dashboard_view = DashboardViewSim(self)
		self.monitor_view = MonitorViewSim(self)
		self.settings_view = SettingsViewSim(self)
		self.alert_history_view = AlertHistoryViewSim(self)
		self.is_disposed = False

		if self.broker:
			self._register_subscriptions()

	def navigate(self, route: str):
		self.current_route = route

	def _register_subscriptions(self):
		self.broker.register_client(self.client_id, self._on_message)
		self.broker.subscribe(self.client_id, f"pbl6/{self.device_id}/telemetry")
		self.broker.subscribe(self.client_id, f"pbl6/{self.device_id}/alert")
		self.broker.subscribe(self.client_id, f"pbl6/{self.device_id}/status")
		self.broker.subscribe(self.client_id, f"pbl6/{self.device_id}/config")
		self.broker.subscribe(self.client_id, f"pbl6/{self.device_id}/command")
		self.broker.subscribe(self.client_id, f"pbl6/{self.device_id}/webrtc/answer")
		self.broker.subscribe(self.client_id, f"pbl6/{self.device_id}/webrtc/ice_candidate")

	def _on_message(self, topic: str, payload: Any, qos: int, retain: bool):
		if topic.endswith("/telemetry"):
			self.dashboard_bloc.handle_telemetry(payload)
		elif topic.endswith("/alert"):
			self.alert_bloc.handle_alert(payload)
			self.notification_service.handle_alert(payload)
		elif topic.endswith("/status"):
			self.connection_bloc.handle_status(payload)
		elif topic.endswith("/config"):
			self.config_bloc.handle_config(payload)
		elif topic.endswith("/webrtc/answer"):
			self.webrtc_bloc.handle_answer(payload)
		elif topic.endswith("/webrtc/ice_candidate"):
			self.webrtc_bloc.handle_ice_candidate(payload)

	def dispose(self):
		self.is_disposed = True
		if self.broker:
			self.broker.unregister_client(self.client_id)
		self.connection_bloc.dispose()
		self.dashboard_bloc.dispose()
		self.alert_bloc.dispose()
		self.webrtc_bloc.dispose()

@dataclass
class TestResultRecord:
	__test__ = False
	tier: int
	feature_id: str
	test_id: str
	name: str
	status: str
	duration_ms: float
	error_message: Optional[str] = None
	details: Dict[str, Any] = field(default_factory=dict)

class E2EResultCollector:
	_instance = None
	_lock = threading.Lock()

	def __new__(cls):
		with cls._lock:
			if cls._instance is None:
				cls._instance = super(E2EResultCollector, cls).__new__(cls)
				cls._instance.records = []
		return cls._instance

	def record(
		self,
		tier: int,
		feature_id: str,
		test_id: str,
		name: str,
		passed: bool,
		duration_ms: float,
		error: Optional[str] = None,
		details: Optional[Dict[str, Any]] = None
	):
		status = "PASSED" if passed else "FAILED"
		rec = TestResultRecord(
			tier=tier,
			feature_id=feature_id,
			test_id=test_id,
			name=name,
			status=status,
			duration_ms=round(duration_ms, 2),
			error_message=str(error) if error else None,
			details=details or {}
		)
		self.records.append(rec)

	def reset(self):
		self.records.clear()

	def get_summary(self) -> Dict[str, Any]:
		total = len(self.records)
		passed = sum(1 for r in self.records if r.status == "PASSED")
		failed = sum(1 for r in self.records if r.status == "FAILED")
		by_tier = {}
		for r in self.records:
			t = f"Tier_{r.tier}"
			if t not in by_tier:
				by_tier[t] = {"total": 0, "passed": 0, "failed": 0}
			by_tier[t]["total"] += 1
			if r.status == "PASSED":
				by_tier[t]["passed"] += 1
			else:
				by_tier[t]["failed"] += 1
		return {
			"total_tests": total,
			"passed": passed,
			"failed": failed,
			"pass_rate_pct": round((passed / total * 100.0) if total > 0 else 0.0, 2),
			"by_tier": by_tier
		}

	def export_json(self, path: str = "test/e2e/e2e_results.json"):
		summary = self.get_summary()
		output = {
			"summary": summary,
			"records": [asdict(r) for r in self.records]
		}
		os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
		with open(path, "w", encoding="utf-8") as f:
			json.dump(output, f, indent=2)

	def print_summary_table(self) -> str:
		sum_data = self.get_summary()
		lines = []
		lines.append("=" * 70)
		lines.append(f"{'PBL6 E2E TEST EXECUTION SUMMARY':^70}")
		lines.append("=" * 70)
		lines.append(f"{'Tier':<12} | {'Total':<10} | {'Passed':<10} | {'Failed':<10} | {'Pass Rate'}")
		lines.append("-" * 70)
		for t, counts in sorted(sum_data["by_tier"].items()):
			pct = (counts["passed"] / counts["total"] * 100.0) if counts["total"] > 0 else 0.0
			lines.append(f"{t:<12} | {counts['total']:<10} | {counts['passed']:<10} | {counts['failed']:<10} | {pct:.1f}%")
		lines.append("-" * 70)
		lines.append(f"{'GRAND TOTAL':<12} | {sum_data['total_tests']:<10} | {sum_data['passed']:<10} | {sum_data['failed']:<10} | {sum_data['pass_rate_pct']:.1f}%")
		lines.append("=" * 70)
		out_str = "\n".join(lines)
		print(out_str)
		return out_str
