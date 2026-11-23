import 'package:flutter/material.dart' hide ConnectionState;
import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/core/constants/app_constants.dart';
import 'package:pbl6_app/domain/entities/device_config_entity.dart';
import 'package:pbl6_app/presentation/bloc/config/config_bloc.dart';
import 'package:pbl6_app/presentation/bloc/connection/connection_bloc.dart';
import 'package:pbl6_app/presentation/screens/settings_screen.dart';
import '../helpers/test_fakes.dart';

void main() {
	late FakeConfigRepository fakeConfigRepo;
	late FakeMqttDatasource fakeMqtt;
	late ConfigBloc configBloc;
	late ConnectionBloc connBloc;

	setUp(() {
		fakeConfigRepo = FakeConfigRepository();
		fakeMqtt = FakeMqttDatasource();
		configBloc = ConfigBloc(configRepository: fakeConfigRepo);
		connBloc = ConnectionBloc(mqttDatasource: fakeMqtt);
	});

	tearDown(() async {
		await configBloc.close();
		await connBloc.close();
		fakeConfigRepo.dispose();
		fakeMqtt.dispose();
	});

	Widget createScreen() {
		return buildTestApp(
			configBloc: configBloc,
			connectionBloc: connBloc,
			child: const SettingsScreen(),
		);
	}

	group('SettingsScreen Widget Tests (W-SET-01..13)', () {
		testWidgets('W-SET-01: Dispatches LoadConfig on mount and populates initial values', (tester) async {
			final initialConfig = createTestConfig(
				distanceThresholdCm: 100,
				speakerVolume: 75,
				alertFrequencyMs: 800,
			);
			fakeConfigRepo.currentConfigValue = initialConfig;

			await tester.pumpWidget(createScreen());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pump();

			expect(find.text('Ngưỡng khoảng cách cảnh báo: 100 cm'), findsOneWidget);
			expect(find.text('Âm lượng loa Raspberry Pi: 75%'), findsOneWidget);
			expect(find.text('Chu kỳ quét cảnh báo: 800 ms'), findsOneWidget);
		});

		testWidgets('W-SET-02: Moving distance slider updates label dynamically', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			final distanceSlider = tester.widget<Slider>(find.byType(Slider).at(0));
			distanceSlider.onChanged!(120);
			await tester.pump();

			expect(find.text('Ngưỡng khoảng cách cảnh báo: 120 cm'), findsOneWidget);
		});

		testWidgets('W-SET-03: Moving speaker volume slider updates label dynamically', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			final volumeSlider = tester.widget<Slider>(find.byType(Slider).at(1));
			volumeSlider.onChanged!(90);
			await tester.pump();

			expect(find.text('Âm lượng loa Raspberry Pi: 90%'), findsOneWidget);
		});

		testWidgets('W-SET-04: Moving alert frequency slider updates label dynamically', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			final freqSlider = tester.widget<Slider>(find.byType(Slider).at(2));
			freqSlider.onChanged!(600);
			await tester.pump();

			expect(find.text('Chu kỳ quét cảnh báo: 600 ms'), findsOneWidget);
		});

		testWidgets('W-SET-05: Tapping save button dispatches UpdateConfigRequested with current values', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			tester.widget<Slider>(find.byType(Slider).at(0)).onChanged!(110);
			tester.widget<Slider>(find.byType(Slider).at(1)).onChanged!(85);
			tester.widget<Slider>(find.byType(Slider).at(2)).onChanged!(700);
			await tester.pump();

			final saveBtn = find.text('Lưu cấu hình lên Pi 4');
			expect(saveBtn, findsOneWidget);

			await tester.tap(saveBtn);
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pump();

			expect(fakeConfigRepo.currentConfig, isNotNull);
			expect(fakeConfigRepo.currentConfig!.distanceThresholdCm, equals(110));
			expect(fakeConfigRepo.currentConfig!.speakerVolume, equals(85));
			expect(fakeConfigRepo.currentConfig!.alertFrequencyMs, equals(700));
		});

		testWidgets('W-SET-06: ConfigSuccess displays green SnackBar', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			configBloc.add(const UpdateConfigRequested(config: DeviceConfigEntity.initial));
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();
			await tester.pump(const Duration(milliseconds: 300));

			expect(find.text('Cập nhật cấu hình thành công'), findsOneWidget);
		});

		testWidgets('W-SET-07: ConfigFailure displays red SnackBar', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			fakeConfigRepo.shouldThrow = true;
			configBloc.add(const UpdateConfigRequested(config: DeviceConfigEntity.initial));
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();
			await tester.pump(const Duration(milliseconds: 300));

			expect(find.textContaining('Lỗi: Exception: Failed to publish config'), findsOneWidget);
		});

		testWidgets('W-SET-08: Tapping reboot command dispatches REBOOT command', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			final rebootTile = find.text('Khởi động lại Pi (Reboot)');
			await tester.ensureVisible(rebootTile);
			await tester.pumpAndSettle();

			expect(rebootTile, findsOneWidget);
			await tester.tap(rebootTile);
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});

			expect(fakeConfigRepo.lastCommand, equals('REBOOT'));
		});

		testWidgets('W-SET-09: Tapping restart service command dispatches RESTART_SERVICE command', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			final restartTile = find.text('Khởi động lại dịch vụ AI (Restart Service)');
			await tester.ensureVisible(restartTile);
			await tester.pumpAndSettle();

			expect(restartTile, findsOneWidget);
			await tester.tap(restartTile);
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});

			expect(fakeConfigRepo.lastCommand, equals('RESTART_SERVICE'));
		});

		testWidgets('W-SET-10: Tapping trigger buzzer command dispatches TRIGGER_BUZZER command', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			final buzzerTile = find.text('Phát còi khẩn cấp (Trigger Buzzer)');
			await tester.ensureVisible(buzzerTile);
			await tester.pumpAndSettle();

			expect(buzzerTile, findsOneWidget);
			await tester.tap(buzzerTile);
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});

			expect(fakeConfigRepo.lastCommand, equals('TRIGGER_BUZZER'));
		});

		testWidgets('W-SET-11: Displays network diagnostics parameters', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			await tester.drag(find.byType(ListView), const Offset(0, -500));
			await tester.pumpAndSettle();

			expect(find.text('Broker: ${AppConstants.defaultMqttBroker}:${AppConstants.defaultMqttPort}'), findsOneWidget);
			expect(find.text('Device ID: ${AppConstants.defaultDeviceId}'), findsOneWidget);
			expect(find.text('STUN: ${AppConstants.defaultStunServer}'), findsOneWidget);
		});

		testWidgets('W-SET-12: Tapping reconnect MQTT button dispatches ConnectRequested', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			await tester.drag(find.byType(ListView), const Offset(0, -500));
			await tester.pumpAndSettle();

			final reconnectBtn = find.text('Tái kết nối MQTT Broker');
			expect(reconnectBtn, findsOneWidget);
			await tester.tap(reconnectBtn);
			await tester.pump();

			expect(connBloc.state, isA<ConnectionLoading>());
		});

		testWidgets('W-SET-13: Out-of-bounds config values are safely clamped on ConfigLoaded', (tester) async {
			final outOfBoundsConfig = createTestConfig(
				distanceThresholdCm: -10,
				speakerVolume: 150,
				alertFrequencyMs: 50,
			);
			fakeConfigRepo.currentConfigValue = outOfBoundsConfig;

			await tester.pumpWidget(createScreen());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pump();

			expect(find.text('Ngưỡng khoảng cách cảnh báo: 20 cm'), findsOneWidget);
			expect(find.text('Âm lượng loa Raspberry Pi: 100%'), findsOneWidget);
			expect(find.text('Chu kỳ quét cảnh báo: 200 ms'), findsOneWidget);
		});
	});
}
