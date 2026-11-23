import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/core/constants/app_constants.dart';
import 'package:pbl6_app/main.dart';
import '../helpers/test_fakes.dart';

void main() {
	late FakeMqttDatasource fakeMqtt;
	late FakeWebrtcDatasource fakeWebrtc;
	late FakeTelemetryRepository fakeTelemetryRepo;
	late FakeAlertRepository fakeAlertRepo;
	late FakeConfigRepository fakeConfigRepo;
	late FakeNotificationService fakeNotif;

	setUp(() {
		setupMockPermissionHandler(isGranted: true);
		fakeMqtt = FakeMqttDatasource();
		fakeWebrtc = FakeWebrtcDatasource();
		fakeTelemetryRepo = FakeTelemetryRepository();
		fakeAlertRepo = FakeAlertRepository();
		fakeConfigRepo = FakeConfigRepository();
		fakeNotif = FakeNotificationService();
	});

	tearDown(() async {
		clearMockPermissionHandler();
		await fakeWebrtc.dispose();
		fakeTelemetryRepo.dispose();
		fakeAlertRepo.dispose();
		fakeConfigRepo.dispose();
		fakeMqtt.dispose();
	});

	testWidgets('AppProviders bootstrap mounts MaterialApp and reactive BLoC ecosystem cleanly', (tester) async {
		await tester.pumpWidget(
			AppProviders(
				mqttDatasource: fakeMqtt,
				webrtcDatasource: fakeWebrtc,
				telemetryRepository: fakeTelemetryRepo,
				alertRepository: fakeAlertRepo,
				configRepository: fakeConfigRepo,
				notificationService: fakeNotif,
			),
		);
		await tester.pump();

		expect(find.text(AppConstants.appTitle), findsOneWidget);
		expect(find.text('Thiết bị Pi 4'), findsOneWidget);
		expect(find.text('Tổng quan'), findsWidgets);
		expect(find.text('Camera POV'), findsOneWidget);
		expect(find.text('Cảnh báo'), findsOneWidget);
		expect(find.text('Cài đặt'), findsOneWidget);

		// Emit live telemetry and verify UI responds
		final tel = createTestTelemetry(
			batteryPercentage: 92,
			temperatureCelsius: 45.0,
			ultrasonicDistanceCm: 180.0,
		);
		fakeTelemetryRepo.emitTelemetry(tel);
		await tester.pump();

		expect(find.text('92%'), findsOneWidget);
		expect(find.text('180.0'), findsOneWidget);
		expect(find.text('Khoảng cách an toàn'), findsOneWidget);

		// Switch to Cài đặt tab
		await tester.tap(find.text('Cài đặt'));
		await tester.pump();

		expect(find.text('Cài đặt & Điều khiển'), findsOneWidget);
	});
}
