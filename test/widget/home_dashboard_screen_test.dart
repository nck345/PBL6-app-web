import 'package:flutter/material.dart' hide ConnectionState;
import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/core/constants/app_constants.dart';
import 'package:pbl6_app/presentation/bloc/alerts/alert_bloc.dart';
import 'package:pbl6_app/presentation/bloc/connection/connection_bloc.dart';
import 'package:pbl6_app/presentation/bloc/dashboard/dashboard_bloc.dart';
import 'package:pbl6_app/presentation/screens/home_dashboard_screen.dart';
import 'package:pbl6_app/presentation/widgets/alert_banner_widget.dart';
import '../helpers/test_fakes.dart';

void main() {
	late FakeMqttDatasource fakeMqtt;
	late FakeTelemetryRepository fakeTelemetryRepo;
	late FakeAlertRepository fakeAlertRepo;
	late FakeNotificationService fakeNotif;

	late ConnectionBloc connBloc;
	late DashboardBloc dashBloc;
	late AlertBloc alertBloc;

	setUp(() {
		fakeMqtt = FakeMqttDatasource();
		fakeTelemetryRepo = FakeTelemetryRepository();
		fakeAlertRepo = FakeAlertRepository();
		fakeNotif = FakeNotificationService();

		connBloc = ConnectionBloc(mqttDatasource: fakeMqtt);
		dashBloc = DashboardBloc(telemetryRepository: fakeTelemetryRepo);
		alertBloc = AlertBloc(alertRepository: fakeAlertRepo, notificationService: fakeNotif);
	});

	tearDown(() async {
		await connBloc.close();
		await dashBloc.close();
		await alertBloc.close();
		fakeTelemetryRepo.dispose();
		fakeAlertRepo.dispose();
		fakeMqtt.dispose();
	});

	Widget createScreen({VoidCallback? onNavigateToLive}) {
		return buildTestApp(
			connectionBloc: connBloc,
			dashboardBloc: dashBloc,
			alertBloc: alertBloc,
			child: HomeDashboardScreen(onNavigateToLive: onNavigateToLive),
		);
	}

	group('HomeDashboardScreen Widget Tests (W-DASH-01..15)', () {
		testWidgets('W-DASH-01: Displays Online chip on ConnectionSuccess', (tester) async {
			connBloc.emit(const ConnectionSuccess(status: 'connected'));
			await tester.pumpWidget(createScreen());

			expect(find.text(AppConstants.appTitle), findsOneWidget);
			expect(find.text('Online'), findsOneWidget);
			expect(find.byIcon(Icons.wifi), findsOneWidget);
		});

		testWidgets('W-DASH-02: Displays CircularProgressIndicator on ConnectionLoading', (tester) async {
			connBloc.emit(ConnectionLoading());
			await tester.pumpWidget(createScreen());

			expect(find.byType(CircularProgressIndicator), findsOneWidget);
		});

		testWidgets('W-DASH-03: Displays reconnect button on ConnectionFailure and dispatches event on tap', (tester) async {
			connBloc.emit(const ConnectionFailure(message: 'Lỗi mạng'));
			await tester.pumpWidget(createScreen());

			final reconnectBtn = find.text('Kết nối lại');
			expect(reconnectBtn, findsOneWidget);
			expect(find.byIcon(Icons.wifi_off), findsOneWidget);

			await tester.tap(reconnectBtn);
			await tester.pump();

			expect(connBloc.state, isA<ConnectionLoading>());
		});

		testWidgets('W-DASH-04: Displays placeholder text when DashboardInitial', (tester) async {
			await tester.pumpWidget(createScreen());

			expect(find.text('Chưa có thông số thiết bị từ MQTT broker'), findsOneWidget);
			expect(find.text('Đang đợi...'), findsOneWidget);
		});

		testWidgets('W-DASH-05: Displays all 4 MetricTiles and battery when DashboardLoaded', (tester) async {
			final tel = createTestTelemetry(
				ultrasonicDistanceCm: 145.2,
				temperatureCelsius: 48.5,
				cpuUsage: 32.0,
				speakerVolume: 80,
				batteryPercentage: 85,
			);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());

			expect(find.text('Vật cản gần nhất'), findsOneWidget);
			expect(find.text('145.2'), findsOneWidget);
			expect(find.text('Nhiệt độ CPU'), findsOneWidget);
			expect(find.text('48.5'), findsOneWidget);
			expect(find.text('Tải CPU'), findsOneWidget);
			expect(find.text('32'), findsOneWidget);
			expect(find.text('Âm lượng loa'), findsOneWidget);
			expect(find.text('80'), findsOneWidget);
			expect(find.text('85%'), findsOneWidget);
		});

		testWidgets('W-DASH-06: Proximity warning for distance < 60cm shows warning subtitle', (tester) async {
			final tel = createTestTelemetry(ultrasonicDistanceCm: 25.0);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());

			expect(find.text('CẢNH BÁO QUÁ GẦN'), findsOneWidget);
		});

		testWidgets('W-DASH-07: Proximity safe for distance >= 60cm shows safe subtitle', (tester) async {
			final tel = createTestTelemetry(ultrasonicDistanceCm: 85.0);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());

			expect(find.text('Khoảng cách an toàn'), findsOneWidget);
		});

		testWidgets('W-DASH-08: Negative sensor reading displays disconnected sensor state', (tester) async {
			final tel = createTestTelemetry(ultrasonicDistanceCm: -1.0);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());

			expect(find.text('--'), findsOneWidget);
			expect(find.text('Chưa kết nối cảm biến'), findsOneWidget);
			expect(find.byIcon(Icons.sensors_off), findsOneWidget);
		});

		testWidgets('W-DASH-09: Thermal styling changes based on CPU temp > 70C', (tester) async {
			final hotTel = createTestTelemetry(temperatureCelsius: 75.0);
			dashBloc.emit(DashboardLoaded(telemetry: hotTel));
			await tester.pumpWidget(createScreen());
			expect(find.text('Nhiệt độ cao'), findsOneWidget);

			final coolTel = createTestTelemetry(temperatureCelsius: 50.0);
			dashBloc.emit(DashboardLoaded(telemetry: coolTel));
			await tester.pumpWidget(createScreen());
			expect(find.text('Ổn định'), findsOneWidget);
		});

		testWidgets('W-DASH-10: Shows staleness banner and grey battery when isStale is true', (tester) async {
			final tel = createTestTelemetry(batteryPercentage: 80);
			dashBloc.emit(DashboardLoaded(telemetry: tel, isStale: true));
			await tester.pumpWidget(createScreen());

			expect(find.text('Dữ liệu cảm biến có thể bị gián đoạn (mất tín hiệu > 10s)'), findsOneWidget);
			expect(find.byIcon(Icons.access_time), findsOneWidget);

			final batteryText = tester.widget<Text>(find.text('80%'));
			expect(batteryText.style?.color, equals(Colors.grey));
		});

		testWidgets('W-DASH-11: Pull-to-refresh triggers connection and subscription events', (tester) async {
			await tester.pumpWidget(createScreen());

			await tester.fling(find.byType(RefreshIndicator), const Offset(0, 300), 1000);
			await tester.pump();
			await tester.pump(const Duration(seconds: 1));

			expect(connBloc.state, isA<ConnectionLoading>());
		});

		testWidgets('W-DASH-12: Displays AlertBannerWidget when active unacknowledged alert exists', (tester) async {
			final alert = createTestAlert(
				level: 'CRITICAL',
				message: 'Hố ga phía trước',
				isAcknowledged: false,
			);
			fakeAlertRepo.emitAlert(alert);
			alertBloc.add(const StartAlertSubscription());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pumpWidget(createScreen());

			expect(find.byType(AlertBannerWidget), findsOneWidget);
			expect(find.text('CẢNH BÁO NGUY HIỂM'), findsOneWidget);
			expect(find.textContaining('Hố ga phía trước'), findsOneWidget);
		});

		testWidgets('W-DASH-13: Acknowledging AlertBannerWidget dispatches event and dismisses banner', (tester) async {
			final alert = createTestAlert(
				eventId: 'evt_999',
				level: 'CRITICAL',
				message: 'Vật cản nguy hiểm',
				isAcknowledged: false,
			);
			fakeAlertRepo.emitAlert(alert);
			alertBloc.add(const StartAlertSubscription());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pumpWidget(createScreen());

			expect(find.byType(AlertBannerWidget), findsOneWidget);

			await tester.tap(find.byIcon(Icons.check));
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pump();

			expect(alertBloc.state, isA<AlertActive>());
			final currentState = alertBloc.state as AlertActive;
			expect(currentState.latestAlert.isAcknowledged, isTrue);

			expect(find.byType(AlertBannerWidget), findsNothing);
		});

		testWidgets('W-DASH-14: Tapping camera card calls onNavigateToLive callback', (tester) async {
			bool navigated = false;
			await tester.pumpWidget(createScreen(onNavigateToLive: () => navigated = true));

			final cameraCard = find.text('Xem Camera Trực Tiếp');
			expect(cameraCard, findsOneWidget);

			await tester.tap(cameraCard);
			await tester.pump();

			expect(navigated, isTrue);
		});

		testWidgets('W-DASH-15: Renders device header and metrics safely on narrow 320x640 screen without overflow', (tester) async {
			tester.view.physicalSize = const Size(320, 640);
			tester.view.devicePixelRatio = 1.0;
			addTearDown(() {
				tester.view.resetPhysicalSize();
				tester.view.resetDevicePixelRatio();
			});

			final tel = createTestTelemetry(
				ultrasonicDistanceCm: 9999.0,
				batteryPercentage: 90,
			);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());

			expect(tester.takeException(), isNull);
			expect(find.text('Thiết bị Pi 4'), findsOneWidget);
			expect(find.text('9999.0'), findsOneWidget);
		});
	});
}
