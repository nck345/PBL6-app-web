import 'package:flutter/material.dart';

class BatteryIndicator extends StatelessWidget {
	final int percentage;
	final bool isStale;
	const BatteryIndicator({
		super.key,
		required this.percentage,
		this.isStale = false,
	});

	Color _getColor(BuildContext context) {
		if (isStale) return Colors.grey;
		if (percentage >= 50) return Colors.green;
		if (percentage >= 20) return Colors.orange;
		return Colors.red;
	}

	IconData _getIcon() {
		if (percentage >= 90) return Icons.battery_full;
		if (percentage >= 70) return Icons.battery_6_bar;
		if (percentage >= 50) return Icons.battery_5_bar;
		if (percentage >= 30) return Icons.battery_3_bar;
		if (percentage >= 15) return Icons.battery_2_bar;
		return Icons.battery_alert;
	}

	@override
	Widget build(BuildContext context) {
		final color = _getColor(context);
		return Row(
			mainAxisSize: MainAxisSize.min,
			children: [
				Icon(_getIcon(), color: color, size: 22),
				const SizedBox(width: 4),
				Text(
					'$percentage%',
					style: TextStyle(
						color: color,
						fontWeight: FontWeight.bold,
						fontSize: 14,
					),
				),
			],
		);
	}
}
