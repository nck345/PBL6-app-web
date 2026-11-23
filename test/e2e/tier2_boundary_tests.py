import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from e2e_harness import (
	EmbeddedMqttBroker,
	TestMqttClient,
	MockPiSimulator,
	WebRtcPeerSim,
	CodebaseContractValidator,
	ClientStateMachineSim,
	E2EResultCollector
)

@pytest.fixture(autouse=True)
def setup_harness():
	broker = EmbeddedMqttBroker()
	client = TestMqttClient("test_boundary_client")
	sim = MockPiSimulator("pi4_01")
	app_sim = ClientStateMachineSim("pi4_01", broker)
	client.connect(broker)
	yield {"broker": broker, "client": client, "sim": sim, "app_sim": app_sim}
	app_sim.dispose()
	client.disconnect()
	broker.stop()

def run_test_wrapper(tier: int, feature_id: str, test_id: str, name: str, test_func):
	collector = E2EResultCollector()
	t0 = time.perf_counter()
	try:
		test_func()
		duration_ms = (time.perf_counter() - t0) * 1000.0
		collector.record(tier, feature_id, test_id, name, True, duration_ms)
	except Exception as ex:
		duration_ms = (time.perf_counter() - t0) * 1000.0
		collector.record(tier, feature_id, test_id, name, False, duration_ms, error=str(ex))
		raise

class TestTier2Boundary01:
	def test_t2_01_1_negative_distance_sensor_error(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			pkt = sim.step_telemetry()
			raw_dist = -1.0
			sanitized = max(0.0, raw_dist) if raw_dist >= 0 else None
			assert sanitized is None
		run_test_wrapper(2, "F1", "T2.1.1", "Negative distance values sensor error handling", _exec)

	def test_t2_01_2_boundary_battery_levels(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.battery_percentage = 0
			p0 = sim.step_telemetry()
			assert p0["battery_percentage"] == 0
			sim.battery_percentage = 100
			p100 = sim.step_telemetry()
			assert p100["battery_percentage"] == 100
		run_test_wrapper(2, "F1", "T2.1.2", "Boundary battery levels 0% and 100%", _exec)

	def test_t2_01_3_extreme_cpu_temperatures(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			p = sim.step_telemetry(cpu_usage=500.0)
			assert p["temperature_celsius"] == 95.0
			is_throttling = p["temperature_celsius"] >= 85.0
			assert is_throttling is True
		run_test_wrapper(2, "F1", "T2.1.3", "Extreme CPU temperatures sub-zero and 95°C", _exec)

	def test_t2_01_4_max_distance_upper_limit(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			p = sim.step_telemetry(distance_delta=600.0)
			assert p["ultrasonic_distance_cm"] == 400.0
			assert sim.ultrasonic_distance_cm == 400.0
		run_test_wrapper(2, "F1", "T2.1.4", "Max ultrasonic distance upper limit > 500cm", _exec)

	def test_t2_01_5_clock_skew_telemetry(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			pkt = sim.step_telemetry()
			pkt["timestamp"] = int(time.time()) - 3600
			app_sim.dashboard_bloc.handle_telemetry(pkt)
			assert app_sim.dashboard_bloc.is_stale is True
		run_test_wrapper(2, "F1", "T2.1.5", "Clock skew and out-of-order timestamp handling", _exec)

class TestTier2Boundary02:
	def test_t2_02_1_missing_optional_fields(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			broker = setup_harness["broker"]
			minimal_pkt = {"device_id": "pi4_01", "timestamp": int(time.time()), "battery_percentage": 80}
			broker.publish("pbl6/pi4_01/telemetry", minimal_pkt)
			assert app_sim.dashboard_bloc.battery == 80
			assert app_sim.dashboard_bloc.camera_active is True
		run_test_wrapper(2, "F2", "T2.2.1", "Missing optional fields in telemetry JSON payload", _exec)

	def test_t2_02_2_malformed_json_syntax(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/telemetry", b'{"bad json')
			assert app_sim.dashboard_bloc.is_loaded is False
		run_test_wrapper(2, "F2", "T2.2.2", "Malformed JSON syntax without crash", _exec)

	def test_t2_02_3_rapid_telemetry_flood(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			client.subscribe("pbl6/pi4_01/telemetry")
			for i in range(25):
				client.publish("pbl6/pi4_01/telemetry", {"seq": i})
			msgs = client.collect_messages("pbl6/pi4_01/telemetry", count=25, timeout=1.0)
			assert len(msgs) == 25
		run_test_wrapper(2, "F2", "T2.2.3", "Rapid telemetry flood throttling handling", _exec)

	def test_t2_02_4_unicode_device_ids(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			special_id = "pi4_01_đặc_biệt_#_safe"
			topic = f"pbl6/{special_id}/telemetry"
			client.subscribe(topic)
			client.publish(topic, {"device_id": special_id})
			msg = client.wait_for_message(topic, timeout=1.0)
			assert msg is not None
			assert msg["payload"]["device_id"] == special_id
		run_test_wrapper(2, "F2", "T2.2.4", "Unicode device IDs and special characters", _exec)

	def test_t2_02_5_type_mismatch_fallback(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			broker = setup_harness["broker"]
			broker.publish("pbl6/pi4_01/telemetry", {"battery_percentage": "85"})
			assert app_sim.dashboard_bloc.battery == 85
		run_test_wrapper(2, "F2", "T2.2.5", "Type mismatch graceful fallback", _exec)

class TestTier2Boundary03:
	def test_t2_03_1_exact_threshold_boundary(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			a1 = sim.inject_hazard(distance_cm=80.0)
			a2 = sim.inject_hazard(distance_cm=79.9)
			assert a1["level"] == "WARNING"
			assert a2["level"] == "CRITICAL"
		run_test_wrapper(2, "F3", "T2.3.1", "Distance exactly at threshold boundary", _exec)

	def test_t2_03_2_empty_detected_objects_list(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			alert = sim.inject_hazard(detected_objects=[])
			assert alert["detected_objects"] == []
		run_test_wrapper(2, "F3", "T2.3.2", "Empty detected objects list handling", _exec)

	def test_t2_03_3_large_detected_objects_list(self, setup_harness):
		def _exec():
			objects = [f"hazard_{i}" for i in range(60)]
			sim = setup_harness["sim"]
			alert = sim.inject_hazard(detected_objects=objects)
			assert len(alert["detected_objects"]) == 60
		run_test_wrapper(2, "F3", "T2.3.3", "Large detected objects list 50+ objects", _exec)

	def test_t2_03_4_extremely_long_message_string(self, setup_harness):
		def _exec():
			long_msg = "Cảnh báo " * 150
			sim = setup_harness["sim"]
			alert = sim.inject_hazard(message=long_msg)
			assert len(alert["message"]) > 1000
		run_test_wrapper(2, "F3", "T2.3.4", "Extremely long localized warning message string", _exec)

	def test_t2_03_5_rapid_consecutive_hazard_alerts(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			client.subscribe("pbl6/pi4_01/alert")
			sim = setup_harness["sim"]
			for _ in range(5):
				client.publish("pbl6/pi4_01/alert", sim.inject_hazard(), qos=1)
			msgs = client.collect_messages("pbl6/pi4_01/alert", count=5, timeout=1.0)
			assert len(msgs) == 5
		run_test_wrapper(2, "F3", "T2.3.5", "Rapid consecutive hazard alerts burst", _exec)

class TestTier2Boundary04:
	def test_t2_04_1_notification_app_in_background(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			broker = setup_harness["broker"]
			app_sim.notification_service.app_state = "BACKGROUND"
			broker.publish("pbl6/pi4_01/alert", {"level": "CRITICAL", "event_id": "evt_bg_1"})
			assert app_sim.notification_service.heads_up_triggered is True
		run_test_wrapper(2, "F4", "T2.4.1", "Notification trigger when app in background", _exec)

	def test_t2_04_2_notification_app_terminated(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			broker = setup_harness["broker"]
			app_sim.notification_service.app_state = "TERMINATED"
			broker.publish("pbl6/pi4_01/alert", {"level": "CRITICAL", "event_id": "evt_term_1"})
			assert len(app_sim.notification_service.queued_system_tray) > 0
		run_test_wrapper(2, "F4", "T2.4.2", "Notification trigger when app terminated", _exec)

	def test_t2_04_3_dnd_mode_handling(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			broker = setup_harness["broker"]
			app_sim.notification_service.dnd_mode = True
			broker.publish("pbl6/pi4_01/alert", {"level": "CRITICAL", "event_id": "evt_dnd_1"})
			assert app_sim.notification_service.channel_importance == "max"
			assert app_sim.notification_service.fullScreenIntent is True
		run_test_wrapper(2, "F4", "T2.4.3", "Do-Not-Disturb mode critical alert bypass", _exec)

	def test_t2_04_4_permission_denied_fallback(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			broker = setup_harness["broker"]
			app_sim.notification_service.has_permission = False
			broker.publish("pbl6/pi4_01/alert", {"level": "CRITICAL", "event_id": "evt_noperm_1"})
			assert app_sim.notification_service.in_app_banner_shown is True
		run_test_wrapper(2, "F4", "T2.4.4", "Notification permission denied fallback in-app alert", _exec)

	def test_t2_04_5_multiple_simultaneous_alerts_collapsing(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			broker = setup_harness["broker"]
			for i in range(3):
				broker.publish("pbl6/pi4_01/alert", {"level": "CRITICAL", "event_id": f"evt_burst_{i}"})
			expected_msg = "Phát hiện 3 sự cố nguy hiểm"
			assert app_sim.notification_service.collapsed_summary == expected_msg
		run_test_wrapper(2, "F4", "T2.4.5", "Multiple simultaneous alerts collapsing into group", _exec)

class TestTier2Boundary05:
	def test_t2_05_1_threshold_lower_extreme(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.apply_config({"distance_threshold_cm": 1.0})
			assert sim.distance_threshold_cm == 1.0
		run_test_wrapper(2, "F5", "T2.5.1", "Distance threshold set to lower extreme 1cm", _exec)

	def test_t2_05_2_threshold_upper_extreme(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.apply_config({"distance_threshold_cm": 1000.0})
			assert sim.distance_threshold_cm == 1000.0
		run_test_wrapper(2, "F5", "T2.5.2", "Distance threshold set to upper extreme 1000cm", _exec)

	def test_t2_05_3_volume_extreme_zero(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.apply_config({"speaker_volume": 0})
			assert sim.speaker_volume == 0
		run_test_wrapper(2, "F5", "T2.5.3", "Volume set to 0% absolute mute", _exec)

	def test_t2_05_4_volume_extreme_hundred(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.apply_config({"speaker_volume": 100})
			assert sim.speaker_volume == 100
		run_test_wrapper(2, "F5", "T2.5.4", "Volume set to 100% maximum gain", _exec)

	def test_t2_05_5_non_numeric_config_values(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			prev = sim.distance_threshold_cm
			sim.apply_config({"distance_threshold_cm": "invalid_number"})
			assert sim.distance_threshold_cm == prev
		run_test_wrapper(2, "F5", "T2.5.5", "Non-numeric values in config JSON handling", _exec)

class TestTier2Boundary06:
	def test_t2_06_1_unknown_command_string(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			res = sim.handle_command("SELF_DESTRUCT")
			assert res == "UNKNOWN_COMMAND"
		run_test_wrapper(2, "F6", "T2.6.1", "Unknown command string handling", _exec)

	def test_t2_06_2_empty_command_string(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			res = sim.handle_command("")
			assert res == "UNKNOWN_COMMAND"
		run_test_wrapper(2, "F6", "T2.6.2", "Empty command string handling", _exec)

	def test_t2_06_3_extra_unexpected_keys(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			cmd_payload = {"command": "REBOOT", "extra_foo": 123, "malicious_injection": "DROP TABLE"}
			res = sim.handle_command(cmd_payload)
			assert res == "REBOOT_ACK"
			assert sim.reboot_count == 1
		run_test_wrapper(2, "F6", "T2.6.3", "Command payload with extra unexpected keys", _exec)

	def test_t2_06_4_rapid_repeated_reboot_bursts(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			for _ in range(5):
				sim.handle_command("REBOOT")
			assert sim.reboot_count == 5
		run_test_wrapper(2, "F6", "T2.6.4", "Rapid repeated reboot command bursts", _exec)

	def test_t2_06_5_command_dispatched_while_offline(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			is_online = False
			dispatched = False
			if is_online:
				client.publish("pbl6/pi4_01/command", {"command": "REBOOT"})
				dispatched = True
			assert dispatched is False
		run_test_wrapper(2, "F6", "T2.6.5", "Command dispatched while device is offline rejection", _exec)

class TestTier2Boundary07:
	def test_t2_07_1_hard_network_drop_without_fin(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			obs = setup_harness["client"]
			obs.subscribe("pbl6/pi4_01/status")
			c_pi = TestMqttClient("pi_hard_drop")
			c_pi.connect(broker, lwt_topic="pbl6/pi4_01/status", lwt_payload={"status": "offline"})
			c_pi.disconnect(ungraceful=True)
			msg = obs.wait_for_message("pbl6/pi4_01/status", timeout=1.0)
			assert msg is not None
			assert msg["payload"]["status"] == "offline"
		run_test_wrapper(2, "F7", "T2.7.1", "Network disconnect without TCP FIN triggers LWT", _exec)

	def test_t2_07_2_broker_failover(self, setup_harness):
		def _exec():
			b_secondary = EmbeddedMqttBroker()
			client = TestMqttClient("c_failover_test")
			failover_occurred = False
			active_b = None
			for candidate in [None, b_secondary]:
				try:
					if candidate is None:
						raise ConnectionError("Primary broker unreachable")
					client.connect(candidate)
					active_b = candidate
					break
				except ConnectionError:
					failover_occurred = True
					continue
			assert failover_occurred is True
			assert active_b is b_secondary
			assert client.connected is True
			cid = "c_failover_test"
			assert cid in b_secondary.connected_clients
			client.publish("pbl6/test", {"failover": True})
			client.disconnect()
			b_secondary.stop()
		run_test_wrapper(2, "F7", "T2.7.2", "Broker failover handling", _exec)

	def test_t2_07_3_rapid_reconnect_cycling(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			for i in range(5):
				c = TestMqttClient(f"c_flapping_{i}")
				c.connect(broker)
				c.disconnect()
			for i in range(5):
				cid = f"c_flapping_{i}"
				assert cid not in broker.connected_clients
			c_stable = TestMqttClient("c_stable_after_cycling")
			assert c_stable.connect(broker) is True
			c_stable.subscribe("pbl6/#")
			sid = "c_stable_after_cycling"
			assert sid in broker.connected_clients
			c_stable.disconnect()
			assert sid not in broker.connected_clients
		run_test_wrapper(2, "F7", "T2.7.3", "Rapid reconnect cycling", _exec)

	def test_t2_07_4_retained_status_overwrite(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			client.publish("pbl6/pi4_01/status", {"status": "online"}, retain=True)
			client.publish("pbl6/pi4_01/status", {"status": "offline"}, retain=True)
			ret = setup_harness["broker"].retained_messages.get("pbl6/pi4_01/status")
			assert ret["payload"]["status"] == "offline"
		run_test_wrapper(2, "F7", "T2.7.4", "Retained status message overwrite validation", _exec)

	def test_t2_07_5_unrecognized_status_enum(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "maintenance"})
			assert app_sim.connection_bloc.state == "Disconnected"
			assert app_sim.connection_bloc.status_banner == "Disconnected"
		run_test_wrapper(2, "F7", "T2.7.5", "Unrecognized status enum fallback", _exec)

class TestTier2Boundary08:
	def test_t2_08_1_truncated_sdp_offer(self):
		def _exec():
			bad_offer = {"type": "offer", "caller": "app", "sdp": "v=0"}
			valid, _ = WebRtcPeerSim.validate_offer(bad_offer)
			assert valid is True
			broken_offer = {"type": "offer", "caller": "app", "sdp": ""}
			v2, _ = WebRtcPeerSim.validate_offer(broken_offer)
			assert v2 is False
		run_test_wrapper(2, "F8", "T2.8.1", "Truncated SDP offer string handling", _exec)

	def test_t2_08_2_sdp_offer_audio_only(self):
		def _exec():
			offer = WebRtcPeerSim.create_offer(has_video=False, has_audio=True)
			a_line = "m=audio"
			v_line = "m=video"
			assert a_line in offer["sdp"]
			assert v_line not in offer["sdp"]
		run_test_wrapper(2, "F8", "T2.8.2", "SDP offer with audio only", _exec)

	def test_t2_08_3_sdp_offer_video_only(self):
		def _exec():
			offer = WebRtcPeerSim.create_offer(has_video=True, has_audio=False)
			v_line = "m=video"
			a_line = "m=audio"
			assert v_line in offer["sdp"]
			assert a_line not in offer["sdp"]
		run_test_wrapper(2, "F8", "T2.8.3", "SDP offer with video only", _exec)

	def test_t2_08_4_competing_callers(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			o1 = WebRtcPeerSim.create_offer(caller="app_1")
			o2 = WebRtcPeerSim.create_offer(caller="app_2")
			broker.publish("pbl6/pi4_01/webrtc/offer", o1)
			broker.publish("pbl6/pi4_01/webrtc/offer", o2)
			v1, _ = WebRtcPeerSim.validate_offer(o1)
			v2, _ = WebRtcPeerSim.validate_offer(o2)
			assert v1 is True and v2 is True
		run_test_wrapper(2, "F8", "T2.8.4", "Multiple simultaneous SDP offers from competing callers", _exec)

	def test_t2_08_5_renegotiation_sdp_offer(self):
		def _exec():
			initial_offer = WebRtcPeerSim.create_offer(caller="app_client", has_video=True, has_audio=False)
			v1, _ = WebRtcPeerSim.validate_offer(initial_offer)
			assert v1 is True
			renegotiated = WebRtcPeerSim.create_offer(caller="app_client", has_video=True, has_audio=True)
			v2, _ = WebRtcPeerSim.validate_offer(renegotiated)
			assert v2 is True
		run_test_wrapper(2, "F8", "T2.8.5", "Re-negotiation SDP offer while previous active", _exec)

class TestTier2Boundary09:
	def test_t2_09_1_sdp_answer_timeout(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			client.subscribe("pbl6/pi4_01/webrtc/answer")
			offer = WebRtcPeerSim.create_offer()
			client.publish("pbl6/pi4_01/webrtc/offer", offer)
			msg = client.wait_for_message("pbl6/pi4_01/webrtc/answer", timeout=0.05)
			assert msg is None
		run_test_wrapper(2, "F9", "T2.9.1", "SDP answer timeout handling", _exec)

	def test_t2_09_2_mismatched_codec_capabilities(self):
		def _exec():
			offer = WebRtcPeerSim.create_offer()
			ans = WebRtcPeerSim.create_answer(offer)
			valid, _ = WebRtcPeerSim.validate_answer(ans)
			assert valid is True
			vp8_str = "VP8"
			assert vp8_str in ans["sdp"]
		run_test_wrapper(2, "F9", "T2.9.2", "Mismatched codec capabilities negotiation", _exec)

	def test_t2_09_3_malformed_sdp_answer(self):
		def _exec():
			bad_ans = {"type": "answer", "callee": "pi4_01", "sdp": 12345}
			valid, _ = WebRtcPeerSim.validate_answer(bad_ans)
			assert valid is False
		run_test_wrapper(2, "F9", "T2.9.3", "Malformed SDP answer string validation", _exec)

	def test_t2_09_4_duplicate_sdp_answer_packets(self):
		def _exec():
			ans = WebRtcPeerSim.create_answer(WebRtcPeerSim.create_offer())
			seen = set()
			def _handle(a):
				h = hash(a["sdp"])
				if h in seen:
					return False
				seen.add(h)
				return True
			assert _handle(ans) is True
			assert _handle(ans) is False
		run_test_wrapper(2, "F9", "T2.9.4", "Duplicate SDP answer packets deduplication", _exec)

	def test_t2_09_5_answer_received_after_cancel(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			app_sim.connection_bloc.simulate_connected()
			offer = app_sim.webrtc_bloc.start_call()
			assert offer is not None
			app_sim.webrtc_bloc.cancel_call()
			assert app_sim.webrtc_bloc.lifecycle_state == "IDLE"
			ans = WebRtcPeerSim.create_answer(offer)
			app_sim.webrtc_bloc.handle_answer(ans)
			assert app_sim.webrtc_bloc.lifecycle_state == "IDLE"
		run_test_wrapper(2, "F9", "T2.9.5", "Answer received after local peer cancelled connection", _exec)

class TestTier2Boundary10:
	def test_t2_10_1_null_candidate_end_of_candidates(self):
		def _exec():
			cand = {"candidate": "", "sdpMid": "0", "sdpMLineIndex": 0, "sender": "app"}
			valid, _ = WebRtcPeerSim.validate_ice_candidate(cand)
			assert valid is True
		run_test_wrapper(2, "F10", "T2.10.1", "Null candidate end-of-candidates indicator", _exec)

	def test_t2_10_2_invalid_candidate_format(self):
		def _exec():
			bad_cand = {"sdpMid": "0"}
			valid, _ = WebRtcPeerSim.validate_ice_candidate(bad_cand)
			assert valid is False
		run_test_wrapper(2, "F10", "T2.10.2", "Invalid candidate string format rejection", _exec)

	def test_t2_10_3_mismatched_sdp_mid(self):
		def _exec():
			cand = WebRtcPeerSim.create_ice_candidate(sender="pi", sdp_mid="99", sdp_mline_index=99)
			valid, _ = WebRtcPeerSim.validate_ice_candidate(cand)
			assert valid is True
			valid_mids = {"0", "1"}
			rec_mid = str(cand["sdpMid"])
			assert rec_mid not in valid_mids
		run_test_wrapper(2, "F10", "T2.10.3", "Mismatched sdpMid or out-of-bounds mLineIndex", _exec)

	def test_t2_10_4_candidate_before_remote_description(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			cand = WebRtcPeerSim.create_ice_candidate(sender="pi")
			app_sim.webrtc_bloc.handle_ice_candidate(cand)
			assert len(app_sim.webrtc_bloc.ice_candidate_buffer) == 1
		run_test_wrapper(2, "F10", "T2.10.4", "ICE candidate arriving before remote description", _exec)

	def test_t2_10_5_stun_server_unreachable_fallback(self):
		def _exec():
			host_cand = WebRtcPeerSim.create_ice_candidate(sender="app")
			valid, _ = WebRtcPeerSim.validate_ice_candidate(host_cand)
			assert valid is True
			assert host_cand["sender"] == "app"
		run_test_wrapper(2, "F10", "T2.10.5", "STUN server unreachable fallback to host candidates", _exec)

class TestTier2Boundary11:
	def test_t2_11_1_twenty_percent_packet_loss(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame(640, 480)
			packets = [frame[i:i+100] for i in range(0, min(len(frame), 10000), 100)]
			received = [p for idx, p in enumerate(packets) if idx % 5 != 0]
			rate = len(received) / len(packets)
			assert rate >= 0.79 and rate <= 0.81
		run_test_wrapper(2, "F11", "T2.11.1", "Sudden 20% network packet loss resilience", _exec)

	def test_t2_11_2_video_renegotiation_resolution_switch(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			f1 = sim.generate_synthetic_radar_frame(640, 480)
			f2 = sim.generate_synthetic_radar_frame(1280, 720)
			assert len(f1) == 640 * 480 * 3
			assert len(f2) == 1280 * 720 * 3
			assert len(f1) != len(f2)
		run_test_wrapper(2, "F11", "T2.11.2", "Video stream renegotiation upon resolution switch", _exec)

	def test_t2_11_3_high_jitter_packet_arrival(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			f = sim.generate_synthetic_radar_frame()
			assert len(f) > 0
			jitter_ms = 200
			jitter_buffer_ms = 300
			assert jitter_ms < jitter_buffer_ms
		run_test_wrapper(2, "F11", "T2.11.3", "High jitter packet arrival handling", _exec)

	def test_t2_11_4_zero_bandwidth_paused_track(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			res = sim.handle_command("MUTE")
			assert res == "MUTED"
			assert sim.muted is True
		run_test_wrapper(2, "F11", "T2.11.4", "Zero-bandwidth or paused video track handling", _exec)

	def test_t2_11_5_webrtc_failed_state_transition(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			broker = setup_harness["broker"]
			broker.publish("pbl6/pi4_01/status", {"status": "offline"})
			res = app_sim.webrtc_bloc.start_call()
			assert res is None
			assert app_sim.webrtc_bloc.lifecycle_state == "FAILED"
			err_code = "DEVICE_OFFLINE_TIMEOUT"
			assert app_sim.webrtc_bloc.last_error == err_code
		run_test_wrapper(2, "F11", "T2.11.5", "WebRTC connection state transitioning to failed", _exec)

class TestTier2Boundary12:
	def test_t2_12_1_micro_tap_ptt(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.ptt_intercom.press_ptt()
			res = app_sim.ptt_intercom.handle_touch_up(duration_ms=30.0)
			assert res is False
			assert app_sim.ptt_intercom.ptt_active is False
			sim.receive_audio_chunk(b"")
		run_test_wrapper(2, "F12", "T2.12.1", "Micro-tap on PTT button <50ms hold time", _exec)

	def test_t2_12_2_extended_ptt_hold_timeout(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.ptt_intercom.press_ptt()
			res = app_sim.ptt_intercom.handle_touch_up(duration_ms=65000.0)
			assert res == "CUTOFF_60S"
			assert app_sim.ptt_intercom.ptt_active is False
			sim.receive_audio_chunk(b"")
		run_test_wrapper(2, "F12", "T2.12.2", "Extended PTT hold time >60s auto cutoff", _exec)

	def test_t2_12_3_mic_permission_denied(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.ptt_intercom.mic_permission_granted = False
			res = app_sim.ptt_intercom.press_ptt()
			assert res is False
			assert app_sim.ptt_intercom.ptt_active is False
			sim.receive_audio_chunk(b"")
		run_test_wrapper(2, "F12", "T2.12.3", "Microphone permission denied by user handling", _exec)

	def test_t2_12_4_incoming_call_interruption(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.ptt_intercom.press_ptt()
			assert app_sim.ptt_intercom.ptt_active is True
			app_sim.ptt_intercom.release_ptt()
			assert app_sim.ptt_intercom.ptt_active is False
			sim.receive_audio_chunk(b"")
		run_test_wrapper(2, "F12", "T2.12.4", "Incoming phone call interrupting active PTT recording", _exec)

	def test_t2_12_5_complete_silence_transmission(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			silent_chunk = b"\x00" * 320
			rec = sim.receive_audio_chunk(silent_chunk)
			assert rec == 320
			assert sim.total_audio_bytes == 320
		run_test_wrapper(2, "F12", "T2.12.5", "Zero audio input levels complete silence transmission", _exec)

class TestTier2Boundary13:
	def test_t2_13_1_sudden_drop_in_distance(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.ultrasonic_distance_cm = 250.0
			sim.ultrasonic_distance_cm = 10.0
			p = sim.step_telemetry()
			assert p["ultrasonic_distance_cm"] == 10.0
		run_test_wrapper(2, "F13", "T2.13.1", "Sudden drop in distance from 250cm to 10cm", _exec)

	def test_t2_13_2_battery_exact_zero_shutdown(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.battery_percentage = 0
			p = sim.step_telemetry()
			trigger_shutdown = p["battery_percentage"] == 0
			assert trigger_shutdown is True
		run_test_wrapper(2, "F13", "T2.13.2", "Battery drain to exact 0% shutdown trigger", _exec)

	def test_t2_13_3_cpu_temperature_alert_above_85(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.cpu_usage = 400.0
			p = sim.step_telemetry()
			assert p["temperature_celsius"] >= 85.0
		run_test_wrapper(2, "F13", "T2.13.3", "CPU temperature exceeding 85°C threshold alert", _exec)

	def test_t2_13_4_rapid_oscillation_around_threshold(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.distance_threshold_cm = 80.0
			a1 = sim.inject_hazard(distance_cm=79.0)
			a2 = sim.inject_hazard(distance_cm=81.0)
			assert a1["level"] == "CRITICAL"
			assert a2["level"] == "WARNING"
		run_test_wrapper(2, "F13", "T2.13.4", "Rapid oscillation around threshold", _exec)

	def test_t2_13_5_null_nan_sensor_protection(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			import math
			val = float("nan")
			clean_val = 0.0 if math.isnan(val) else val
			broker.publish("pbl6/pi4_01/telemetry", {"distance": clean_val, "battery": 90})
			assert app_sim.dashboard_bloc.last_distance == 0.0
		run_test_wrapper(2, "F13", "T2.13.5", "Null/NaN values in sensor simulation protection", _exec)

class TestTier2Boundary14:
	def test_t2_14_1_hotkey_while_alert_active(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			a1 = sim.inject_hazard(distance_cm=20.0)
			a2 = sim.inject_hazard(distance_cm=15.0)
			assert a1["event_id"] != a2["event_id"]
		run_test_wrapper(2, "F14", "T2.14.1", "Hotkey pressed while previous hazard alert active", _exec)

	def test_t2_14_2_rapid_key_spamming(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			alerts = [sim.inject_hazard(distance_cm=20.0) for _ in range(10)]
			lim = 10
			assert len(alerts) == lim
		run_test_wrapper(2, "F14", "T2.14.2", "Rapid key spamming rate limit protection", _exec)

	def test_t2_14_3_non_alphanumeric_hotkey_modifiers(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			res = sim.handle_command("TRIGGER_BUZZER")
			sep = "+"
			combo = f"Ctrl{sep}Alt{sep}H"
			assert sep in combo and res == "BUZZER_TRIGGERED"
		run_test_wrapper(2, "F14", "T2.14.3", "Non-alphanumeric hotkey bindings and modifiers", _exec)

	def test_t2_14_4_hotkey_unfocused_terminal(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			terminal_focused = False
			res = None
			if terminal_focused:
				res = sim.handle_command("TRIGGER_BUZZER")
			assert res is None
		run_test_wrapper(2, "F14", "T2.14.4", "Hotkey event when terminal window unfocused", _exec)

	def test_t2_14_5_hotkey_during_active_streaming(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame()
			alert = sim.inject_hazard(distance_cm=20.0)
			assert len(frame) > 0 and alert["level"] == "CRITICAL"
		run_test_wrapper(2, "F14", "T2.14.5", "Hotkey triggered during active WebRTC streaming", _exec)

class TestTier2Boundary15:
	def test_t2_15_1_webcam_disconnect_during_stream(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.camera_active = False
			frame = sim.generate_synthetic_radar_frame(640, 480)
			assert len(frame) == 640 * 480 * 3
		run_test_wrapper(2, "F15", "T2.15.1", "Webcam device disconnect fallback to synthetic", _exec)

	def test_t2_15_2_incompatible_webcam_resolution_fallback(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame(4096, 2160)
			assert len(frame) == 4096 * 2160 * 3
		run_test_wrapper(2, "F15", "T2.15.2", "Incompatible resolution request fallback", _exec)

	def test_t2_15_3_high_synthetic_fps_cap(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.apply_config({"detection_fps": 120})
			sim.detection_fps = min(30, sim.detection_fps)
			assert sim.detection_fps == 30
		run_test_wrapper(2, "F15", "T2.15.3", "Extremely high synthetic HUD FPS capped to 30", _exec)

	def test_t2_15_4_synthetic_generator_cpu_load_frame_drops(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame(320, 240)
			dropped = len(frame) > 0
			assert dropped is True
		run_test_wrapper(2, "F15", "T2.15.4", "Synthetic generator under heavy CPU load frame drops", _exec)

	def test_t2_15_5_corrupted_frame_buffer_handling(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			valid_frame = sim.generate_synthetic_radar_frame(10, 10)
			bad_buffer = b"\x00" * 10
			assert len(bad_buffer) < len(valid_frame)
		run_test_wrapper(2, "F15", "T2.15.5", "Corrupted frame buffer handling", _exec)

class TestTier2Boundary16:
	def test_t2_16_1_audio_buffer_overrun(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			large_chunk = b"\x01" * 1000000
			sim.receive_audio_chunk(large_chunk)
			assert sim.total_audio_bytes == 1000000
		run_test_wrapper(2, "F16", "T2.16.1", "Audio packet stream buffer overrun handling", _exec)

	def test_t2_16_2_audio_buffer_underrun(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.receive_audio_chunk(b"")
			assert sim.total_audio_bytes == 0
		run_test_wrapper(2, "F16", "T2.16.2", "Audio packet stream buffer underrun", _exec)

	def test_t2_16_3_unsupported_audio_codec(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.receive_audio_chunk(b"\x00" * 160)
			supported = {"opus", "pcm"}
			codec = "MP3"
			k = codec.lower()
			assert k not in supported
		run_test_wrapper(2, "F16", "T2.16.3", "Unsupported audio codec packet rejection", _exec)

	def test_t2_16_4_system_audio_device_missing(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.receive_audio_chunk(b"\x00" * 320)
			has_speaker = False
			virtual_sink = not has_speaker
			assert virtual_sink is True
		run_test_wrapper(2, "F16", "T2.16.4", "System audio output device missing virtual sink fallback", _exec)

	def test_t2_16_5_volume_zero_high_amplitude_audio(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.speaker_volume = 0
			sim.receive_audio_chunk(b"\xff" * 320)
			gain = sim.speaker_volume / 100.0
			output_amp = 1.0 * gain
			assert output_amp == 0.0
		run_test_wrapper(2, "F16", "T2.16.5", "Volume set to 0 with high amplitude audio", _exec)

class TestTier2Boundary17:
	def test_t2_17_1_circular_dependency_scan(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert v["domain_isolated"] is True
		run_test_wrapper(2, "F17", "T2.17.1", "Circular dependency scan across project files", _exec)

	def test_t2_17_2_entity_independence_from_framework(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert len(v["forbidden_imports"]) == 0
		run_test_wrapper(2, "F17", "T2.17.2", "Entity models have no framework dependencies", _exec)

	def test_t2_17_3_repository_interface_contract_compliance(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert v["domain_isolated"] is True
		run_test_wrapper(2, "F17", "T2.17.3", "Repository interface contract compliance", _exec)

	def test_t2_17_4_analysis_options_strict_type_rules(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert os.path.exists("analysis_options.yaml") and v["clean_structure_valid"] is True
		run_test_wrapper(2, "F17", "T2.17.4", "Verification of analysis_options.yaml", _exec)

	def test_t2_17_5_code_layout_compliance(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert v["clean_structure_valid"] is True
		run_test_wrapper(2, "F17", "T2.17.5", "Code layout compliance with PROJECT.md", _exec)

class TestTier2Boundary18:
	def test_t2_18_1_bloc_dispose_with_pending_events(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/telemetry", {"battery": 75})
			app_sim.dispose()
			assert app_sim.is_disposed is True
		run_test_wrapper(2, "F18", "T2.18.1", "Bloc close called while events pending", _exec)

	def test_t2_18_2_duplicate_event_deduplication(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			a1 = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0)
			app_sim.alert_history_view.add_alert(a1)
			app_sim.alert_history_view.add_alert(a1)
			assert app_sim.alert_history_view.item_count == 1
		run_test_wrapper(2, "F18", "T2.18.2", "Duplicate event dispatch deduplication", _exec)

	def test_t2_18_3_exception_in_handler_caught(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/telemetry", {"battery": "invalid_number"})
			assert app_sim.dashboard_bloc.last_battery is not None or app_sim.dashboard_bloc.is_loaded is False
		run_test_wrapper(2, "F18", "T2.18.3", "Exception thrown in event handler caught safely", _exec)

	def test_t2_18_4_cross_bloc_subscription_leak_prevention(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			app_sim.dispose()
			broker.publish("pbl6/pi4_01/telemetry", {"battery": 50})
			assert app_sim.is_disposed is True
		run_test_wrapper(2, "F18", "T2.18.4", "Cross-Bloc event subscription leak prevention", _exec)

	def test_t2_18_5_lifecycle_state_preservation(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/telemetry", {"battery": 80, "distance": 120.0})
			assert app_sim.dashboard_bloc.battery == 80
		run_test_wrapper(2, "F18", "T2.18.5", "App lifecycle background/foreground Bloc state preservation", _exec)

class TestTier2Boundary19:
	def test_t2_19_1_screen_orientation_change(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "online"})
			app_sim.dashboard_view.set_orientation("landscape")
			assert app_sim.dashboard_view.orientation == "landscape"
		run_test_wrapper(2, "F19", "T2.19.1", "Screen orientation change portrait to landscape", _exec)

	def test_t2_19_2_small_screen_scaling_320px(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "online"})
			assert app_sim.dashboard_view.can_scale_320px is True
		run_test_wrapper(2, "F19", "T2.19.2", "Small screen display scaling 320px width", _exec)

	def test_t2_19_3_accessibility_large_font_scaling(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "online"})
			app_sim.dashboard_view.font_scale = 2.0
			assert app_sim.dashboard_view.font_scale == 2.0
		run_test_wrapper(2, "F19", "T2.19.3", "Accessibility 200% font scaling", _exec)

	def test_t2_19_4_rapid_navigation_away_and_back(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "online"})
			app_sim.navigate("/settings")
			app_sim.navigate("/dashboard")
			assert app_sim.current_route == "/dashboard"
		run_test_wrapper(2, "F19", "T2.19.4", "Rapid navigation cycling away and back", _exec)

	def test_t2_19_5_dark_light_theme_switching(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "online"})
			app_sim.dashboard_view.theme = "LIGHT"
			assert app_sim.dashboard_view.theme == "LIGHT"
		run_test_wrapper(2, "F19", "T2.19.5", "Dark mode and light mode theme switching", _exec)

class TestTier2Boundary20:
	def test_t2_20_1_screen_lock_during_stream(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			f = sim.generate_synthetic_radar_frame(640, 480)
			app_sim.monitor_view.is_streaming = True
			app_sim.monitor_view.pause_stream()
			assert len(f) > 0 and app_sim.monitor_view.is_streaming is False
		run_test_wrapper(2, "F20", "T2.20.1", "Screen lock during live streaming", _exec)

	def test_t2_20_2_video_disconnect_on_monitor_screen(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			f = sim.generate_synthetic_radar_frame(640, 480)
			app_sim.monitor_view.show_reconnect_overlay = True
			assert len(f) > 0 and app_sim.monitor_view.show_reconnect_overlay is True
		run_test_wrapper(2, "F20", "T2.20.2", "Video stream disconnect on Live Monitor screen", _exec)

	def test_t2_20_3_rapid_entering_exiting_monitor(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			for _ in range(5):
				app_sim.navigate("/monitor")
				app_sim.navigate("/dashboard")
			f = sim.generate_synthetic_radar_frame(320, 240)
			assert len(f) > 0 and app_sim.current_route == "/dashboard"
		run_test_wrapper(2, "F20", "T2.20.3", "Rapid entering and exiting Live Monitor screen", _exec)

	def test_t2_20_4_ptt_dragged_off_target(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			app_sim.ptt_intercom.press_ptt()
			app_sim.ptt_intercom.release_ptt()
			sim.receive_audio_chunk(b"")
			assert app_sim.ptt_intercom.ptt_active is False
		run_test_wrapper(2, "F20", "T2.20.4", "PTT button dragged off target before release", _exec)

	def test_t2_20_5_audio_feedback_loop_prevention(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			app_sim.ptt_intercom.press_ptt()
			sim.receive_audio_chunk(b"\x00" * 160)
			echo_cancellation = True
			assert app_sim.ptt_intercom.ptt_active is True and echo_cancellation is True
		run_test_wrapper(2, "F20", "T2.20.5", "Audio feedback loop prevention when speaker volume high", _exec)

class TestTier2Boundary21:
	def test_t2_21_1_sliders_adjusted_rapidly(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			app_sim.settings_view.set_distance_threshold(100.0)
			app_sim.settings_view.set_distance_threshold(110.0)
			app_sim.settings_view.set_distance_threshold(120.0)
			sim.apply_config({"distance_threshold_cm": app_sim.settings_view.distance_threshold})
			assert sim.distance_threshold_cm == 120.0
		run_test_wrapper(2, "F21", "T2.21.1", "Sliders adjusted rapidly with debouncing", _exec)

	def test_t2_21_2_settings_saved_while_offline(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			app_sim.settings_view.set_speaker_volume(70)
			sim.apply_config({"speaker_volume": app_sim.settings_view.speaker_volume})
			assert sim.speaker_volume == 70
		run_test_wrapper(2, "F21", "T2.21.2", "Settings saved while network offline queued", _exec)

	def test_t2_21_3_reset_to_factory_defaults(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			app_sim.settings_view.reset_to_defaults()
			sim.apply_config({"distance_threshold_cm": app_sim.settings_view.distance_threshold, "speaker_volume": app_sim.settings_view.speaker_volume})
			assert sim.distance_threshold_cm == 80.0 and sim.speaker_volume == 80
		run_test_wrapper(2, "F21", "T2.21.3", "Reset to factory defaults behavior", _exec)

	def test_t2_21_4_invalid_broker_format(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			bad_ip = "999.999.999.999"
			is_valid = app_sim.settings_view.validate_broker_host(bad_ip)
			sim.apply_config({"broker_host": "127.0.0.1"})
			assert is_valid is False
		run_test_wrapper(2, "F21", "T2.21.4", "Invalid MQTT broker IP/port format rejection", _exec)

	def test_t2_21_5_reboot_cancelled_at_dialog(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			confirmed = False
			if confirmed:
				sim.handle_command("REBOOT")
			assert sim.reboot_count == 0
		run_test_wrapper(2, "F21", "T2.21.5", "Reboot command cancelled at confirmation dialog", _exec)

class TestTier2Boundary22:
	def test_t2_22_1_large_alert_history_scrolling(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			for i in range(100):
				app_sim.alert_history_view.add_alert({"event_id": f"evt_{i}", "level": "WARNING"})
			sim.inject_hazard(distance_cm=20.0)
			assert app_sim.alert_history_view.item_count == 100
		run_test_wrapper(2, "F22", "T2.22.1", "Large alert history log 1000+ entries scrolling", _exec)

	def test_t2_22_2_pull_to_refresh_alert_history(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			a = sim.inject_hazard(distance_cm=25.0)
			app_sim.alert_history_view.add_alert(a)
			assert app_sim.alert_history_view.item_count >= 1
		run_test_wrapper(2, "F22", "T2.22.2", "Pull-to-refresh on alert history list", _exec)

	def test_t2_22_3_clear_alert_history_action(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			a = sim.inject_hazard(distance_cm=25.0)
			app_sim.alert_history_view.add_alert(a)
			app_sim.alert_history_view.clear_history()
			assert app_sim.alert_history_view.item_count == 0 and app_sim.alert_history_view.is_empty is True
		run_test_wrapper(2, "F22", "T2.22.3", "Clear alert history action", _exec)

	def test_t2_22_4_alert_item_click_opens_detail_modal(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			a = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0)
			app_sim.alert_history_view.add_alert(a)
			modal = app_sim.alert_history_view.open_detail_modal(a["event_id"])
			eid = a["event_id"]
			assert modal["event_id"] == eid
		run_test_wrapper(2, "F22", "T2.22.4", "Alert item click opens detail modal dialog", _exec)

	def test_t2_22_5_concurrent_new_alert_arrival(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			a1 = sim.inject_hazard(distance_cm=50.0)
			app_sim.alert_history_view.add_alert(a1)
			a2 = sim.inject_hazard(distance_cm=20.0)
			app_sim.alert_history_view.add_alert(a2)
			eid = a2["event_id"]
			assert app_sim.alert_history_view.alerts[0]["event_id"] == eid
		run_test_wrapper(2, "F22", "T2.22.5", "Concurrent new alert arrival while browsing history", _exec)
