import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/core/constants/app_constants.dart';
import 'package:pbl6_app/presentation/bloc/dashboard/dashboard_bloc.dart';
import 'package:pbl6_app/presentation/screens/gps_map_screen.dart';
import '../helpers/test_fakes.dart';

void main() {
	late FakeTelemetryRepository fakeTelemetryRepo;
	late DashboardBloc dashBloc;

	setUp(() {
		fakeTelemetryRepo = FakeTelemetryRepository();
		dashBloc = DashboardBloc(telemetryRepository: fakeTelemetryRepo);
	});

	tearDown(() async {
		await dashBloc.close();
		fakeTelemetryRepo.dispose();
	});

	Widget createScreen({String deviceId = AppConstants.defaultDeviceId}) {
		return buildTestApp(
			dashboardBloc: dashBloc,
			child: GpsMapScreen(deviceId: deviceId),
		);
	}

	group('GpsMapScreen Widget Tests (W-MAP-01..06)', () {
		testWidgets('W-MAP-01: Displays AppBar with title and device ID', (tester) async {
			await tester.pumpWidget(createScreen(deviceId: 'pi4_01'));
			await tester.pump();

			expect(find.text('Bản đồ Giám sát GPS'), findsOneWidget);
			expect(find.text('Thiết bị: pi4_01'), findsOneWidget);
		});

		testWidgets('W-MAP-02: Displays GPS fix status chip with satellites when available', (tester) async {
			final tel = createTestTelemetry(
				latitude: 16.0738,
				longitude: 108.1499,
				hasGpsFix: true,
				satellites: 8,
			);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());
			await tester.pump();

			expect(find.text('Đã định vị (8 vệ tinh)'), findsOneWidget);
			expect(find.byIcon(Icons.gps_fixed), findsOneWidget);
		});

		testWidgets('W-MAP-03: Displays missing GPS chip when fix is lost', (tester) async {
			final tel = createTestTelemetry(
				hasGpsFix: false,
				latitude: null,
				longitude: null,
			);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());
			await tester.pump();

			expect(find.text('Mất GPS'), findsOneWidget);
			expect(find.byIcon(Icons.gps_not_fixed), findsOneWidget);
		});

		testWidgets('W-MAP-04: Renders FlutterMap and floating control buttons', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();

			expect(find.byType(FlutterMap), findsOneWidget);
			expect(find.byIcon(Icons.my_location), findsOneWidget);
			expect(find.byIcon(Icons.add), findsOneWidget);
			expect(find.byIcon(Icons.remove), findsOneWidget);
			expect(find.byIcon(Icons.timeline), findsOneWidget);
		});

		testWidgets('W-MAP-05: Bottom card displays location, speed, altitude, and Google Maps action', (tester) async {
			final tel = createTestTelemetry(
				latitude: 16.0738,
				longitude: 108.1499,
				hasGpsFix: true,
				speedKmh: 3.5,
				altitudeM: 14.2,
				headingDegrees: 90.0,
			);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());
			await tester.pump();

			expect(find.text('16.073800°, 108.149900°'), findsOneWidget);
			expect(find.text('3.5 km/h'), findsOneWidget);
			expect(find.textContaining('Độ cao: 14.2m | Hướng: 90°'), findsOneWidget);
			expect(find.text('Google Maps'), findsOneWidget);
		});

		testWidgets('W-MAP-06: Renders safely on narrow 320x640 screen without overflow', (tester) async {
			tester.view.physicalSize = const Size(320, 640);
			tester.view.devicePixelRatio = 1.0;
			addTearDown(() {
				tester.view.resetPhysicalSize();
				tester.view.resetDevicePixelRatio();
			});

			final tel = createTestTelemetry(
				latitude: 16.0738,
				longitude: 108.1499,
				hasGpsFix: true,
			);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());
			await tester.pump();

			expect(tester.takeException(), isNull);
			expect(find.text('Bản đồ Giám sát GPS'), findsOneWidget);
		});
	});
}
