import 'package:flutter/material.dart';

class MetricTile extends StatelessWidget {
	final String title;
	final String value;
	final String? unit;
	final IconData icon;
	final Color? color;
	final String? subtitle;

	const MetricTile({
		super.key,
		required this.title,
		required this.value,
		this.unit,
		required this.icon,
		this.color,
		this.subtitle,
	});

	@override
	Widget build(BuildContext context) {
		final effectiveColor = color ?? Theme.of(context).colorScheme.primary;
		return Card(
			elevation: 1,
			shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
			child: Padding(
				padding: const EdgeInsets.all(12),
				child: Column(
					crossAxisAlignment: CrossAxisAlignment.start,
					mainAxisAlignment: MainAxisAlignment.spaceBetween,
					children: [
						Row(
							mainAxisAlignment: MainAxisAlignment.spaceBetween,
							children: [
								Expanded(
									child: Text(
										title,
										style: Theme.of(context).textTheme.labelMedium?.copyWith(
											color: Colors.grey[700],
										),
										maxLines: 1,
										overflow: TextOverflow.ellipsis,
									),
								),
								Icon(icon, color: effectiveColor, size: 20),
							],
						),
						const SizedBox(height: 8),
						Row(
							crossAxisAlignment: CrossAxisAlignment.baseline,
							textBaseline: TextBaseline.alphabetic,
							children: [
								Text(
									value,
									style: TextStyle(
										fontSize: 22,
										fontWeight: FontWeight.bold,
										color: effectiveColor,
									),
								),
								if (unit != null) ...[
									const SizedBox(width: 4),
									Text(
										unit!,
										style: TextStyle(
											fontSize: 13,
											color: Colors.grey[600],
										),
									),
								],
							],
						),
						if (subtitle != null) ...[
							const SizedBox(height: 4),
							Text(
								subtitle!,
								style: TextStyle(fontSize: 11, color: Colors.grey[500]),
								maxLines: 1,
								overflow: TextOverflow.ellipsis,
							),
						],
					],
				),
			),
		);
	}
}
