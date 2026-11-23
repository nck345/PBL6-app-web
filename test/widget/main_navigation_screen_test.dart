import 'package:flutter/material.dart' hide ConnectionState;
import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/presentation/bloc/alerts/alert_bloc.dart';
import 'package:pbl6_app/presentation/bloc/config/config_bloc.dart';
import 'package:pbl6_app/presentation/bloc/connection/connection_bloc.dart';
import 'package:pbl6_app/presentation/bloc/dashboard/dashboard_bloc.dart';
import 'package:pbl6_app/presentation/bloc/webrtc/webrtc_bloc.dart';
import 'package:pbl6_app/presentation/screens/main_navigation_screen.dart';
import '../helpers/test_fakes.dart';

void main() {
	late FakeMqttDatasource fakeMqtt;
	late FakeTelemetryRepository fakeTelemetryRepo;
	late FakeAlertRepository fakeAlertRepo;
	late FakeConfigRepository fakeConfigRepo;
	late FakeWebrtcDatasource fakeWebrtc;
	late FakeNotificationService fakeNotif;

	late ConnectionBloc connBloc;
	late DashboardBloc dashBloc;
	late AlertBloc alertBloc;
	late ConfigBloc configBloc;
	late WebRtcBloc webrtcBloc;

	setUp(() {
		setupMockPermissionHandler(isGranted: true);
		fakeMqtt = FakeMqttDatasource();
		fakeTelemetryRepo = FakeTelemetryRepository();
		fakeAlertRepo = FakeAlertRepository();
		fakeConfigRepo = FakeConfigRepository();
		fakeWebrtc = FakeWebrtcDatasource();
		fakeNotif = FakeNotificationService();

		connBloc = ConnectionBloc(mqttDatasource: fakeMqtt);
		dashBloc = DashboardBloc(telemetryRepository: fakeTelemetryRepo);
		alertBloc = AlertBloc(alertRepository: fakeAlertRepo, notificationService: fakeNotif);
		configBloc = ConfigBloc(configRepository: fakeConfigRepo);
		webrtcBloc = WebRtcBloc(webrtcDatasource: fakeWebrtc);
	});

	tearDown(() async {
		clearMockPermissionHandler();
		await connBloc.close();
		await dashBloc.close();
		await alertBloc.close();
		await configBloc.close();
		await webrtcBloc.close();
		await fakeWebrtc.dispose();
		fakeTelemetryRepo.dispose();
		fakeAlertRepo.dispose();
		fakeConfigRepo.dispose();
		fakeMqtt.dispose();
	});

	Widget createScreen() {
		return buildTestApp(
			connectionBloc: connBloc,
			dashboardBloc: dashBloc,
			alertBloc: alertBloc,
			configBloc: configBloc,
			webrtcBloc: webrtcBloc,
			child: const MainNavigationScreen(),
		);
	}

	group('MainNavigationScreen Widget Tests (W-NAV-01..04)', () {
		testWidgets('W-NAV-01: Displays all 4 navigation destinations', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			expect(find.text('Tổng quan'), findsWidgets);
			expect(find.text('Camera POV'), findsOneWidget);
			expect(find.text('Cảnh báo'), findsOneWidget);
			expect(find.text('Cài đặt'), findsOneWidget);
		});

		testWidgets('W-NAV-02: Defaults to Tổng quan (index 0) with dashboard content', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			final stack = tester.widget<IndexedStack>(find.byType(IndexedStack));
			expect(stack.index, equals(0));
			expect(find.text('Thiết bị Pi 4'), findsOneWidget);
		});

		testWidgets('W-NAV-03: Tapping destinations on NavigationBar switches IndexedStack index', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			// Tap Camera POV (index 1)
			await tester.tap(find.text('Camera POV'));
			await tester.pump();
			var stack = tester.widget<IndexedStack>(find.byType(IndexedStack));
			expect(stack.index, equals(1));

			// Tap Cảnh báo (index 2)
			await tester.tap(find.text('Cảnh báo'));
			await tester.pump();
			stack = tester.widget<IndexedStack>(find.byType(IndexedStack));
			expect(stack.index, equals(2));
			expect(find.text('Lịch sử Cảnh báo'), findsOneWidget);

			// Tap Cài đặt (index 3)
			await tester.tap(find.text('Cài đặt'));
			await tester.pump();
			stack = tester.widget<IndexedStack>(find.byType(IndexedStack));
			expect(stack.index, equals(3));
			expect(find.text('Cài đặt & Điều khiển'), findsOneWidget);

			// Tap Tổng quan (index 0)
			await tester.tap(find.text('Tổng quan').last);
			await tester.pump();
			stack = tester.widget<IndexedStack>(find.byType(IndexedStack));
			expect(stack.index, equals(0));
		});

		testWidgets('W-NAV-04: Tapping camera card from dashboard switches to Camera POV (index 1)', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			final cameraCard = find.text('Xem Camera Trực Tiếp');
			expect(cameraCard, findsOneWidget);

			await tester.tap(cameraCard);
			await tester.pump();

			final stack = tester.widget<IndexedStack>(find.byType(IndexedStack));
			expect(stack.index, equals(1));
		});

		testWidgets('W-NAV-05: Wide screen (>= 900px) displays NavigationRail', (tester) async {
			tester.view.physicalSize = const Size(1200, 800);
			tester.view.devicePixelRatio = 1.0;
			addTearDown(() {
				tester.view.resetPhysicalSize();
				tester.view.resetDevicePixelRatio();
			});

			await tester.pumpWidget(createScreen());
			await tester.pump();

			expect(find.byType(NavigationRail), findsOneWidget);
			expect(find.byType(NavigationBar), findsNothing);
		});
	});
}
