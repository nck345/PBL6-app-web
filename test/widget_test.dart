import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/presentation/widgets/battery_indicator.dart';
import 'package:pbl6_app/presentation/widgets/metric_tile.dart';

void main() {
	testWidgets('BatteryIndicator displays percentage correctly', (WidgetTester tester) async {
		await tester.pumpWidget(
			const MaterialApp(
				home: Scaffold(
					body: BatteryIndicator(percentage: 85),
				),
			),
		);

		expect(find.text('85%'), findsOneWidget);
		expect(find.byIcon(Icons.battery_6_bar), findsOneWidget);
	});

	testWidgets('MetricTile displays title, value and unit', (WidgetTester tester) async {
		await tester.pumpWidget(
			const MaterialApp(
				home: Scaffold(
					body: MetricTile(
						title: 'Khoảng cách',
						value: '145.2',
						unit: 'cm',
						icon: Icons.radar,
					),
				),
			),
		);

		expect(find.text('Khoảng cách'), findsOneWidget);
		expect(find.text('145.2'), findsOneWidget);
		expect(find.text('cm'), findsOneWidget);
		expect(find.byIcon(Icons.radar), findsOneWidget);
	});
}
