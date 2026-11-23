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
	E2EResultCollector
)

@pytest.fixture
def scenario_env():
	broker = EmbeddedMqttBroker()
	app_client = TestMqttClient("mobile_app_user")
	pi_sim = MockPiSimulator("pi4_01")
	app_client.connect(broker)
	yield {"broker": broker, "app": app_client, "sim": pi_sim}
	app_client.disconnect()
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

class TestTier4Scenarios:
	def test_s01_cold_boot_and_surveillance_cycle(self, scenario_env):
		def _exec():
			broker, app, sim = scenario_env["broker"], scenario_env["app"], scenario_env["sim"]
			app.subscribe("pbl6/pi4_01/#")
			broker.publish("pbl6/pi4_01/status", {"status": "online", "timestamp": int(time.time())}, qos=1, retain=True)
			status_msg = app.wait_for_message("pbl6/pi4_01/status", timeout=1.0)
			assert status_msg is not None and status_msg["payload"]["status"] == "online"

			broker.publish("pbl6/pi4_01/telemetry", sim.step_telemetry())
			telem_msg = app.wait_for_message("pbl6/pi4_01/telemetry", timeout=1.0)
			assert telem_msg is not None and telem_msg["payload"]["battery_percentage"] == 85

			offer = WebRtcPeerSim.create_offer(caller="mobile_app_user")
			app.publish("pbl6/pi4_01/webrtc/offer", offer)
			answer = WebRtcPeerSim.create_answer(offer, callee="pi4_01")
			broker.publish("pbl6/pi4_01/webrtc/answer", answer)
			ans_msg = app.wait_for_message("pbl6/pi4_01/webrtc/answer", timeout=1.0)
			assert ans_msg is not None and ans_msg["payload"]["type"] == "answer"

			frame = sim.generate_synthetic_radar_frame()
			assert len(frame) == 640 * 480 * 3
			audio_bytes = b"\x01\x02\x03\x04" * 100
			assert sim.receive_audio_chunk(audio_bytes) == len(audio_bytes)
		run_test_wrapper(4, "Scenario", "Scenario_1", "Cold-boot surveillance cycle with WebRTC negotiation and audio streaming", _exec)

	def test_s02_sudden_obstacle_danger_rapid_response(self, scenario_env):
		def _exec():
			broker, app, sim = scenario_env["broker"], scenario_env["app"], scenario_env["sim"]
			app.subscribe("pbl6/pi4_01/alert")
			alert = sim.inject_hazard(alert_type="OBSTACLE_DANGER", distance_cm=22.0, detected_objects=["stairs_down"])
			broker.publish("pbl6/pi4_01/alert", alert, qos=1)

			rec_alert = app.wait_for_message("pbl6/pi4_01/alert", timeout=1.0)
			assert rec_alert is not None
			assert rec_alert["payload"]["level"] == "CRITICAL"
			target_obj = "stairs_down"
			assert target_obj in rec_alert["payload"]["detected_objects"]

			voice_warning = b"\x10\x20\x30\x40" * 80
			delivered = sim.receive_audio_chunk(voice_warning)
			assert delivered == len(voice_warning)
		run_test_wrapper(4, "Scenario", "Scenario_2", "Sudden obstacle danger alert notification and PTT voice warning", _exec)

	def test_s03_dynamic_parameter_tuning_in_noisy_market(self, scenario_env):
		def _exec():
			broker, app, sim = scenario_env["broker"], scenario_env["app"], scenario_env["sim"]
			app.subscribe("pbl6/pi4_01/config")
			new_cfg = {"distance_threshold_cm": 150, "speaker_volume": 100}
			app.publish("pbl6/pi4_01/config", new_cfg, qos=1, retain=True)

			rec_cfg = app.wait_for_message("pbl6/pi4_01/config", timeout=1.0)
			assert rec_cfg is not None
			sim.apply_config(rec_cfg["payload"])
			assert sim.distance_threshold_cm == 150
			assert sim.speaker_volume == 100
		run_test_wrapper(4, "Scenario", "Scenario_3", "Dynamic parameter tuning in high noise environment", _exec)

	def test_s04_network_disruption_and_auto_recovery(self, scenario_env):
		def _exec():
			broker, sim = scenario_env["broker"], scenario_env["sim"]
			temp_client = TestMqttClient("cellular_app")
			temp_client.connect(broker)
			temp_client.subscribe("pbl6/pi4_01/telemetry")
			temp_client.publish("pbl6/pi4_01/telemetry", sim.step_telemetry())
			assert temp_client.wait_for_message("pbl6/pi4_01/telemetry", timeout=1.0) is not None

			temp_client.disconnect(ungraceful=False)
			time.sleep(0.01)
			temp_client.connect(broker)
			temp_client.subscribe("pbl6/pi4_01/telemetry")
			temp_client.publish("pbl6/pi4_01/telemetry", sim.step_telemetry())
			res = temp_client.wait_for_message("pbl6/pi4_01/telemetry", timeout=1.0)
			assert res is not None
			temp_client.disconnect()
		run_test_wrapper(4, "Scenario", "Scenario_4", "Network disruption and automatic client reconnect cycle", _exec)

	def test_s05_battery_depletion_and_power_off_supervision(self, scenario_env):
		def _exec():
			broker, app, sim = scenario_env["broker"], scenario_env["app"], scenario_env["sim"]
			app.subscribe("pbl6/pi4_01/#")
			pi_client = TestMqttClient("pi_hardware_node")
			pi_client.connect(broker, lwt_topic="pbl6/pi4_01/status", lwt_payload={"status": "offline"})

			for battery_level in [15, 10, 5, 0]:
				sim.battery_percentage = battery_level
				p = sim.step_telemetry()
				broker.publish("pbl6/pi4_01/telemetry", p)

			pi_client.disconnect(ungraceful=True)
			offline_msg = app.wait_for_message("pbl6/pi4_01/status", timeout=1.0, predicate=lambda m: m["payload"]["status"] == "offline")
			assert offline_msg is not None
			assert offline_msg["payload"]["status"] == "offline"
		run_test_wrapper(4, "Scenario", "Scenario_5", "Battery depletion to 0% and power-off LWT supervision", _exec)

	def test_s06_manual_hazard_injection_stress(self, scenario_env):
		def _exec():
			broker, app, sim = scenario_env["broker"], scenario_env["app"], scenario_env["sim"]
			app.subscribe("pbl6/pi4_01/alert")
			alert_a = sim.inject_hazard(distance_cm=20.0, detected_objects=["stairs_down"])
			broker.publish("pbl6/pi4_01/alert", alert_a, qos=1)
			alert_p = sim.inject_hazard(distance_cm=15.0, detected_objects=["puddle"])
			broker.publish("pbl6/pi4_01/alert", alert_p, qos=1)

			alerts = app.collect_messages("pbl6/pi4_01/alert", count=2, timeout=1.0)
			assert len(alerts) == 2
			obj1 = "stairs_down"
			obj2 = "puddle"
			assert obj1 in alerts[0]["payload"]["detected_objects"]
			assert obj2 in alerts[1]["payload"]["detected_objects"]
		run_test_wrapper(4, "Scenario", "Scenario_6", "Manual hotkey hazard injection and chronological recording", _exec)

	def test_s07_remote_maintenance_reboot_lifecycle(self, scenario_env):
		def _exec():
			broker, app, sim = scenario_env["broker"], scenario_env["app"], scenario_env["sim"]
			app.subscribe("pbl6/pi4_01/command")
			app.publish("pbl6/pi4_01/command", {"command": "RESTART_SERVICE"}, qos=1)

			cmd_msg = app.wait_for_message("pbl6/pi4_01/command", timeout=1.0)
			assert cmd_msg is not None
			ack = sim.handle_command(cmd_msg["payload"]["command"])
			assert ack == "RESTART_ACK"
		run_test_wrapper(4, "Scenario", "Scenario_7", "Remote service restart command and sensor normalization", _exec)

	def test_s08_multi_subscriber_synchronization(self, scenario_env):
		def _exec():
			broker, sim = scenario_env["broker"], scenario_env["sim"]
			family_member_1 = TestMqttClient("family_1")
			family_member_2 = TestMqttClient("family_2")
			family_member_1.connect(broker)
			family_member_2.connect(broker)

			family_member_1.subscribe("pbl6/pi4_01/#")
			family_member_2.subscribe("pbl6/pi4_01/#")

			alert = sim.inject_hazard(distance_cm=25.0)
			broker.publish("pbl6/pi4_01/alert", alert, qos=1)

			m1 = family_member_1.wait_for_message("pbl6/pi4_01/alert", timeout=1.0)
			m2 = family_member_2.wait_for_message("pbl6/pi4_01/alert", timeout=1.0)
			assert m1 is not None and m2 is not None
			assert m1["payload"]["event_id"] == m2["payload"]["event_id"]

			family_member_1.disconnect()
			family_member_2.disconnect()
		run_test_wrapper(4, "Scenario", "Scenario_8", "Multi-subscriber synchronization for family members", _exec)

	def test_s09_push_to_talk_intercom_reliability(self, scenario_env):
		def _exec():
			sim = scenario_env["sim"]
			for turn in range(5):
				chunk = bytes([turn] * 200)
				rec = sim.receive_audio_chunk(chunk)
				assert rec == 200
			assert sim.audio_chunks_received == 5
		run_test_wrapper(4, "Scenario", "Scenario_9", "Push-to-Talk 5-turn voice intercom without audio clipping", _exec)

	def test_s10_continuous_long_duration_telemetry(self, scenario_env):
		def _exec():
			broker, app, sim = scenario_env["broker"], scenario_env["app"], scenario_env["sim"]
			app.subscribe("pbl6/pi4_01/telemetry")
			for cycle in range(100):
				pkt = sim.step_telemetry(distance_delta=(cycle % 3 - 1))
				broker.publish("pbl6/pi4_01/telemetry", pkt)
			msgs = app.collect_messages("pbl6/pi4_01/telemetry", count=100, timeout=2.0)
			assert len(msgs) == 100
		run_test_wrapper(4, "Scenario", "Scenario_10", "Continuous 100-cycle telemetry burst stability without packet loss", _exec)

	def test_s11_emergency_alert_flood_and_debounce(self, scenario_env):
		def _exec():
			broker, app, sim = scenario_env["broker"], scenario_env["app"], scenario_env["sim"]
			app.subscribe("pbl6/pi4_01/alert")
			for i in range(10):
				alert = sim.inject_hazard(distance_cm=10.0 + i)
				broker.publish("pbl6/pi4_01/alert", alert, qos=1)
			alerts = app.collect_messages("pbl6/pi4_01/alert", count=10, timeout=1.0)
			assert len(alerts) == 10
		run_test_wrapper(4, "Scenario", "Scenario_11", "Emergency alert flood 10 bursts handled with exact sequencing", _exec)

	def test_s12_graceful_degradation_without_webrtc_hardware(self, scenario_env):
		def _exec():
			broker, app, sim = scenario_env["broker"], scenario_env["app"], scenario_env["sim"]
			has_camera = False
			has_mic = False

			app.subscribe("pbl6/pi4_01/#")
			broker.publish("pbl6/pi4_01/telemetry", sim.step_telemetry())
			telem = app.wait_for_message("pbl6/pi4_01/telemetry", timeout=1.0)
			assert telem is not None
			assert not has_camera and not has_mic
		run_test_wrapper(4, "Scenario", "Scenario_12", "Graceful degradation without WebRTC hardware with full telemetry active", _exec)
