import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/presentation/widgets/battery_indicator.dart';
import 'package:pbl6_app/presentation/widgets/metric_tile.dart';

void main() {
	group('BatteryIndicator Widget Tests (W-BAT-01..04)', () {
		testWidgets('W-BAT-01: High battery levels render green color and corresponding icons', (tester) async {
			for (final level in [95, 75, 55]) {
				await tester.pumpWidget(
					MaterialApp(
						home: Scaffold(body: BatteryIndicator(percentage: level)),
					),
				);
				expect(find.text('$level%'), findsOneWidget);
				final textWidget = tester.widget<Text>(find.text('$level%'));
				expect(textWidget.style?.color, equals(Colors.green));
				if (level >= 90) {
					expect(find.byIcon(Icons.battery_full), findsOneWidget);
				} else if (level >= 70) {
					expect(find.byIcon(Icons.battery_6_bar), findsOneWidget);
				} else {
					expect(find.byIcon(Icons.battery_5_bar), findsOneWidget);
				}
			}
		});

		testWidgets('W-BAT-02: Medium battery levels render orange color and corresponding icons', (tester) async {
			for (final level in [35, 22]) {
				await tester.pumpWidget(
					MaterialApp(
						home: Scaffold(body: BatteryIndicator(percentage: level)),
					),
				);
				expect(find.text('$level%'), findsOneWidget);
				final textWidget = tester.widget<Text>(find.text('$level%'));
				expect(textWidget.style?.color, equals(Colors.orange));
				if (level >= 30) {
					expect(find.byIcon(Icons.battery_3_bar), findsOneWidget);
				} else {
					expect(find.byIcon(Icons.battery_2_bar), findsOneWidget);
				}
			}
		});

		testWidgets('W-BAT-03: Low battery levels (< 15%) render red color and battery_alert icon', (tester) async {
			await tester.pumpWidget(
				const MaterialApp(
					home: Scaffold(body: BatteryIndicator(percentage: 10)),
				),
			);
			expect(find.text('10%'), findsOneWidget);
			final textWidget = tester.widget<Text>(find.text('10%'));
			expect(textWidget.style?.color, equals(Colors.red));
			expect(find.byIcon(Icons.battery_alert), findsOneWidget);
		});

		testWidgets('W-BAT-04: Stale battery indicator displays grey color regardless of percentage', (tester) async {
			await tester.pumpWidget(
				const MaterialApp(
					home: Scaffold(body: BatteryIndicator(percentage: 85, isStale: true)),
				),
			);
			expect(find.text('85%'), findsOneWidget);
			final textWidget = tester.widget<Text>(find.text('85%'));
			expect(textWidget.style?.color, equals(Colors.grey));
		});
	});

	group('MetricTile Widget Tests (W-MET-01..03)', () {
		testWidgets('W-MET-01: MetricTile displays title, value, unit, icon, color and subtitle', (tester) async {
			await tester.pumpWidget(
				const MaterialApp(
					home: Scaffold(
						body: MetricTile(
							title: 'Vật cản gần nhất',
							value: '25.0',
							unit: 'cm',
							icon: Icons.radar,
							color: Colors.red,
							subtitle: 'CẢNH BÁO QUÁ GẦN',
						),
					),
				),
			);
			expect(find.text('Vật cản gần nhất'), findsOneWidget);
			expect(find.text('25.0'), findsOneWidget);
			expect(find.text('cm'), findsOneWidget);
			expect(find.text('CẢNH BÁO QUÁ GẦN'), findsOneWidget);
			expect(find.byIcon(Icons.radar), findsOneWidget);
		});

		testWidgets('W-MET-02: MetricTile renders safely without subtitle or unit', (tester) async {
			await tester.pumpWidget(
				const MaterialApp(
					home: Scaffold(
						body: MetricTile(
							title: 'Tải CPU',
							value: '45',
							icon: Icons.memory,
						),
					),
				),
			);
			expect(find.text('Tải CPU'), findsOneWidget);
			expect(find.text('45'), findsOneWidget);
			expect(find.byIcon(Icons.memory), findsOneWidget);
		});

		testWidgets('W-MET-03: MetricTile handles extreme value (9999.0 cm) in confined box without overflow', (tester) async {
			await tester.pumpWidget(
				const MaterialApp(
					home: Scaffold(
						body: SizedBox(
							width: 140,
							height: 100,
							child: MetricTile(
								title: 'Vật cản gần nhất',
								value: '9999.0',
								unit: 'cm',
								icon: Icons.radar,
								subtitle: 'Khoảng cách an toàn',
							),
						),
					),
				),
			);
			expect(tester.takeException(), isNull);
			expect(find.text('9999.0'), findsOneWidget);
			expect(find.text('cm'), findsOneWidget);
		});
	});
}
