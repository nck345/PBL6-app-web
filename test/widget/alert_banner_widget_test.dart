import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/presentation/widgets/alert_banner_widget.dart';
import '../helpers/test_fakes.dart';

void main() {
	group('AlertBannerWidget Tests (W-BAN-01..05)', () {
		testWidgets('W-BAN-01: CRITICAL alert renders hazard header, red background and warning icon', (tester) async {
			final alert = createTestAlert(
				level: 'CRITICAL',
				message: 'Bậc thang nguy hiểm',
				distanceCm: 25.0,
			);
			await tester.pumpWidget(
				MaterialApp(
					home: Scaffold(body: AlertBannerWidget(alert: alert)),
				),
			);

			expect(find.text('CẢNH BÁO NGUY HIỂM'), findsOneWidget);
			expect(find.byIcon(Icons.warning_amber_rounded), findsOneWidget);
			expect(find.textContaining('Bậc thang nguy hiểm'), findsOneWidget);
			expect(find.textContaining('25.0 cm'), findsOneWidget);
		});

		testWidgets('W-BAN-02: WARNING alert renders obstacle header, amber background and info icon', (tester) async {
			final alert = createTestAlert(
				level: 'WARNING',
				message: 'Vật cản phía trước',
				distanceCm: 65.0,
			);
			await tester.pumpWidget(
				MaterialApp(
					home: Scaffold(body: AlertBannerWidget(alert: alert)),
				),
			);

			expect(find.text('CẢNH BÁO VẬT CẢN'), findsOneWidget);
			expect(find.byIcon(Icons.info_outline), findsOneWidget);
			expect(find.textContaining('Vật cản phía trước'), findsOneWidget);
			expect(find.textContaining('65.0 cm'), findsOneWidget);
		});

		testWidgets('W-BAN-03: Renders chips for detectedObjects list', (tester) async {
			final alert = createTestAlert(
				detectedObjects: ['stairs_down', 'puddle', 'chair'],
			);
			await tester.pumpWidget(
				MaterialApp(
					home: Scaffold(body: AlertBannerWidget(alert: alert)),
				),
			);

			expect(find.text('stairs_down'), findsOneWidget);
			expect(find.text('puddle'), findsOneWidget);
			expect(find.text('chair'), findsOneWidget);
		});

		testWidgets('W-BAN-04: Tapping checkmark button invokes onAcknowledge callback', (tester) async {
			bool acknowledged = false;
			final alert = createTestAlert(isAcknowledged: false);
			await tester.pumpWidget(
				MaterialApp(
					home: Scaffold(
						body: AlertBannerWidget(
							alert: alert,
							onAcknowledge: () => acknowledged = true,
						),
					),
				),
			);

			final checkmarkBtn = find.byIcon(Icons.check);
			expect(checkmarkBtn, findsOneWidget);
			await tester.tap(checkmarkBtn);
			await tester.pump();

			expect(acknowledged, isTrue);
		});

		testWidgets('W-BAN-05: Checkmark button is hidden when alert is acknowledged or callback is null', (tester) async {
			final ackAlert = createTestAlert(isAcknowledged: true);
			await tester.pumpWidget(
				MaterialApp(
					home: Scaffold(
						body: AlertBannerWidget(
							alert: ackAlert,
							onAcknowledge: () {},
						),
					),
				),
			);
			expect(find.byIcon(Icons.check), findsNothing);

			final unackAlert = createTestAlert(isAcknowledged: false);
			await tester.pumpWidget(
				MaterialApp(
					home: Scaffold(
						body: AlertBannerWidget(
							alert: unackAlert,
							onAcknowledge: null,
						),
					),
				),
			);
			expect(find.byIcon(Icons.check), findsNothing);
		});
	});
}
