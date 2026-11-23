import 'package:flutter/material.dart' hide ConnectionState;
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../core/constants/app_constants.dart';
import '../bloc/alerts/alert_bloc.dart';
import '../bloc/connection/connection_bloc.dart';
import '../bloc/dashboard/dashboard_bloc.dart';
import '../widgets/alert_banner_widget.dart';
import '../widgets/battery_indicator.dart';
import '../widgets/metric_tile.dart';

class HomeDashboardScreen extends StatelessWidget {
	final VoidCallback? onNavigateToLive;

	const HomeDashboardScreen({super.key, this.onNavigateToLive});

	@override
	Widget build(BuildContext context) {
		return Scaffold(
			appBar: AppBar(
				title: const Text(AppConstants.appTitle),
				actions: [
					BlocBuilder<ConnectionBloc, ConnectionState>(
						builder: (context, state) {
							if (state is ConnectionSuccess) {
								return Padding(
									padding: const EdgeInsets.only(right: 16),
									child: Chip(
										avatar: const Icon(Icons.wifi, color: Colors.green, size: 16),
										label: const Text('Online', style: TextStyle(color: Colors.green, fontSize: 12)),
										backgroundColor: Colors.green.withValues(alpha: 0.1),
										side: BorderSide.none,
									),
								);
							}
							if (state is ConnectionLoading) {
								return const Padding(
									padding: EdgeInsets.only(right: 16),
									child: SizedBox(
										width: 20,
										height: 20,
										child: CircularProgressIndicator(strokeWidth: 2),
									),
								);
							}
							return Padding(
								padding: const EdgeInsets.only(right: 8),
								child: TextButton.icon(
									icon: const Icon(Icons.wifi_off, color: Colors.red, size: 16),
									label: const Text('Kết nối lại', style: TextStyle(color: Colors.red, fontSize: 12)),
									onPressed: () {
										context.read<ConnectionBloc>().add(const ConnectRequested());
									},
								),
							);
						},
					),
				],
			),
			body: RefreshIndicator(
				onRefresh: () async {
					context.read<ConnectionBloc>().add(const ConnectRequested());
					context.read<DashboardBloc>().add(const StartTelemetrySubscription());
					context.read<AlertBloc>().add(const StartAlertSubscription());
				},
				child: ListView(
					padding: const EdgeInsets.all(16),
					children: [
						BlocBuilder<AlertBloc, AlertState>(
							builder: (context, state) {
								if (state is AlertActive && !state.latestAlert.isAcknowledged) {
									return AlertBannerWidget(
										alert: state.latestAlert,
										onAcknowledge: () {
											context.read<AlertBloc>().add(AcknowledgeAlert(eventId: state.latestAlert.eventId));
										},
									);
								}
								return const SizedBox.shrink();
							},
						),
						BlocBuilder<DashboardBloc, DashboardState>(
							builder: (context, state) {
								if (state is DashboardLoaded && state.isStale) {
									return Container(
										margin: const EdgeInsets.only(bottom: 12),
										padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
										decoration: BoxDecoration(
											color: Colors.amber.shade100,
											borderRadius: BorderRadius.circular(8),
											border: Border.all(color: Colors.amber.shade400),
										),
										child: Row(
											children: [
												Icon(Icons.access_time, color: Colors.amber.shade900, size: 20),
												const SizedBox(width: 8),
												Expanded(
													child: Text(
														'Dữ liệu cảm biến có thể bị gián đoạn (mất tín hiệu > 10s)',
														style: TextStyle(color: Colors.amber.shade900, fontSize: 12),
													),
												),
											],
										),
									);
								}
								return const SizedBox.shrink();
							},
						),
						Card(
							shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
							elevation: 2,
							child: Padding(
								padding: const EdgeInsets.all(16),
								child: Column(
									crossAxisAlignment: CrossAxisAlignment.start,
									children: [
										Row(
											mainAxisAlignment: MainAxisAlignment.spaceBetween,
											children: [
												Expanded(
													child: Row(
														children: [
															Icon(Icons.devices, color: Theme.of(context).colorScheme.primary),
															const SizedBox(width: 8),
															const Expanded(
																child: Text(
																	'Thiết bị Pi 4',
																	style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
																	maxLines: 1,
																	overflow: TextOverflow.ellipsis,
																),
															),
														],
													),
												),
												const SizedBox(width: 8),
												BlocBuilder<DashboardBloc, DashboardState>(
													builder: (context, state) {
														if (state is DashboardLoaded) {
															return BatteryIndicator(
																percentage: state.telemetry.batteryPercentage,
																isStale: state.isStale,
															);
														}
														return const Text('Đang đợi...');
													},
												),
											],
										),
										const Divider(height: 24),
										BlocBuilder<DashboardBloc, DashboardState>(
											builder: (context, state) {
												if (state is DashboardLoaded) {
													final t = state.telemetry;
													final isSensorConn = t.isSensorConnected;
													final isDistDanger = isSensorConn && t.ultrasonicDistanceCm < 60;
													return LayoutBuilder(
														builder: (context, constraints) {
															final isWide = constraints.maxWidth >= 600;
															return GridView.count(
																crossAxisCount: isWide ? 4 : 2,
																crossAxisSpacing: 10,
																mainAxisSpacing: 10,
																shrinkWrap: true,
																physics: const NeverScrollableScrollPhysics(),
																childAspectRatio: isWide ? 1.4 : 1.15,
																children: [
																	MetricTile(
																		title: 'Vật cản gần nhất',
																		value: isSensorConn ? t.ultrasonicDistanceCm.toStringAsFixed(1) : '--',
																		unit: isSensorConn ? 'cm' : '',
																		icon: isSensorConn ? Icons.radar : Icons.sensors_off,
																		color: !isSensorConn ? Colors.grey : (isDistDanger ? Colors.red : Colors.blue),
																		subtitle: !isSensorConn ? 'Chưa kết nối cảm biến' : (isDistDanger ? 'CẢNH BÁO QUÁ GẦN' : 'Khoảng cách an toàn'),
																	),
																	MetricTile(
																		title: 'Nhiệt độ CPU',
																		value: t.temperatureCelsius.toStringAsFixed(1),
																		unit: '°C',
																		icon: Icons.thermostat,
																		color: t.temperatureCelsius > 70 ? Colors.orange : Colors.teal,
																		subtitle: t.temperatureCelsius > 70 ? 'Nhiệt độ cao' : 'Ổn định',
																	),
																	MetricTile(
																		title: 'Tải CPU',
																		value: t.cpuUsage.toStringAsFixed(0),
																		unit: '%',
																		icon: Icons.memory,
																		color: Colors.indigo,
																	),
																	MetricTile(
																		title: 'Âm lượng loa',
																		value: '${t.speakerVolume}',
																		unit: '%',
																		icon: Icons.volume_up,
																		color: Colors.deepPurple,
																	),
																],
															);
														},
													);
												}
												if (state is DashboardLoading) {
													return const Center(
														child: Padding(
															padding: EdgeInsets.all(24),
															child: CircularProgressIndicator(),
														),
													);
												}
												return const Center(
													child: Padding(
														padding: EdgeInsets.all(16),
														child: Text('Chưa có thông số thiết bị từ MQTT broker'),
													),
												);
											},
										),
									],
								),
							),
						),
						const SizedBox(height: 16),
						Card(
							elevation: 1,
							shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
							child: ListTile(
								contentPadding: const EdgeInsets.all(16),
								leading: Container(
									padding: const EdgeInsets.all(12),
									decoration: BoxDecoration(
										color: Theme.of(context).colorScheme.primaryContainer,
										shape: BoxShape.circle,
									),
									child: Icon(Icons.videocam, color: Theme.of(context).colorScheme.primary, size: 28),
								),
								title: const Text('Xem Camera Trực Tiếp', style: TextStyle(fontWeight: FontWeight.bold)),
								subtitle: const Text('Góc nhìn người khiếm thị & Đàm thoại Push-to-Talk'),
								trailing: const Icon(Icons.arrow_forward_ios, size: 16),
								onTap: onNavigateToLive,
							),
						),
					],
				),
			),
		);
	}
}
