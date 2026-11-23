import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:pbl6_app/core/constants/app_constants.dart';
import 'package:pbl6_app/presentation/bloc/dashboard/dashboard_bloc.dart';
import 'package:pbl6_app/presentation/bloc/webrtc/webrtc_bloc.dart';
import 'package:pbl6_app/presentation/screens/live_monitor_screen.dart';
import 'package:pbl6_app/presentation/widgets/ptt_mic_button.dart';
import '../helpers/test_fakes.dart';

void main() {
	late FakeWebrtcDatasource fakeWebrtc;
	late FakeTelemetryRepository fakeTelemetryRepo;
	late WebRtcBloc webrtcBloc;
	late DashboardBloc dashBloc;

	setUp(() {
		setupMockPermissionHandler(isGranted: true);
		fakeWebrtc = FakeWebrtcDatasource();
		fakeTelemetryRepo = FakeTelemetryRepository();
		webrtcBloc = WebRtcBloc(webrtcDatasource: fakeWebrtc);
		dashBloc = DashboardBloc(telemetryRepository: fakeTelemetryRepo);
	});

	tearDown(() async {
		clearMockPermissionHandler();
		await webrtcBloc.close();
		await dashBloc.close();
		await fakeWebrtc.dispose();
		fakeTelemetryRepo.dispose();
	});

	Widget createScreen({String deviceId = AppConstants.defaultDeviceId}) {
		return buildTestApp(
			webrtcBloc: webrtcBloc,
			dashboardBloc: dashBloc,
			child: LiveMonitorScreen(deviceId: deviceId),
		);
	}

	group('LiveMonitorScreen Widget Tests (W-LIVE-01..11)', () {
		testWidgets('W-LIVE-01: Auto-connects WebRTC on initial screen load', (tester) async {
			await tester.pumpWidget(createScreen());
			await tester.pump();
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pump();

			expect(webrtcBloc.state, isA<WebRtcConnected>());
		});

		testWidgets('W-LIVE-02: Displays loading spinner and negotiation label during WebRtcConnecting', (tester) async {
			webrtcBloc.emit(const WebRtcConnecting());
			await tester.pumpWidget(createScreen());

			expect(find.text('Đang bắt tay WebRTC P2P...'), findsOneWidget);
			expect(find.byType(CircularProgressIndicator), findsOneWidget);
		});

		testWidgets('W-LIVE-03: Renders RTCVideoView when WebRtcConnected', (tester) async {
			webrtcBloc.emit(WebRtcConnected(renderer: fakeWebrtc.fakeRenderer, isPttActive: false));
			await tester.pumpWidget(createScreen());

			expect(find.byType(RTCVideoView), findsOneWidget);
		});

		testWidgets('W-LIVE-04: Displays error message and retry button on WebRtcFailure', (tester) async {
			webrtcBloc.emit(const WebRtcFailure(message: 'Lỗi bắt tay ICE'));
			await tester.pumpWidget(createScreen());

			expect(find.text('Lỗi bắt tay ICE'), findsOneWidget);
			expect(find.byIcon(Icons.error_outline), findsOneWidget);

			final retryBtn = find.text('Thử lại');
			expect(retryBtn, findsOneWidget);

			await tester.tap(retryBtn);
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pump();

			expect(webrtcBloc.state, isA<WebRtcConnected>());
		});

		testWidgets('W-LIVE-05: Displays camera off icon and start button on WebRtcDisconnected', (tester) async {
			webrtcBloc.emit(const WebRtcDisconnected());
			await tester.pumpWidget(createScreen());

			expect(find.byIcon(Icons.videocam_off), findsOneWidget);
			expect(find.text('Chưa kết nối luồng video'), findsOneWidget);

			final startBtn = find.text('Bật Camera');
			expect(startBtn, findsOneWidget);

			await tester.tap(startBtn);
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pump();

			expect(webrtcBloc.state, isA<WebRtcConnected>());
		});

		testWidgets('W-LIVE-06: AppBar refresh button dispatches ConnectWebRtcEvent', (tester) async {
			webrtcBloc.emit(const WebRtcDisconnected());
			await tester.pumpWidget(createScreen());

			final refreshBtn = find.byTooltip('Kết nối lại luồng WebRTC');
			expect(refreshBtn, findsOneWidget);

			await tester.tap(refreshBtn);
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pump();

			expect(webrtcBloc.state, isA<WebRtcConnected>());
		});

		testWidgets('W-LIVE-07: Obstacle HUD overlay turns red with danger label when dist < 60cm', (tester) async {
			webrtcBloc.emit(WebRtcConnected(renderer: fakeWebrtc.fakeRenderer, isPttActive: false));
			final tel = createTestTelemetry(ultrasonicDistanceCm: 35.0);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());

			expect(find.textContaining('Vật cản: 35.0 cm - NGUY HIỂM'), findsOneWidget);
			expect(find.byIcon(Icons.warning), findsOneWidget);
		});

		testWidgets('W-LIVE-08: Obstacle HUD overlay shows dark pill with radar icon when dist >= 60cm', (tester) async {
			webrtcBloc.emit(WebRtcConnected(renderer: fakeWebrtc.fakeRenderer, isPttActive: false));
			final tel = createTestTelemetry(ultrasonicDistanceCm: 120.0);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());

			expect(find.textContaining('Vật cản: 120.0 cm'), findsOneWidget);
			expect(find.textContaining('- NGUY HIỂM'), findsNothing);
			expect(find.byIcon(Icons.radar), findsOneWidget);
		});

		testWidgets('W-LIVE-08b: Obstacle HUD displays disconnected text when sensor is not connected', (tester) async {
			webrtcBloc.emit(WebRtcConnected(renderer: fakeWebrtc.fakeRenderer, isPttActive: false));
			final tel = createTestTelemetry(ultrasonicDistanceCm: -1.0);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());

			expect(find.text('Cảm biến khoảng cách: Chưa kết nối'), findsOneWidget);
			expect(find.byIcon(Icons.sensors_off), findsOneWidget);
		});

		testWidgets('W-LIVE-09: Obstacle HUD is hidden when DashboardInitial', (tester) async {
			webrtcBloc.emit(WebRtcConnected(renderer: fakeWebrtc.fakeRenderer, isPttActive: false));
			await tester.pumpWidget(createScreen());

			expect(find.byIcon(Icons.radar), findsNothing);
			expect(find.byIcon(Icons.warning), findsNothing);
		});

		testWidgets('W-LIVE-10: Displays instruction text and PttMicButton at bottom', (tester) async {
			webrtcBloc.emit(WebRtcConnected(renderer: fakeWebrtc.fakeRenderer, isPttActive: false));
			await tester.pumpWidget(createScreen());

			expect(find.text('Nhấn giữ nút mic để nói qua loa Raspberry Pi'), findsOneWidget);
			expect(find.byType(PttMicButton), findsOneWidget);
		});

		testWidgets('W-LIVE-11: Renders safely on narrow 320x640 screen without RenderFlex overflow', (tester) async {
			tester.view.physicalSize = const Size(320, 640);
			tester.view.devicePixelRatio = 1.0;
			addTearDown(() {
				tester.view.resetPhysicalSize();
				tester.view.resetDevicePixelRatio();
			});

			webrtcBloc.emit(WebRtcConnected(renderer: fakeWebrtc.fakeRenderer, isPttActive: false));
			await tester.pumpWidget(createScreen());

			expect(tester.takeException(), isNull);
			expect(find.text('Nhấn giữ nút mic để nói qua loa Raspberry Pi'), findsOneWidget);
		});

		testWidgets('W-LIVE-12: Displays GPS overlay pill with coordinates when GPS fix is active', (tester) async {
			webrtcBloc.emit(WebRtcConnected(renderer: fakeWebrtc.fakeRenderer, isPttActive: false));
			final tel = createTestTelemetry(
				latitude: 16.0738,
				longitude: 108.1499,
				hasGpsFix: true,
			);
			dashBloc.emit(DashboardLoaded(telemetry: tel));
			await tester.pumpWidget(createScreen());

			expect(find.textContaining('16.0738°, 108.1499°'), findsOneWidget);
			expect(find.byIcon(Icons.location_on), findsOneWidget);
		});
	});
}
