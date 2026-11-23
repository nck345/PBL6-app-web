import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/presentation/bloc/alerts/alert_bloc.dart';
import 'package:pbl6_app/presentation/screens/alert_history_screen.dart';
import '../helpers/test_fakes.dart';

void main() {
	late FakeAlertRepository fakeAlertRepo;
	late FakeNotificationService fakeNotif;
	late AlertBloc alertBloc;

	setUp(() {
		fakeAlertRepo = FakeAlertRepository();
		fakeNotif = FakeNotificationService();
		alertBloc = AlertBloc(alertRepository: fakeAlertRepo, notificationService: fakeNotif);
	});

	tearDown(() async {
		await alertBloc.close();
		fakeAlertRepo.dispose();
	});

	Widget createScreen() {
		return buildTestApp(
			alertBloc: alertBloc,
			child: const AlertHistoryScreen(),
		);
	}

	group('AlertHistoryScreen Widget Tests (W-HIST-01..09)', () {
		testWidgets('W-HIST-01: Displays empty state placeholder when no alerts present', (tester) async {
			alertBloc.emit(AlertEmpty());
			await tester.pumpWidget(createScreen());

			expect(find.byIcon(Icons.notifications_none), findsOneWidget);
			expect(find.text('Chưa ghi nhận cảnh báo nguy hiểm nào'), findsOneWidget);
		});

		testWidgets('W-HIST-02: Displays list of alert cards with message, timestamp and distance badge', (tester) async {
			final alert = createTestAlert(
				eventId: 'evt_101',
				message: 'Vật cản bậc thềm',
				distanceCm: 32.5,
				timestamp: 1732312000,
			);
			fakeAlertRepo.emitAlert(alert);
			alertBloc.add(const StartAlertSubscription());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pumpWidget(createScreen());

			expect(find.text('Vật cản bậc thềm'), findsOneWidget);
			expect(find.text('32.5 cm'), findsOneWidget);
			expect(find.textContaining(':'), findsWidgets);
		});

		testWidgets('W-HIST-03: CRITICAL alert renders red avatar, warning icon and red distance badge', (tester) async {
			final alert = createTestAlert(
				level: 'CRITICAL',
				distanceCm: 25.0,
			);
			fakeAlertRepo.emitAlert(alert);
			alertBloc.add(const StartAlertSubscription());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pumpWidget(createScreen());

			expect(find.byIcon(Icons.warning), findsOneWidget);
			expect(find.text('25.0 cm'), findsOneWidget);
		});

		testWidgets('W-HIST-04: WARNING alert renders amber avatar, info icon and amber distance badge', (tester) async {
			final alert = createTestAlert(
				level: 'WARNING',
				distanceCm: 70.0,
			);
			fakeAlertRepo.emitAlert(alert);
			alertBloc.add(const StartAlertSubscription());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pumpWidget(createScreen());

			expect(find.byIcon(Icons.info), findsOneWidget);
			expect(find.text('70.0 cm'), findsOneWidget);
		});

		testWidgets('W-HIST-05: Unacknowledged alert displays bold text and checkmark IconButton', (tester) async {
			final alert = createTestAlert(isAcknowledged: false, message: 'Chưa xác nhận');
			fakeAlertRepo.emitAlert(alert);
			alertBloc.add(const StartAlertSubscription());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pumpWidget(createScreen());

			final textWidget = tester.widget<Text>(find.text('Chưa xác nhận'));
			expect(textWidget.style?.fontWeight, equals(FontWeight.bold));
			expect(find.byIcon(Icons.check), findsOneWidget);
		});

		testWidgets('W-HIST-06: Tapping checkmark IconButton dispatches AcknowledgeAlert', (tester) async {
			final alert = createTestAlert(eventId: 'evt_ack_1', isAcknowledged: false);
			fakeAlertRepo.emitAlert(alert);
			alertBloc.add(const StartAlertSubscription());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pumpWidget(createScreen());

			await tester.tap(find.byIcon(Icons.check));
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pump();

			expect(alertBloc.state, isA<AlertActive>());
			final state = alertBloc.state as AlertActive;
			expect(state.latestAlert.isAcknowledged, isTrue);
			expect(find.byIcon(Icons.check_circle), findsOneWidget);
		});

		testWidgets('W-HIST-07: Acknowledged alert displays normal text font and check_circle icon', (tester) async {
			final alert = createTestAlert(isAcknowledged: true, message: 'Đã xác nhận');
			fakeAlertRepo.emitAlert(alert);
			alertBloc.add(const StartAlertSubscription());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pumpWidget(createScreen());

			final textWidget = tester.widget<Text>(find.text('Đã xác nhận'));
			expect(textWidget.style?.fontWeight, equals(FontWeight.normal));
			expect(find.byIcon(Icons.check_circle), findsOneWidget);
		});

		testWidgets('W-HIST-08: Renders chips for detectedObjects', (tester) async {
			final alert = createTestAlert(detectedObjects: ['motorcycle', 'tree']);
			fakeAlertRepo.emitAlert(alert);
			alertBloc.add(const StartAlertSubscription());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pumpWidget(createScreen());

			expect(find.text('motorcycle'), findsOneWidget);
			expect(find.text('tree'), findsOneWidget);
		});

		testWidgets('W-HIST-09: Tapping delete_sweep button clears history and shows empty state', (tester) async {
			final alert = createTestAlert();
			fakeAlertRepo.emitAlert(alert);
			alertBloc.add(const StartAlertSubscription());
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pumpWidget(createScreen());

			expect(find.text(alert.message), findsOneWidget);

			await tester.tap(find.byIcon(Icons.delete_sweep));
			await tester.runAsync(() async {
				await Future.delayed(const Duration(milliseconds: 20));
			});
			await tester.pump();

			expect(alertBloc.state, isA<AlertEmpty>());
			expect(find.text('Chưa ghi nhận cảnh báo nguy hiểm nào'), findsOneWidget);
		});
	});
}
