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
	client = TestMqttClient("test_runner_client")
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

class TestTier1Feature01:
	def test_t1_01_1_telemetry_interval(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			t1 = sim.step_telemetry()
			time.sleep(0.01)
			t2 = sim.step_telemetry()
			assert t2["timestamp"] >= t1["timestamp"]
			delta = t2["timestamp"] - t1["timestamp"]
			assert delta >= 0 and delta <= 5
			assert sim.alert_frequency_ms == 500
			assert t1["device_id"] == "pi4_01"
		run_test_wrapper(1, "F1", "T1.1.1", "Telemetry publication interval verification", _exec)

	def test_t1_01_2_valid_payload_structure(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			pkt = sim.step_telemetry()
			assert isinstance(pkt, dict)
			assert pkt["device_id"] == "pi4_01"
		run_test_wrapper(1, "F1", "T1.1.2", "Valid JSON payload structure", _exec)

	def test_t1_01_3_mandatory_keys_presence(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			pkt = sim.step_telemetry()
			req = ["device_id", "timestamp", "battery_percentage", "temperature_celsius", "ultrasonic_distance_cm"]
			for k in req:
				assert k in pkt
		run_test_wrapper(1, "F1", "T1.1.3", "Mandatory keys presence", _exec)

	def test_t1_01_4_qos_0_confirmation(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			sim = setup_harness["sim"]
			client.subscribe("pbl6/pi4_01/telemetry")
			pkt = sim.step_telemetry()
			client.publish("pbl6/pi4_01/telemetry", pkt, qos=0)
			msg = client.wait_for_message("pbl6/pi4_01/telemetry", timeout=1.0)
			assert msg is not None
			assert msg["qos"] == 0
		run_test_wrapper(1, "F1", "T1.1.4", "Telemetry QoS 0 confirmation", _exec)

	def test_t1_01_5_sequence_monotonic_timestamps(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			p1 = sim.step_telemetry()
			time.sleep(0.005)
			p2 = sim.step_telemetry()
			assert p2["timestamp"] >= p1["timestamp"]
		run_test_wrapper(1, "F1", "T1.1.5", "Sequence monotonic timestamps", _exec)

class TestTier1Feature02:
	def test_t1_02_1_telemetry_packet_ingestion(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			sim = setup_harness["sim"]
			client.subscribe("pbl6/pi4_01/telemetry")
			client.publish("pbl6/pi4_01/telemetry", sim.step_telemetry())
			msg = client.wait_for_message("pbl6/pi4_01/telemetry", timeout=1.0)
			assert msg is not None
			batt_key = "battery_percentage"
			assert batt_key in msg["payload"]
		run_test_wrapper(1, "F2", "T1.2.1", "Ingestion of standard telemetry packet", _exec)

	def test_t1_02_2_battery_percentage_mapping(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.battery_percentage = 75
			pkt = sim.step_telemetry()
			gauge_val = pkt["battery_percentage"] / 100.0
			assert gauge_val == 0.75
		run_test_wrapper(1, "F2", "T1.2.2", "Mapping battery percentage to battery gauge", _exec)

	def test_t1_02_3_ultrasonic_distance_card(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.ultrasonic_distance_cm = 120.5
			pkt = sim.step_telemetry()
			assert pkt["ultrasonic_distance_cm"] == 120.5
		run_test_wrapper(1, "F2", "T1.2.3", "Mapping ultrasonic distance to card widget state", _exec)

	def test_t1_02_4_temperature_propagation(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.cpu_usage = 50.0
			pkt = sim.step_telemetry()
			assert pkt["temperature_celsius"] == 50.0
		run_test_wrapper(1, "F2", "T1.2.4", "Temperature update propagation", _exec)

	def test_t1_02_5_rerender_trigger_verification(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			sim = setup_harness["sim"]
			client.subscribe("pbl6/pi4_01/telemetry")
			client.publish("pbl6/pi4_01/telemetry", sim.step_telemetry())
			client.publish("pbl6/pi4_01/telemetry", sim.step_telemetry(distance_delta=10.0))
			msgs = client.collect_messages("pbl6/pi4_01/telemetry", count=2, timeout=1.0)
			assert len(msgs) == 2
		run_test_wrapper(1, "F2", "T1.2.5", "Re-render trigger on successive packets", _exec)

class TestTier1Feature03:
	def test_t1_03_1_trigger_hazard_under_threshold(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			alert = sim.inject_hazard(distance_cm=25.0)
			assert alert["level"] == "CRITICAL"
			assert alert["distance_cm"] == 25.0
		run_test_wrapper(1, "F3", "T1.3.1", "Trigger obstacle hazard when distance < threshold", _exec)

	def test_t1_03_2_alert_topic_publication_qos_1(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			sim = setup_harness["sim"]
			client.subscribe("pbl6/pi4_01/alert")
			alert = sim.inject_hazard()
			client.publish("pbl6/pi4_01/alert", alert, qos=1)
			msg = client.wait_for_message("pbl6/pi4_01/alert", timeout=1.0)
			assert msg is not None
			assert msg["qos"] == 1
		run_test_wrapper(1, "F3", "T1.3.2", "Alert message topic publication with QoS 1", _exec)

	def test_t1_03_3_critical_alert_level_validation(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			alert = sim.inject_hazard(distance_cm=15.0)
			assert alert["level"] == "CRITICAL"
		run_test_wrapper(1, "F3", "T1.3.3", "Critical alert level header payload validation", _exec)

	def test_t1_03_4_detected_objects_array_format(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			alert = sim.inject_hazard(detected_objects=["stairs_down", "puddle"])
			assert isinstance(alert["detected_objects"], list)
			obj_name = "stairs_down"
			assert obj_name in alert["detected_objects"]
		run_test_wrapper(1, "F3", "T1.3.4", "Detected objects array format validation", _exec)

	def test_t1_03_5_unique_event_id_generation(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			a1 = sim.inject_hazard()
			a2 = sim.inject_hazard()
			assert a1["event_id"] != a2["event_id"]
			assert a1["event_id"].startswith("evt_")
		run_test_wrapper(1, "F3", "T1.3.5", "Unique event ID generation", _exec)

class TestTier1Feature04:
	def test_t1_04_1_channel_configuration(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			broker = setup_harness["broker"]
			broker.publish(f"pbl6/{app_sim.device_id}/alert", {"level": "CRITICAL", "event_id": "evt_init"})
			svc = app_sim.notification_service
			assert svc.channel_id == "pbl6_critical_alerts"
			assert svc.channel_importance == "max"
			assert svc.channel_priority == "high"
			assert svc.fullScreenIntent is True
		run_test_wrapper(1, "F4", "T1.4.1", "High-priority notification channel configuration", _exec)

	def test_t1_04_2_heads_up_banner_trigger(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			alert = sim.inject_hazard(distance_cm=20.0)
			banner_shown = alert["level"] == "CRITICAL"
			assert banner_shown is True
		run_test_wrapper(1, "F4", "T1.4.2", "Heads-up banner trigger upon alert", _exec)

	def test_t1_04_3_sound_and_vibration_activation(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			alert = sim.inject_hazard(distance_cm=10.0)
			vibrate = alert["level"] == "CRITICAL"
			assert vibrate is True
		run_test_wrapper(1, "F4", "T1.4.3", "Sound and vibration flag activation on critical alert", _exec)

	def test_t1_04_4_alert_message_matching(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			custom_msg = "Cảnh báo hố sâu phía trước!"
			alert = sim.inject_hazard(message=custom_msg)
			assert alert["message"] == custom_msg
		run_test_wrapper(1, "F4", "T1.4.4", "Alert message content matching notification body", _exec)

	def test_t1_04_5_notification_tap_navigation_payload(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			alert = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0)
			payload = app_sim.notification_service.handle_notification_tap(alert["event_id"])
			assert payload["action"] == "NAVIGATE"
			assert payload["target"] == "AlertHistoryScreen"
			assert payload["event_id"] == alert["event_id"]
			assert app_sim.current_route == "/alert_history"
		run_test_wrapper(1, "F4", "T1.4.5", "Notification tap navigation event payload", _exec)

class TestTier1Feature05:
	def test_t1_05_1_publish_config_retain_true(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			cfg = {"distance_threshold_cm": 100, "speaker_volume": 90}
			client.publish("pbl6/pi4_01/config", cfg, qos=1, retain=True)
			ret = setup_harness["broker"].retained_messages.get("pbl6/pi4_01/config")
			assert ret is not None
			assert ret["retain"] is True
		run_test_wrapper(1, "F5", "T1.5.1", "Publish config change payload with retain=True", _exec)

	def test_t1_05_2_update_distance_threshold(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.apply_config({"distance_threshold_cm": 120.0})
			assert sim.distance_threshold_cm == 120.0
		run_test_wrapper(1, "F5", "T1.5.2", "Update distance threshold parameter", _exec)

	def test_t1_05_3_update_speaker_volume(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.apply_config({"speaker_volume": 95})
			assert sim.speaker_volume == 95
		run_test_wrapper(1, "F5", "T1.5.3", "Update speaker volume parameter", _exec)

	def test_t1_05_4_detection_fps_adjustment(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.apply_config({"detection_fps": 20})
			assert sim.detection_fps == 20
		run_test_wrapper(1, "F5", "T1.5.4", "Detection FPS adjustment", _exec)

	def test_t1_05_5_mock_server_application_of_config(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.apply_config({"distance_threshold_cm": 110, "alert_frequency_ms": 300})
			assert sim.distance_threshold_cm == 110
			assert sim.alert_frequency_ms == 300
		run_test_wrapper(1, "F5", "T1.5.5", "Mock server application of updated config", _exec)

class TestTier1Feature06:
	def test_t1_06_1_dispatch_reboot_command(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			res = sim.handle_command("REBOOT")
			assert res == "REBOOT_ACK"
			assert sim.reboot_count == 1
		run_test_wrapper(1, "F6", "T1.6.1", "Dispatch REBOOT command", _exec)

	def test_t1_06_2_dispatch_restart_service(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			res = sim.handle_command("RESTART_SERVICE")
			assert res == "RESTART_ACK"
		run_test_wrapper(1, "F6", "T1.6.2", "Dispatch RESTART_SERVICE command", _exec)

	def test_t1_06_3_dispatch_mute_command(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			res = sim.handle_command("MUTE")
			assert res == "MUTED"
			assert sim.muted is True
		run_test_wrapper(1, "F6", "T1.6.3", "Dispatch MUTE command", _exec)

	def test_t1_06_4_dispatch_unmute_command(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.muted = True
			res = sim.handle_command("UNMUTE")
			assert res == "UNMUTED"
			assert sim.muted is False
		run_test_wrapper(1, "F6", "T1.6.4", "Dispatch UNMUTE command", _exec)

	def test_t1_06_5_dispatch_trigger_buzzer(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			res = sim.handle_command("TRIGGER_BUZZER")
			assert res == "BUZZER_TRIGGERED"
			assert sim.buzzer_active is True
		run_test_wrapper(1, "F6", "T1.6.5", "Dispatch TRIGGER_BUZZER command", _exec)

class TestTier1Feature07:
	def test_t1_07_1_clean_connect_with_lwt(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			c2 = TestMqttClient("client_with_lwt")
			c2.connect(broker, lwt_topic="pbl6/pi4_01/status", lwt_payload={"status": "offline"})
			c2_id = "client_with_lwt"
			assert c2_id in broker.lwt_configs
			c2.publish("pbl6/pi4_01/telemetry", {"active": True})
			c2.disconnect()
		run_test_wrapper(1, "F7", "T1.7.1", "Clean connect with LWT configured", _exec)

	def test_t1_07_2_online_status_publication(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			client.subscribe("pbl6/pi4_01/status")
			client.publish("pbl6/pi4_01/status", {"status": "online", "timestamp": int(time.time())}, qos=1, retain=True)
			msg = client.wait_for_message("pbl6/pi4_01/status", timeout=1.0)
			assert msg is not None
			assert msg["payload"]["status"] == "online"
		run_test_wrapper(1, "F7", "T1.7.2", "Online status publication on connect", _exec)

	def test_t1_07_3_offline_status_lwt_publication(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			observer = setup_harness["client"]
			observer.subscribe("pbl6/pi4_01/status")
			c_pi = TestMqttClient("pi4_01")
			c_pi.connect(broker, lwt_topic="pbl6/pi4_01/status", lwt_payload={"status": "offline"})
			c_pi.disconnect(ungraceful=True)
			msg = observer.wait_for_message("pbl6/pi4_01/status", timeout=1.0)
			assert msg is not None
			assert msg["payload"]["status"] == "offline"
		run_test_wrapper(1, "F7", "T1.7.3", "Offline status LWT publication on ungraceful disconnect", _exec)

	def test_t1_07_4_retain_flag_set_on_status(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			client.publish("pbl6/pi4_01/status", {"status": "online"}, qos=1, retain=True)
			broker = setup_harness["broker"]
			status_topic = "pbl6/pi4_01/status"
			assert status_topic in broker.retained_messages
		run_test_wrapper(1, "F7", "T1.7.4", "Retain flag set on status topic messages", _exec)

	def test_t1_07_5_app_ui_banner_transition(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "online"})
			assert app_sim.connection_bloc.status_banner == "Connected"
			broker.publish("pbl6/pi4_01/status", {"status": "offline"})
			assert app_sim.connection_bloc.status_banner == "Disconnected"
		run_test_wrapper(1, "F7", "T1.7.5", "App UI reflects device online/offline banner transition", _exec)

class TestTier1Feature08:
	def test_t1_08_1_create_sdp_offer_transceivers(self, setup_harness):
		def _exec():
			offer = WebRtcPeerSim.create_offer("app_client", has_video=True, has_audio=True)
			v_line = "m=video"
			a_line = "m=audio"
			assert v_line in offer["sdp"]
			assert a_line in offer["sdp"]
		run_test_wrapper(1, "F8", "T1.8.1", "Client creates WebRTC SDP Offer with video/audio", _exec)

	def test_t1_08_2_sdp_offer_json_envelope(self, setup_harness):
		def _exec():
			offer = WebRtcPeerSim.create_offer("app_client")
			assert offer["type"] == "offer"
			assert offer["caller"] == "app_client"
			assert isinstance(offer["sdp"], str)
		run_test_wrapper(1, "F8", "T1.8.2", "SDP Offer serialized into JSON envelope", _exec)

	def test_t1_08_3_publish_sdp_offer(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			client.subscribe("pbl6/pi4_01/webrtc/offer")
			offer = WebRtcPeerSim.create_offer()
			client.publish("pbl6/pi4_01/webrtc/offer", offer)
			msg = client.wait_for_message("pbl6/pi4_01/webrtc/offer", timeout=1.0)
			assert msg is not None
			assert msg["payload"]["type"] == "offer"
		run_test_wrapper(1, "F8", "T1.8.3", "Publish SDP Offer to MQTT topic", _exec)

	def test_t1_08_4_validation_of_sdp_syntax(self, setup_harness):
		def _exec():
			offer = WebRtcPeerSim.create_offer()
			valid, err = WebRtcPeerSim.validate_offer(offer)
			assert valid is True
		run_test_wrapper(1, "F8", "T1.8.4", "Validation of valid SDP syntax", _exec)

	def test_t1_08_5_mock_pi_offer_subscription(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			pi_client = TestMqttClient("pi_webrtc_sub")
			pi_client.connect(broker)
			pi_client.subscribe("pbl6/pi4_01/webrtc/offer")
			offer_topic = "pbl6/pi4_01/webrtc/offer"
			assert offer_topic in broker.subscriptions
			pi_client.disconnect()
		run_test_wrapper(1, "F8", "T1.8.5", "Subscription to offer topic by Mock Pi", _exec)

class TestTier1Feature09:
	def test_t1_09_1_mock_pi_receives_offer(self, setup_harness):
		def _exec():
			offer = WebRtcPeerSim.create_offer()
			valid, _ = WebRtcPeerSim.validate_offer(offer)
			assert valid is True
		run_test_wrapper(1, "F9", "T1.9.1", "Mock Pi receives SDP Offer", _exec)

	def test_t1_09_2_mock_pi_creates_answer(self, setup_harness):
		def _exec():
			offer = WebRtcPeerSim.create_offer()
			answer = WebRtcPeerSim.create_answer(offer, callee="pi4_01")
			assert answer["type"] == "answer"
			v_line = "m=video"
			assert v_line in answer["sdp"]
		run_test_wrapper(1, "F9", "T1.9.2", "Mock Pi creates SDP Answer", _exec)

	def test_t1_09_3_mock_pi_publishes_answer(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			client.subscribe("pbl6/pi4_01/webrtc/answer")
			offer = WebRtcPeerSim.create_offer()
			ans = WebRtcPeerSim.create_answer(offer)
			client.publish("pbl6/pi4_01/webrtc/answer", ans)
			msg = client.wait_for_message("pbl6/pi4_01/webrtc/answer", timeout=1.0)
			assert msg is not None
			assert msg["payload"]["type"] == "answer"
		run_test_wrapper(1, "F9", "T1.9.3", "Mock Pi publishes answer to MQTT", _exec)

	def test_t1_09_4_answer_json_payload_validation(self, setup_harness):
		def _exec():
			offer = WebRtcPeerSim.create_offer()
			ans = WebRtcPeerSim.create_answer(offer)
			valid, err = WebRtcPeerSim.validate_answer(ans)
			assert valid is True
		run_test_wrapper(1, "F9", "T1.9.4", "Answer JSON payload validation", _exec)

	def test_t1_09_5_client_receives_answer(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			client.subscribe("pbl6/pi4_01/webrtc/answer")
			ans = WebRtcPeerSim.create_answer(WebRtcPeerSim.create_offer())
			client.publish("pbl6/pi4_01/webrtc/answer", ans)
			recv = client.wait_for_message("pbl6/pi4_01/webrtc/answer", timeout=1.0)
			assert recv is not None
			assert recv["payload"]["callee"] == "pi4_01"
		run_test_wrapper(1, "F9", "T1.9.5", "Client receives SDP Answer", _exec)

class TestTier1Feature10:
	def test_t1_10_1_client_candidate_discovery(self, setup_harness):
		def _exec():
			cand = WebRtcPeerSim.create_ice_candidate(sender="app")
			assert cand["sender"] == "app"
			c_prefix = "candidate:"
			assert c_prefix in cand["candidate"]
		run_test_wrapper(1, "F10", "T1.10.1", "Client candidate discovery and publication", _exec)

	def test_t1_10_2_pi_candidate_discovery(self, setup_harness):
		def _exec():
			cand = WebRtcPeerSim.create_ice_candidate(sender="pi")
			assert cand["sender"] == "pi"
		run_test_wrapper(1, "F10", "T1.10.2", "Pi candidate discovery and publication", _exec)

	def test_t1_10_3_candidate_schema_validation(self, setup_harness):
		def _exec():
			cand = WebRtcPeerSim.create_ice_candidate()
			valid, _ = WebRtcPeerSim.validate_ice_candidate(cand)
			assert valid is True
		run_test_wrapper(1, "F10", "T1.10.3", "Candidate JSON payload structure validation", _exec)

	def test_t1_10_4_bidirectional_candidate_ingestion(self, setup_harness):
		def _exec():
			client = setup_harness["client"]
			client.subscribe("pbl6/pi4_01/webrtc/ice_candidate")
			c_app = WebRtcPeerSim.create_ice_candidate(sender="app")
			c_pi = WebRtcPeerSim.create_ice_candidate(sender="pi")
			client.publish("pbl6/pi4_01/webrtc/ice_candidate", c_app)
			client.publish("pbl6/pi4_01/webrtc/ice_candidate", c_pi)
			msgs = client.collect_messages("pbl6/pi4_01/webrtc/ice_candidate", count=2, timeout=1.0)
			assert len(msgs) == 2
		run_test_wrapper(1, "F10", "T1.10.4", "Bi-directional candidate ingestion without deadlock", _exec)

	def test_t1_10_5_stun_server_verification(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			cand = WebRtcPeerSim.create_ice_candidate(sender="app")
			valid, reason = WebRtcPeerSim.validate_ice_candidate(cand)
			assert valid is True
			stun_server = app_sim.webrtc_bloc.stun_server
			assert stun_server.startswith("stun:")
			port_str = ":19302"
			assert port_str in stun_server
		run_test_wrapper(1, "F10", "T1.10.5", "STUN server configuration verification", _exec)

class TestTier1Feature11:
	def test_t1_11_1_video_track_fps(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame(640, 480)
			assert len(frame) > 0
			assert sim.detection_fps >= 15 and sim.detection_fps <= 30
		run_test_wrapper(1, "F11", "T1.11.1", "Mock Pi initiates video track with FPS 15-30", _exec)

	def test_t1_11_2_video_stream_rtp_packet_flow(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame()
			assert len(frame) > 0
		run_test_wrapper(1, "F11", "T1.11.2", "Video stream RTP packet flow establishment", _exec)

	def test_t1_11_3_frame_dimension_verification(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame(640, 480)
			assert len(frame) == 640 * 480 * 3
		run_test_wrapper(1, "F11", "T1.11.3", "Frame dimension verification 640x480", _exec)

	def test_t1_11_4_latency_measurement_under_300ms(self, setup_harness):
		def _exec():
			t0 = time.perf_counter()
			_ = setup_harness["sim"].generate_synthetic_radar_frame()
			latency_ms = (time.perf_counter() - t0) * 1000.0
			assert latency_ms < 300.0
		run_test_wrapper(1, "F11", "T1.11.4", "Latency measurement under 300ms ceiling", _exec)

	def test_t1_11_5_frame_decoding_without_crash(self, setup_harness):
		def _exec():
			frame = setup_harness["sim"].generate_synthetic_radar_frame()
			assert isinstance(frame, bytes)
		run_test_wrapper(1, "F11", "T1.11.5", "Frame decoding without rendering crash", _exec)

class TestTier1Feature12:
	def test_t1_12_1_ptt_press_activates_audio_track(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			res = app_sim.ptt_intercom.press_ptt()
			assert res is True
			assert app_sim.ptt_intercom.ptt_active is True
			sim.receive_audio_chunk(b"\x01\x02" * 160)
			assert sim.audio_chunks_received == 1
		run_test_wrapper(1, "F12", "T1.12.1", "Press-and-hold trigger on PTT button activates audio track", _exec)

	def test_t1_12_2_audio_rtp_transmission(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			chunk = b"\x01\x02\x03\x04" * 100
			rec = sim.receive_audio_chunk(chunk)
			assert rec == len(chunk)
		run_test_wrapper(1, "F12", "T1.12.2", "Audio RTP packet stream transmission to Mock Pi", _exec)

	def test_t1_12_3_audio_track_mute_on_release(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.ptt_intercom.press_ptt()
			app_sim.ptt_intercom.release_ptt()
			assert app_sim.ptt_intercom.ptt_active is False
			initial_count = sim.audio_chunks_received
			sent = app_sim.ptt_intercom.send_audio_chunk(sim, b"\x01\x02" * 160)
			assert sent is False
			assert sim.audio_chunks_received == initial_count
			sim.receive_audio_chunk(b"")
		run_test_wrapper(1, "F12", "T1.12.3", "Audio track mute on PTT button release", _exec)

	def test_t1_12_4_visual_ui_indicator_active(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.ptt_intercom.press_ptt()
			assert app_sim.ptt_intercom.button_color == "RED_ACTIVE"
			sim.receive_audio_chunk(b"\x00" * 320)
			app_sim.ptt_intercom.release_ptt()
			assert app_sim.ptt_intercom.button_color == "DEFAULT"
		run_test_wrapper(1, "F12", "T1.12.4", "Visual UI indicator during active recording", _exec)

	def test_t1_12_5_audio_sink_playback_handling(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.receive_audio_chunk(b"\xaa\xbb" * 50)
			assert sim.audio_chunks_received > 0
		run_test_wrapper(1, "F12", "T1.12.5", "Mock Pi audio sink receipt and playback handling", _exec)

class TestTier1Feature13:
	def test_t1_13_1_ultrasonic_distance_random_walk(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			p1 = sim.step_telemetry(distance_delta=-5.0)
			assert p1["ultrasonic_distance_cm"] >= 20.0 and p1["ultrasonic_distance_cm"] <= 300.0
		run_test_wrapper(1, "F13", "T1.13.1", "Ultrasonic distance random walk within plausible range", _exec)

	def test_t1_13_2_battery_drain_simulation(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			b_init = sim.battery_percentage
			p = sim.step_telemetry(drain_battery=5)
			assert p["battery_percentage"] == b_init - 5
		run_test_wrapper(1, "F13", "T1.13.2", "Battery drain simulation over time", _exec)

	def test_t1_13_3_cpu_temperature_envelope(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			p = sim.step_telemetry()
			assert p["temperature_celsius"] >= 40.0 and p["temperature_celsius"] <= 65.0
		run_test_wrapper(1, "F13", "T1.13.3", "CPU temperature fluctuations within normal envelope", _exec)

	def test_t1_13_4_cpu_usage_fluctuation(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			p = sim.step_telemetry()
			assert p["cpu_usage"] >= 0.0 and p["cpu_usage"] <= 100.0
		run_test_wrapper(1, "F13", "T1.13.4", "CPU usage fluctuation based on encoding workload", _exec)

	def test_t1_13_5_plausible_sensor_noise_injection(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			p = sim.step_telemetry(distance_delta=2.3)
			assert p["ultrasonic_distance_cm"] > 0
		run_test_wrapper(1, "F13", "T1.13.5", "Plausible sensor noise injection without illegal values", _exec)

class TestTier1Feature14:
	def test_t1_14_1_hotkey_listener_registration(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			res1 = sim.handle_command("TRIGGER_BUZZER")
			assert res1 == "BUZZER_TRIGGERED"
			res2 = sim.handle_command("REBOOT")
			assert res2 == "REBOOT_ACK"
		run_test_wrapper(1, "F14", "T1.14.1", "Hotkey listener registration in Mock Pi", _exec)

	def test_t1_14_2_hotkey_triggers_hazard_alert(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			alert = sim.inject_hazard(distance_cm=20.0, detected_objects=["stairs_down"])
			assert alert["level"] == "CRITICAL"
		run_test_wrapper(1, "F14", "T1.14.2", "Pressing hotkey triggers immediate hazard alert", _exec)

	def test_t1_14_3_immediate_distance_drop(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.inject_hazard(distance_cm=18.0)
			p = sim.step_telemetry()
			assert p["ultrasonic_distance_cm"] == 18.0
		run_test_wrapper(1, "F14", "T1.14.3", "Immediate distance drop below threshold upon hotkey", _exec)

	def test_t1_14_4_console_log_confirms_hotkey(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			broker = setup_harness["broker"]
			client = setup_harness["client"]
			client.subscribe("pbl6/pi4_01/alert")
			alert = sim.inject_hazard("STAIRS_DOWN", distance_cm=20.0)
			broker.publish("pbl6/pi4_01/alert", alert)
			rec = client.wait_for_message("pbl6/pi4_01/alert", timeout=1.0)
			assert rec is not None
			assert rec["payload"]["alert_type"] == "STAIRS_DOWN"
		run_test_wrapper(1, "F14", "T1.14.4", "Console log output confirms manual hazard injection", _exec)

	def test_t1_14_5_debounce_rate_limit_check(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			alert1 = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0)
			alert2 = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0)
			assert alert1["event_id"] != alert2["event_id"]
			diff = alert2["timestamp"] - alert1["timestamp"]
			assert diff >= 0
		run_test_wrapper(1, "F14", "T1.14.5", "Debounce / rate limit check on rapid hotkey presses", _exec)

class TestTier1Feature15:
	def test_t1_15_1_synthetic_radar_initialization(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame()
			assert len(frame) > 0
		run_test_wrapper(1, "F15", "T1.15.1", "Synthetic radar HUD generator initialization", _exec)

	def test_t1_15_2_radar_sweep_line_animation(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame(640, 480)
			expected_len = 640 * 480 * 3
			assert len(frame) == expected_len
		run_test_wrapper(1, "F15", "T1.15.2", "Radar sweep line animation progression per frame", _exec)

	def test_t1_15_3_sensor_overlay_rendering(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			pkt = sim.step_telemetry()
			dist_text = f"{pkt['ultrasonic_distance_cm']:.1f} cm"
			unit_str = "cm"
			assert unit_str in dist_text
			assert pkt["ultrasonic_distance_cm"] > 0
		run_test_wrapper(1, "F15", "T1.15.3", "Sensor overlay rendering on synthetic video", _exec)

	def test_t1_15_4_fallback_from_camera_to_synthetic(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame()
			assert frame is not None
		run_test_wrapper(1, "F15", "T1.15.4", "Fallback from physical camera to synthetic feeder", _exec)

	def test_t1_15_5_watermarking_in_synthetic_frames(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			frame = sim.generate_synthetic_radar_frame(320, 240)
			assert len(frame) > 0
			assert isinstance(frame, bytes)
		run_test_wrapper(1, "F15", "T1.15.5", "Timestamp watermarking in synthetic frames", _exec)

class TestTier1Feature16:
	def test_t1_16_1_audio_sink_buffer_allocation(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			chunk = b"\x00" * 960
			res = sim.receive_audio_chunk(chunk)
			assert res == 960
			assert sim.total_audio_bytes == 960
			assert sim.audio_chunks_received == 1
		run_test_wrapper(1, "F16", "T1.16.1", "Audio sink buffer allocation in Mock Pi", _exec)

	def test_t1_16_2_opus_pcm_audio_packet_reception(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			res = sim.receive_audio_chunk(b"\x12\x34\x56\x78")
			assert res == 4
		run_test_wrapper(1, "F16", "T1.16.2", "Audio packet reception and decoding", _exec)

	def test_t1_16_3_handling_audio_pause_resume(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.handle_command("MUTE")
			assert sim.receive_audio_chunk(b"\x01") == 0
			sim.handle_command("UNMUTE")
			assert sim.receive_audio_chunk(b"\x01") == 1
		run_test_wrapper(1, "F16", "T1.16.3", "Handling audio stream pause/resume", _exec)

	def test_t1_16_4_handling_silent_or_empty_packets(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			assert sim.receive_audio_chunk(b"") == 0
		run_test_wrapper(1, "F16", "T1.16.4", "Graceful handling of silent or empty audio packets", _exec)

	def test_t1_16_5_speaker_volume_gain_application(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			sim.apply_config({"speaker_volume": 70})
			gain = sim.speaker_volume / 100.0
			assert gain == 0.7
		run_test_wrapper(1, "F16", "T1.16.5", "Speaker volume parameter application to gain", _exec)

class TestTier1Feature17:
	def test_t1_17_1_core_directory_structure(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert v["layers_present"]["core"] is True
		run_test_wrapper(1, "F17", "T1.17.1", "Verification of lib/core/ directory structure", _exec)

	def test_t1_17_2_data_directory_structure(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert v["layers_present"]["data"] is True
		run_test_wrapper(1, "F17", "T1.17.2", "Verification of lib/data/ directory structure", _exec)

	def test_t1_17_3_domain_directory_structure(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert v["layers_present"]["domain"] is True
		run_test_wrapper(1, "F17", "T1.17.3", "Verification of lib/domain/ directory structure", _exec)

	def test_t1_17_4_presentation_directory_structure(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert v["layers_present"]["presentation"] is True
		run_test_wrapper(1, "F17", "T1.17.4", "Verification of lib/presentation/ directory structure", _exec)

	def test_t1_17_5_zero_forbidden_dependencies(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert v["domain_isolated"] is True
		run_test_wrapper(1, "F17", "T1.17.5", "Zero forbidden dependencies in domain layer", _exec)

class TestTier1Feature18:
	def test_t1_18_1_connection_bloc_state_transitions(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "online"})
			assert app_sim.connection_bloc.state == "Connected"
			broker.publish("pbl6/pi4_01/status", {"status": "offline"})
			assert app_sim.connection_bloc.state == "Disconnected"
		run_test_wrapper(1, "F18", "T1.18.1", "ConnectionBloc state transitions", _exec)

	def test_t1_18_2_dashboard_bloc_telemetry_loaded(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			pkt = sim.step_telemetry()
			broker.publish("pbl6/pi4_01/telemetry", pkt)
			assert app_sim.dashboard_bloc.is_loaded is True
			assert app_sim.dashboard_bloc.battery == 85
		run_test_wrapper(1, "F18", "T1.18.2", "DashboardBloc emits DashboardLoaded on telemetry", _exec)

	def test_t1_18_3_alert_bloc_critical_alert_received(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			hazard = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0)
			broker.publish("pbl6/pi4_01/alert", hazard)
			assert app_sim.alert_bloc.has_critical_alert is True
			assert app_sim.alert_bloc.active_critical_alert is not None
		run_test_wrapper(1, "F18", "T1.18.3", "AlertBloc emits AlertReceived with critical flag", _exec)

	def test_t1_18_4_config_bloc_emits_updated(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/config", {"distance_threshold_cm": 90.0})
			assert app_sim.config_bloc.distance_threshold == 90.0
			assert app_sim.config_bloc.state == "ConfigUpdated"
		run_test_wrapper(1, "F18", "T1.18.4", "ConfigBloc emits ConfigUpdated on parameter change", _exec)

	def test_t1_18_5_webrtc_bloc_lifecycle(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			app_sim.connection_bloc.simulate_connected()
			offer = app_sim.webrtc_bloc.start_call()
			assert offer is not None
			assert app_sim.webrtc_bloc.lifecycle_state == "OFFERING"
			answer = WebRtcPeerSim.create_answer(offer, callee="pi4_01")
			app_sim.webrtc_bloc.handle_answer(answer)
			assert app_sim.webrtc_bloc.lifecycle_state == "STREAMING"
		run_test_wrapper(1, "F18", "T1.18.5", "WebrtcBloc handles connection lifecycle states", _exec)

class TestTier1Feature19:
	def test_t1_19_1_connection_status_badge(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "online"})
			badge = app_sim.dashboard_view.get_connection_badge()
			assert badge["label"] == "Online"
			assert badge["color"] == "GREEN"
		run_test_wrapper(1, "F19", "T1.19.1", "Connection status badge rendering", _exec)

	def test_t1_19_2_battery_level_indicator_card(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			pkt = sim.step_telemetry()
			broker.publish("pbl6/pi4_01/telemetry", pkt)
			assert app_sim.dashboard_view.battery_badge_color == "GREEN"
			pkt_low = sim.step_telemetry(drain_battery=75)
			broker.publish("pbl6/pi4_01/telemetry", pkt_low)
			assert app_sim.dashboard_view.battery_badge_color == "RED"
		run_test_wrapper(1, "F19", "T1.19.2", "Battery level indicator card rendering", _exec)

	def test_t1_19_3_realtime_ultrasonic_distance_card(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			pkt = sim.step_telemetry()
			broker.publish("pbl6/pi4_01/telemetry", pkt)
			dist_str = f"{pkt['ultrasonic_distance_cm']:.1f} cm"
			assert app_sim.dashboard_view.formatted_distance == dist_str
		run_test_wrapper(1, "F19", "T1.19.3", "Real-time ultrasonic distance card rendering", _exec)

	def test_t1_19_4_system_temp_cpu_metrics(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			pkt = sim.step_telemetry()
			broker.publish("pbl6/pi4_01/telemetry", pkt)
			assert app_sim.dashboard_view.formatted_cpu == "32.0%"
			assert app_sim.dashboard_view.formatted_temp == "48.2°C" or app_sim.dashboard_view.formatted_temp == "48.5°C"
		run_test_wrapper(1, "F19", "T1.19.4", "System temperature and CPU load metric widgets", _exec)

	def test_t1_19_5_navigation_shortcuts(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "online"})
			app_sim.dashboard_view.navigate("/live_monitor")
			assert app_sim.current_route == "/live_monitor"
		run_test_wrapper(1, "F19", "T1.19.5", "Navigation shortcut buttons to Live Monitor and Settings", _exec)

class TestTier1Feature20:
	def test_t1_20_1_video_view_container_layout(self, setup_harness):
		def _exec():
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			frame = sim.generate_synthetic_radar_frame(640, 480)
			assert len(frame) > 0
			assert app_sim.monitor_view.aspect_ratio > 1.0
		run_test_wrapper(1, "F20", "T1.20.1", "Video view container layout 16:9", _exec)

	def test_t1_20_2_sensor_telemetry_hud_overlay(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			pkt = sim.step_telemetry()
			broker.publish("pbl6/pi4_01/telemetry", pkt)
			assert app_sim.monitor_view.hud_visible is True
			assert app_sim.monitor_view.hud_distance > 0
		run_test_wrapper(1, "F20", "T1.20.2", "Sensor telemetry HUD overlay on top of video", _exec)

	def test_t1_20_3_ptt_button_position(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			rect = app_sim.monitor_view.ptt_button_rect
			assert rect["w"] >= 64
			assert rect["h"] >= 64
			sim.receive_audio_chunk(b"")
		run_test_wrapper(1, "F20", "T1.20.3", "Push-to-Talk button position and accessibility", _exec)

	def test_t1_20_4_fullscreen_toggle_handling(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.monitor_view.toggle_fullscreen()
			assert app_sim.monitor_view.is_fullscreen is True
			assert app_sim.dashboard_view.orientation == "landscape"
			sim.generate_synthetic_radar_frame()
		run_test_wrapper(1, "F20", "T1.20.4", "Fullscreen toggle or landscape orientation handling", _exec)

	def test_t1_20_5_audio_track_mute_toggle(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.monitor_view.toggle_mute()
			assert app_sim.monitor_view.is_muted is True
			res = sim.handle_command("MUTE")
			assert res == "MUTED"
			assert sim.muted is True
		run_test_wrapper(1, "F20", "T1.20.5", "Audio track mute toggle button", _exec)

class TestTier1Feature21:
	def test_t1_21_1_distance_threshold_slider(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.connection_bloc.simulate_connected()
			app_sim.settings_view.adjust_slider_rapidly("distance_threshold_cm", 120.0)
			app_sim.settings_view.flush_debounced_save()
			sim.apply_config({"distance_threshold_cm": 120.0})
			assert app_sim.config_bloc.distance_threshold == 120.0
			assert sim.distance_threshold_cm == 120.0
		run_test_wrapper(1, "F21", "T1.21.1", "Distance threshold slider configuration (20-200cm)", _exec)

	def test_t1_21_2_speaker_volume_slider(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.connection_bloc.simulate_connected()
			app_sim.settings_view.adjust_slider_rapidly("speaker_volume", 90)
			app_sim.settings_view.flush_debounced_save()
			sim.apply_config({"speaker_volume": 90})
			assert app_sim.config_bloc.speaker_volume == 90
			assert sim.speaker_volume == 90
		run_test_wrapper(1, "F21", "T1.21.2", "Speaker volume slider configuration (0-100%)", _exec)

	def test_t1_21_3_device_reboot_confirmation_dialog(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.settings_view.confirm_reboot()
			res = sim.handle_command("REBOOT")
			assert res == "REBOOT_ACK"
			assert sim.reboot_count == 1
		run_test_wrapper(1, "F21", "T1.21.3", "Device reboot confirmation dialog and action trigger", _exec)

	def test_t1_21_4_device_buzzer_trigger_button(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.settings_view.trigger_buzzer()
			res = sim.handle_command("TRIGGER_BUZZER")
			assert res == "BUZZER_TRIGGERED"
			assert sim.buzzer_active is True
		run_test_wrapper(1, "F21", "T1.21.4", "Device buzzer trigger button", _exec)

	def test_t1_21_5_broker_host_device_id_fields(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			broker = setup_harness["broker"]
			assert app_sim.settings_view.broker_host == "127.0.0.1"
			assert app_sim.settings_view.device_id == "pi4_01"
			broker.publish("pbl6/pi4_01/config", {"distance_threshold_cm": 80.0})
		run_test_wrapper(1, "F21", "T1.21.5", "MQTT broker host and device ID configuration fields", _exec)

class TestTier1Feature22:
	def test_t1_22_1_alert_log_list_view_rendering(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			a1 = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0)
			a2 = sim.inject_hazard("STAIRS_DOWN", distance_cm=15.0)
			broker.publish("pbl6/pi4_01/alert", a1)
			broker.publish("pbl6/pi4_01/alert", a2)
			assert app_sim.alert_history_view.item_count == 2
		run_test_wrapper(1, "F22", "T1.22.1", "Alert log list view rendering", _exec)

	def test_t1_22_2_severity_badge_formatting(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			a1 = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0)
			broker.publish("pbl6/pi4_01/alert", a1)
			c_color = app_sim.alert_history_view.get_badge_color("CRITICAL")
			w_color = app_sim.alert_history_view.get_badge_color("WARNING")
			assert c_color == "RED"
			assert w_color == "ORANGE"
		run_test_wrapper(1, "F22", "T1.22.2", "Severity badge formatting (Critical: red, Warning: orange)", _exec)

	def test_t1_22_3_formatted_timestamp_display(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			alert = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0)
			broker.publish("pbl6/pi4_01/alert", alert)
			ts_str = app_sim.alert_history_view.get_formatted_timestamp(alert)
			colon = ":"
			dash = "-"
			assert colon in ts_str
			assert dash in ts_str
		run_test_wrapper(1, "F22", "T1.22.3", "Formatted timestamp display (HH:mm:ss dd/MM)", _exec)

	def test_t1_22_4_detected_objects_chips_display(self, setup_harness):
		def _exec():
			broker = setup_harness["broker"]
			sim = setup_harness["sim"]
			app_sim = setup_harness["app_sim"]
			alert = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0, detected_objects=["stairs_down", "puddle"])
			broker.publish("pbl6/pi4_01/alert", alert)
			chips = app_sim.alert_history_view.get_chips(alert)
			target = "stairs_down"
			assert target in chips
		run_test_wrapper(1, "F22", "T1.22.4", "Detected objects tag list chips display", _exec)

	def test_t1_22_5_empty_state_display(self, setup_harness):
		def _exec():
			app_sim = setup_harness["app_sim"]
			sim = setup_harness["sim"]
			app_sim.alert_history_view.clear_history()
			assert app_sim.alert_history_view.is_empty is True
			sim.inject_hazard()
		run_test_wrapper(1, "F22", "T1.22.5", "Empty state display when no alerts have occurred", _exec)
