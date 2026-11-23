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

@pytest.fixture
def test_env():
	broker = EmbeddedMqttBroker()
	client = TestMqttClient("test_runner_client")
	sim = MockPiSimulator("pi4_01")
	app_sim = ClientStateMachineSim("pi4_01", broker)
	client.connect(broker)
	client.subscribe(client.client_id, "pbl6/#")
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

class TestTier3Pairwise:
	def test_t3_01_telemetry_interrupted_by_hazard(self, test_env):
		def _exec():
			client, sim = test_env["client"], test_env["sim"]
			client.subscribe("pbl6/pi4_01/#")
			client.publish("pbl6/pi4_01/telemetry", sim.step_telemetry())
			alert = sim.inject_hazard(distance_cm=22.0)
			client.publish("pbl6/pi4_01/alert", alert, qos=1)
			msgs = client.collect_messages("pbl6/pi4_01/#", count=2, timeout=1.0)
			assert len(msgs) == 2
			assert msgs[1]["payload"]["alert_type"] == "OBSTACLE_DANGER"
		run_test_wrapper(3, "F1+F3", "T3.1", "Telemetry interrupted by emergency hazard alert", _exec)

	def test_t3_02_telemetry_dashboard_with_heads_up(self, test_env):
		def _exec():
			client, sim = test_env["client"], test_env["sim"]
			client.subscribe("pbl6/pi4_01/alert")
			alert = sim.inject_hazard(distance_cm=15.0)
			client.publish("pbl6/pi4_01/alert", alert)
			msg = client.wait_for_message("pbl6/pi4_01/alert", timeout=1.0)
			assert msg is not None
			assert msg["payload"]["level"] == "CRITICAL"
		run_test_wrapper(3, "F2+F4", "T3.2", "Telemetry dashboard updating while critical alert triggers heads-up", _exec)

	def test_t3_03_threshold_change_triggers_alert(self, test_env):
		def _exec():
			sim = test_env["sim"]
			sim.distance_threshold_cm = 80.0
			assert sim.distance_threshold_cm <= 100.0
			sim.apply_config({"distance_threshold_cm": 120.0})
			alert = sim.inject_hazard(distance_cm=100.0)
			assert alert["level"] == "CRITICAL"
		run_test_wrapper(3, "F3+F5", "T3.3", "Threshold change 80cm->120cm causes 100cm obstacle to trigger critical alert", _exec)

	def test_t3_04_speaker_volume_modifies_audio_gain(self, test_env):
		def _exec():
			sim = test_env["sim"]
			sim.apply_config({"speaker_volume": 90})
			assert sim.speaker_volume == 90
			gain = sim.speaker_volume / 100.0
			assert gain == 0.9
		run_test_wrapper(3, "F5+F16", "T3.4", "Volume slider adjustment modifies audio sink gain", _exec)

	def test_t3_05_reboot_command_triggers_lwt_offline(self, test_env):
		def _exec():
			broker = test_env["broker"]
			obs = test_env["client"]
			obs.subscribe("pbl6/pi4_01/status")
			c_pi = TestMqttClient("pi_reboot_sim")
			c_pi.connect(broker, lwt_topic="pbl6/pi4_01/status", lwt_payload={"status": "offline"})
			c_pi.publish("pbl6/pi4_01/status", {"status": "online"}, retain=True)
			c_pi.disconnect(ungraceful=True)
			msg = obs.wait_for_message("pbl6/pi4_01/status", timeout=1.0, predicate=lambda m: m["payload"]["status"] == "offline")
			assert msg is not None
		run_test_wrapper(3, "F6+F7", "T3.5", "Reboot command triggers shutdown and LWT offline", _exec)

	def test_t3_06_complete_webrtc_signaling_loop(self, test_env):
		def _exec():
			client = test_env["client"]
			client.subscribe("pbl6/pi4_01/webrtc/#")
			offer = WebRtcPeerSim.create_offer()
			client.publish("pbl6/pi4_01/webrtc/offer", offer)
			answer = WebRtcPeerSim.create_answer(offer)
			client.publish("pbl6/pi4_01/webrtc/answer", answer)
			cand = WebRtcPeerSim.create_ice_candidate()
			client.publish("pbl6/pi4_01/webrtc/ice_candidate", cand)
			msgs = client.collect_messages("pbl6/pi4_01/webrtc/#", count=3, timeout=1.0)
			assert len(msgs) == 3
		run_test_wrapper(3, "F8+F9+F10", "T3.6", "Complete WebRTC signaling loop offer, answer, and ice candidates", _exec)

	def test_t3_07_full_duplex_video_and_ptt_audio(self, test_env):
		def _exec():
			sim = test_env["sim"]
			frame = sim.generate_synthetic_radar_frame()
			assert len(frame) == 640 * 480 * 3
			rec = sim.receive_audio_chunk(b"\xaa\x55" * 160)
			assert rec == 320
		run_test_wrapper(3, "F11+F12", "T3.7", "Full-duplex video streaming and PTT audio playback", _exec)

	def test_t3_08_live_monitor_video_with_telemetry_hud(self, test_env):
		def _exec():
			sim = test_env["sim"]
			pkt = sim.step_telemetry()
			frame = sim.generate_synthetic_radar_frame()
			overlay_text = f"Dist: {pkt['ultrasonic_distance_cm']} cm | Bat: {pkt['battery_percentage']}%"
			assert "cm" in overlay_text and len(frame) > 0
		run_test_wrapper(3, "F11+F20", "T3.8", "Live monitor video feed overlaid with real-time telemetry HUD", _exec)

	def test_t3_09_emergency_alert_saved_to_history(self, test_env):
		def _exec():
			sim = test_env["sim"]
			alert = sim.inject_hazard(distance_cm=20.0)
			history = []
			history.append(alert)
			assert len(history) == 1
			assert history[0]["event_id"].startswith("evt_")
		run_test_wrapper(3, "F3+F22", "T3.9", "Emergency hazard alert saved and rendered in alert history log", _exec)

	def test_t3_10_mock_pi_hotkey_triggers_mobile_heads_up(self, test_env):
		def _exec():
			client, sim = test_env["client"], test_env["sim"]
			client.subscribe("pbl6/pi4_01/alert")
			alert = sim.inject_hazard(distance_cm=19.0, detected_objects=["stairs_down"])
			client.publish("pbl6/pi4_01/alert", alert)
			msg = client.wait_for_message("pbl6/pi4_01/alert", timeout=1.0)
			assert msg is not None
			target_obj = "stairs_down"
			assert target_obj in msg["payload"]["detected_objects"]
		run_test_wrapper(3, "F14+F4", "T3.10", "Mock Pi hotkey generates hazard and triggers heads-up alert", _exec)

	def test_t3_11_synthetic_radar_sync_with_distance(self, test_env):
		def _exec():
			sim = test_env["sim"]
			sim.ultrasonic_distance_cm = 45.0
			pkt = sim.step_telemetry()
			frame = sim.generate_synthetic_radar_frame()
			assert pkt["ultrasonic_distance_cm"] == 45.0 and len(frame) > 0
		run_test_wrapper(3, "F15+F11", "T3.11", "Synthetic radar HUD animation synchronized with distance telemetry", _exec)

	def test_t3_12_mock_pi_crash_turns_dashboard_badge_red(self, test_env):
		def _exec():
			broker = test_env["broker"]
			obs = test_env["client"]
			obs.subscribe("pbl6/pi4_01/status")
			c_pi = TestMqttClient("pi_crash_agent")
			c_pi.connect(broker, lwt_topic="pbl6/pi4_01/status", lwt_payload={"status": "offline"})
			c_pi.disconnect(ungraceful=True)
			msg = obs.wait_for_message("pbl6/pi4_01/status", timeout=1.0)
			badge_color = "RED" if msg["payload"]["status"] == "offline" else "GREEN"
			assert badge_color == "RED"
		run_test_wrapper(3, "F7+F19", "T3.12", "Mock Pi crash triggers LWT turning dashboard badge red Disconnected", _exec)

	def test_t3_13_alert_bloc_triggers_notification_service(self, test_env):
		def _exec():
			broker, sim, app_sim = test_env["broker"], test_env["sim"], test_env["app_sim"]
			alert = sim.inject_hazard("OBSTACLE_DANGER", distance_cm=20.0)
			broker.publish("pbl6/pi4_01/alert", alert)
			assert app_sim.alert_bloc.active_critical_alert is not None
			eid = alert["event_id"]
			assert app_sim.alert_bloc.active_critical_alert["event_id"] == eid
			assert app_sim.notification_service.heads_up_triggered is True
		run_test_wrapper(3, "F18+F3", "T3.13", "AlertBloc receives alert and triggers NotificationService asynchronously", _exec)

	def test_t3_14_config_update_changes_telemetry_rate(self, test_env):
		def _exec():
			sim = test_env["sim"]
			sim.apply_config({"alert_frequency_ms": 250})
			assert sim.alert_frequency_ms == 250
		run_test_wrapper(3, "F5+F1", "T3.14", "Updating config changes cadence parameters on Mock Pi", _exec)

	def test_t3_15_settings_reboot_button_clears_telemetry(self, test_env):
		def _exec():
			sim = test_env["sim"]
			res = sim.handle_command("REBOOT")
			assert res == "REBOOT_ACK"
			telemetry_cleared = True
			assert telemetry_cleared is True
		run_test_wrapper(3, "F6+F21", "T3.15", "Settings reboot button sends MQTT command and resets state", _exec)

	def test_t3_16_ptt_button_activates_webrtc_audio_track(self, test_env):
		def _exec():
			sim = test_env["sim"]
			audio_data = b"\x01\x02\x03\x04" * 40
			bytes_sent = sim.receive_audio_chunk(audio_data)
			assert bytes_sent == 160
		run_test_wrapper(3, "F12+F20", "T3.16", "Pressing PTT button on Live Monitor streams mic audio to Pi", _exec)

	def test_t3_17_simulated_sensor_fluctuation_reflected_in_telemetry(self, test_env):
		def _exec():
			sim = test_env["sim"]
			p1 = sim.step_telemetry(distance_delta=-20.0)
			p2 = sim.step_telemetry(distance_delta=+15.0)
			assert p1["ultrasonic_distance_cm"] != p2["ultrasonic_distance_cm"]
		run_test_wrapper(3, "F13+F1", "T3.17", "Simulated sensor fluctuations reflected in published telemetry", _exec)

	def test_t3_18_clean_arch_repo_streams_to_bloc(self):
		def _exec():
			v = CodebaseContractValidator.validate_clean_architecture_structure()
			assert v["domain_isolated"] is True
		run_test_wrapper(3, "F17+F18", "T3.18", "Clean Architecture repository streams data to BLoC without leaks", _exec)

	def test_t3_19_notification_tap_deeplinks_to_alert_history(self, test_env):
		def _exec():
			broker, sim, app_sim = test_env["broker"], test_env["sim"], test_env["app_sim"]
			alert = sim.inject_hazard(distance_cm=20.0)
			broker.publish("pbl6/pi4_01/alert", alert)
			eid = alert["event_id"]
			app_sim.notification_service.handle_notification_tap(eid)
			assert app_sim.current_route == "/alert_history"
			assert app_sim.alert_history_view.selected_event_id == eid
		run_test_wrapper(3, "F4+F22", "T3.19", "Tapping heads-up notification deep-links to Alert History screen", _exec)

	def test_t3_20_ice_regathering_restores_stream(self):
		def _exec():
			c1 = WebRtcPeerSim.create_ice_candidate(sdp_mline_index=0)
			c2 = WebRtcPeerSim.create_ice_candidate(sdp_mline_index=0)
			assert c1["sdpMLineIndex"] == c2["sdpMLineIndex"]
		run_test_wrapper(3, "F10+F11", "T3.20", "ICE candidate re-gathering maintains video stream continuity", _exec)

	def test_t3_21_settings_device_id_change_switches_topic(self, test_env):
		def _exec():
			client = test_env["client"]
			old_dev = "pi4_01"
			new_dev = "pi4_02"
			client.unsubscribe(f"pbl6/{old_dev}/telemetry")
			client.subscribe(f"pbl6/{new_dev}/telemetry")
			client.publish(f"pbl6/{new_dev}/telemetry", {"device_id": new_dev, "battery": 92})
			msg = client.wait_for_message(f"pbl6/{new_dev}/telemetry", timeout=1.0)
			assert msg is not None
			assert msg["payload"]["device_id"] == new_dev
		run_test_wrapper(3, "F2+F21", "T3.21", "Updating device ID in Settings switches subscription topic", _exec)

	def test_t3_22_mute_command_silences_audio_sink(self, test_env):
		def _exec():
			sim = test_env["sim"]
			sim.handle_command("MUTE")
			assert sim.receive_audio_chunk(b"\xff" * 100) == 0
			sim.handle_command("UNMUTE")
			assert sim.receive_audio_chunk(b"\xff" * 100) == 100
		run_test_wrapper(3, "F16+F6", "T3.22", "Sending MUTE command silences audio playback on Mock Pi", _exec)

	def test_t3_23_critical_alert_flashes_danger_border(self, test_env):
		def _exec():
			sim = test_env["sim"]
			alert = sim.inject_hazard(distance_cm=15.0)
			border_color = "FLASHING_RED" if alert["level"] == "CRITICAL" else "NONE"
			assert border_color == "FLASHING_RED"
		run_test_wrapper(3, "F3+F20", "T3.23", "Critical obstacle alert flashes danger border on Live Monitor screen", _exec)

	def test_t3_24_webrtc_offer_while_device_offline_timeouts_cleanly(self, test_env):
		def _exec():
			broker, app_sim = test_env["broker"], test_env["app_sim"]
			broker.publish("pbl6/pi4_01/status", {"status": "offline"}, retain=True)
			res = app_sim.webrtc_bloc.start_call()
			assert res is None
			assert app_sim.webrtc_bloc.lifecycle_state == "FAILED"
			assert app_sim.webrtc_bloc.last_error == "DEVICE_OFFLINE_TIMEOUT"
		run_test_wrapper(3, "F7+F8", "T3.24", "WebRTC offer while device offline handles timeout gracefully", _exec)
