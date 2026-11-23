import 'package:flutter/material.dart';
import '../../domain/entities/alert_entity.dart';

class AlertBannerWidget extends StatelessWidget {
	final AlertEntity alert;
	final VoidCallback? onAcknowledge;

	const AlertBannerWidget({
		super.key,
		required this.alert,
		this.onAcknowledge,
	});

	@override
	Widget build(BuildContext context) {
		final isCritical = alert.level.toUpperCase() == 'CRITICAL';
		final bgColor = isCritical ? Colors.red.shade700 : Colors.amber.shade800;

		return Container(
			margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
			padding: const EdgeInsets.all(12),
			decoration: BoxDecoration(
				color: bgColor,
				borderRadius: BorderRadius.circular(10),
				boxShadow: [
					BoxShadow(
						color: bgColor.withValues(alpha: 0.4),
						blurRadius: 8,
						offset: const Offset(0, 3),
					),
				],
			),
			child: Row(
				children: [
					Icon(
						isCritical ? Icons.warning_amber_rounded : Icons.info_outline,
						color: Colors.white,
						size: 28,
					),
					const SizedBox(width: 12),
					Expanded(
						child: Column(
							crossAxisAlignment: CrossAxisAlignment.start,
							mainAxisSize: MainAxisSize.min,
							children: [
								Text(
									isCritical ? 'CẢNH BÁO NGUY HIỂM' : 'CẢNH BÁO VẬT CẢN',
									style: const TextStyle(
										color: Colors.white,
										fontWeight: FontWeight.bold,
										fontSize: 13,
									),
								),
								const SizedBox(height: 2),
								Text(
									'${alert.message} (${alert.distanceCm.toStringAsFixed(1)} cm)',
									style: const TextStyle(color: Colors.white, fontSize: 13),
									maxLines: 2,
									overflow: TextOverflow.ellipsis,
								),
								if (alert.detectedObjects.isNotEmpty) ...[
									const SizedBox(height: 4),
									Wrap(
										spacing: 4,
										children: alert.detectedObjects.map((obj) => Container(
											padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
											decoration: BoxDecoration(
												color: Colors.black26,
												borderRadius: BorderRadius.circular(4),
											),
											child: Text(
												obj,
												style: const TextStyle(color: Colors.white, fontSize: 11),
											),
										)).toList(),
									),
								],
							],
						),
					),
					if (onAcknowledge != null && !alert.isAcknowledged)
						IconButton(
							icon: const Icon(Icons.check, color: Colors.white),
							tooltip: 'Xác nhận',
							onPressed: onAcknowledge,
						),
				],
			),
		);
	}
}
