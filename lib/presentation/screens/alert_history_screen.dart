import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:intl/intl.dart';
import '../bloc/alerts/alert_bloc.dart';

class AlertHistoryScreen extends StatelessWidget {
	const AlertHistoryScreen({super.key});

	@override
	Widget build(BuildContext context) {
		return Scaffold(
			appBar: AppBar(
				title: const Text('Lịch sử Cảnh báo'),
				actions: [
					IconButton(
						icon: const Icon(Icons.delete_sweep),
						tooltip: 'Xóa danh sách cảnh báo',
						onPressed: () {
							context.read<AlertBloc>().add(const ClearAlerts());
						},
					),
				],
			),
			body: BlocBuilder<AlertBloc, AlertState>(
				builder: (context, state) {
					if (state is AlertActive && state.alertHistory.isNotEmpty) {
						final alerts = state.alertHistory;
						return ListView.separated(
							padding: const EdgeInsets.all(12),
							itemCount: alerts.length,
							separatorBuilder: (_, _) => const Divider(height: 1),
							itemBuilder: (context, index) {
								final alert = alerts[index];
								final isCritical = alert.level.toUpperCase() == 'CRITICAL';
								final timeStr = DateFormat('HH:mm:ss dd/MM').format(alert.dateTime);

								return ListTile(
									leading: CircleAvatar(
										backgroundColor: isCritical ? Colors.red.shade100 : Colors.amber.shade100,
										child: Icon(
											isCritical ? Icons.warning : Icons.info,
											color: isCritical ? Colors.red : Colors.amber.shade900,
										),
									),
									title: Row(
										children: [
											Expanded(
												child: Text(
													alert.message,
													style: TextStyle(
														fontWeight: alert.isAcknowledged ? FontWeight.normal : FontWeight.bold,
													),
												),
											),
											Container(
												padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
												decoration: BoxDecoration(
													color: isCritical ? Colors.red.shade50 : Colors.amber.shade50,
													borderRadius: BorderRadius.circular(4),
													border: Border.all(
														color: isCritical ? Colors.red.shade200 : Colors.amber.shade200,
													),
												),
												child: Text(
													'${alert.distanceCm.toStringAsFixed(1)} cm',
													style: TextStyle(
														fontSize: 11,
														fontWeight: FontWeight.bold,
														color: isCritical ? Colors.red.shade800 : Colors.amber.shade900,
													),
												),
											),
										],
									),
									subtitle: Column(
										crossAxisAlignment: CrossAxisAlignment.start,
										children: [
											const SizedBox(height: 4),
											Text(timeStr, style: const TextStyle(fontSize: 12, color: Colors.grey)),
											if (alert.detectedObjects.isNotEmpty) ...[
												const SizedBox(height: 4),
												Wrap(
													spacing: 4,
													children: alert.detectedObjects.map((obj) => Chip(
														label: Text(obj, style: const TextStyle(fontSize: 10)),
														padding: EdgeInsets.zero,
														materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
													)).toList(),
												),
											],
										],
									),
									trailing: alert.isAcknowledged
										? const Icon(Icons.check_circle, color: Colors.green, size: 20)
										: IconButton(
											icon: const Icon(Icons.check),
											tooltip: 'Đánh dấu đã xem',
											onPressed: () {
												context.read<AlertBloc>().add(AcknowledgeAlert(eventId: alert.eventId));
											},
										),
								);
							},
						);
					}
					return const Center(
						child: Column(
							mainAxisSize: MainAxisSize.min,
							children: [
								Icon(Icons.notifications_none, size: 56, color: Colors.grey),
								SizedBox(height: 12),
								Text('Chưa ghi nhận cảnh báo nguy hiểm nào', style: TextStyle(color: Colors.grey)),
							],
						),
					);
				},
			),
		);
	}
}
