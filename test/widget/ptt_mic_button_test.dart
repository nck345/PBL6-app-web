import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/presentation/bloc/webrtc/webrtc_bloc.dart';
import 'package:pbl6_app/presentation/widgets/ptt_mic_button.dart';
import '../helpers/test_fakes.dart';

void main() {
	late FakeWebrtcDatasource fakeDatasource;
	late WebRtcBloc bloc;

	setUp(() {
		setupMockPermissionHandler(isGranted: true);
		fakeDatasource = FakeWebrtcDatasource();
		bloc = WebRtcBloc(webrtcDatasource: fakeDatasource);
	});

	tearDown(() async {
		clearMockPermissionHandler();
		await bloc.close();
		await fakeDatasource.dispose();
	});

	group('PttMicButton Widget Tests (W-PTT-01..07)', () {
		testWidgets('W-PTT-01: Disabled state when WebRTC is not connected', (tester) async {
			await tester.pumpWidget(
				buildTestApp(
					webrtcBloc: bloc,
					child: const Scaffold(body: Center(child: PttMicButton())),
				),
			);

			expect(find.text('GIỮ ĐỂ NÓI'), findsOneWidget);
			expect(find.byIcon(Icons.mic_none), findsOneWidget);

			final gesture = await tester.startGesture(tester.getCenter(find.byType(PttMicButton)));
			await tester.pump();
			await gesture.up();
			await tester.pump();

			expect(bloc.state, isA<WebRtcInitial>());
		});

		testWidgets('W-PTT-02: Ready state when WebRTC is connected', (tester) async {
			bloc.emit(WebRtcConnected(renderer: fakeDatasource.fakeRenderer, isPttActive: false));
			await tester.pumpWidget(
				buildTestApp(
					webrtcBloc: bloc,
					child: const Scaffold(body: Center(child: PttMicButton())),
				),
			);

			expect(find.text('GIỮ ĐỂ NÓI'), findsOneWidget);
			expect(find.byIcon(Icons.mic_none), findsOneWidget);
		});

		testWidgets('W-PTT-03: Hold down (onTapDown) with mic permission dispatches PTT talking true', (tester) async {
			bloc.emit(WebRtcConnected(renderer: fakeDatasource.fakeRenderer, isPttActive: false));
			await tester.pumpWidget(
				buildTestApp(
					webrtcBloc: bloc,
					child: const Scaffold(body: Center(child: PttMicButton())),
				),
			);

			final gesture = await tester.startGesture(tester.getCenter(find.byType(PttMicButton)));
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();

			expect(bloc.state, isA<WebRtcConnected>());
			final state = bloc.state as WebRtcConnected;
			expect(state.isPttActive, isTrue);
			expect(find.text('ĐANG NÓI'), findsOneWidget);
			expect(find.byIcon(Icons.mic), findsOneWidget);

			await gesture.up();
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();
		});

		testWidgets('W-PTT-04: Release (onTapUp) dispatches PTT talking false', (tester) async {
			bloc.emit(WebRtcConnected(renderer: fakeDatasource.fakeRenderer, isPttActive: false));
			await tester.pumpWidget(
				buildTestApp(
					webrtcBloc: bloc,
					child: const Scaffold(body: Center(child: PttMicButton())),
				),
			);

			final gesture = await tester.startGesture(tester.getCenter(find.byType(PttMicButton)));
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();
			expect((bloc.state as WebRtcConnected).isPttActive, isTrue);

			await gesture.up();
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();

			expect((bloc.state as WebRtcConnected).isPttActive, isFalse);
			expect(find.text('GIỮ ĐỂ NÓI'), findsOneWidget);
			expect(find.byIcon(Icons.mic_none), findsOneWidget);
		});

		testWidgets('W-PTT-05: Cancel (onTapCancel) returns button to idle state', (tester) async {
			bloc.emit(WebRtcConnected(renderer: fakeDatasource.fakeRenderer, isPttActive: false));
			await tester.pumpWidget(
				buildTestApp(
					webrtcBloc: bloc,
					child: const Scaffold(body: Center(child: PttMicButton())),
				),
			);

			final gesture = await tester.startGesture(tester.getCenter(find.byType(PttMicButton)));
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();
			expect((bloc.state as WebRtcConnected).isPttActive, isTrue);

			await gesture.cancel();
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();

			expect((bloc.state as WebRtcConnected).isPttActive, isFalse);
			expect(find.text('GIỮ ĐỂ NÓI'), findsOneWidget);
		});

		testWidgets('W-PTT-06: Permission denied shows SnackBar and prevents talking', (tester) async {
			setupMockPermissionHandler(isGranted: false);
			bloc.emit(WebRtcConnected(renderer: fakeDatasource.fakeRenderer, isPttActive: false));
			await tester.pumpWidget(
				buildTestApp(
					webrtcBloc: bloc,
					child: const Scaffold(body: Center(child: PttMicButton())),
				),
			);

			final gesture = await tester.startGesture(tester.getCenter(find.byType(PttMicButton)));
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();

			expect(find.text('Vui lòng cấp quyền Microphone để đàm thoại'), findsOneWidget);
			expect((bloc.state as WebRtcConnected).isPttActive, isFalse);

			await gesture.up();
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();
		});

		testWidgets('W-PTT-07: Rapid touch-and-release (fast tap) does not leave mic stuck in talking state', (tester) async {
			bloc.emit(WebRtcConnected(renderer: fakeDatasource.fakeRenderer, isPttActive: false));
			await tester.pumpWidget(
				buildTestApp(
					webrtcBloc: bloc,
					child: const Scaffold(body: Center(child: PttMicButton())),
				),
			);

			final gesture = await tester.startGesture(tester.getCenter(find.byType(PttMicButton)));
			await gesture.up();

			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 50));
			});
			await tester.pump();

			expect((bloc.state as WebRtcConnected).isPttActive, isFalse);
			expect(find.text('GIỮ ĐỂ NÓI'), findsOneWidget);
		});
	});
}
