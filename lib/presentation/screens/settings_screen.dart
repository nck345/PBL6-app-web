import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../core/constants/app_constants.dart';
import '../../domain/entities/device_config_entity.dart';
import '../bloc/config/config_bloc.dart';
import '../bloc/connection/connection_bloc.dart';

class SettingsScreen extends StatefulWidget {
	const SettingsScreen({super.key});

	@override
	State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
	double _distanceThreshold = AppConstants.defaultDistanceThresholdCm.toDouble();
	double _speakerVolume = AppConstants.defaultSpeakerVolume.toDouble();
	double _alertFrequency = AppConstants.defaultAlertFrequencyMs.toDouble();

	@override
	void initState() {
		super.initState();
		context.read<ConfigBloc>().add(const LoadConfig());
	}

	@override
	Widget build(BuildContext context) {
		return Scaffold(
			appBar: AppBar(title: const Text('Cài đặt & Điều khiển')),
			body: BlocConsumer<ConfigBloc, ConfigState>(
				listener: (context, state) {
					if (state is ConfigSuccess) {
						ScaffoldMessenger.of(context).showSnackBar(
							SnackBar(content: Text(state.message ?? 'Cập nhật cấu hình thành công'), backgroundColor: Colors.green),
						);
					}
					if (state is ConfigFailure) {
						ScaffoldMessenger.of(context).showSnackBar(
							SnackBar(content: Text('Lỗi: ${state.message}'), backgroundColor: Colors.red),
						);
					}
					if (state is ConfigLoaded) {
						setState(() {
							_distanceThreshold = state.config.distanceThresholdCm.clamp(20, 250).toDouble();
							_speakerVolume = state.config.speakerVolume.clamp(0, 100).toDouble();
							_alertFrequency = state.config.alertFrequencyMs.clamp(200, 2000).toDouble();
						});
					}
				},
				builder: (context, state) {
					return ListView(
						padding: const EdgeInsets.all(16),
						children: [
							Card(
								shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
								child: Padding(
									padding: const EdgeInsets.all(16),
									child: Column(
										crossAxisAlignment: CrossAxisAlignment.start,
										children: [
											const Text('Cấu hình Cảm biến & Cảnh báo', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
											const SizedBox(height: 16),
											Text('Ngưỡng khoảng cách cảnh báo: ${_distanceThreshold.round()} cm'),
											Slider(
												value: _distanceThreshold.clamp(20, 250),
												min: 20,
												max: 250,
												divisions: 23,
												label: '${_distanceThreshold.round()} cm',
												onChanged: (val) => setState(() => _distanceThreshold = val),
											),
											const SizedBox(height: 8),
											Text('Âm lượng loa Raspberry Pi: ${_speakerVolume.round()}%'),
											Slider(
												value: _speakerVolume.clamp(0, 100),
												min: 0,
												max: 100,
												divisions: 20,
												label: '${_speakerVolume.round()}%',
												onChanged: (val) => setState(() => _speakerVolume = val),
											),
											const SizedBox(height: 8),
											Text('Chu kỳ quét cảnh báo: ${_alertFrequency.round()} ms'),
											Slider(
												value: _alertFrequency.clamp(200, 2000),
												min: 200,
												max: 2000,
												divisions: 18,
												label: '${_alertFrequency.round()} ms',
												onChanged: (val) => setState(() => _alertFrequency = val),
											),
											const SizedBox(height: 16),
											SizedBox(
												width: double.infinity,
												child: ElevatedButton.icon(
													icon: const Icon(Icons.save),
													label: const Text('Lưu cấu hình lên Pi 4'),
													onPressed: () {
														final newConfig = DeviceConfigEntity(
															distanceThresholdCm: _distanceThreshold.round(),
															speakerVolume: _speakerVolume.round(),
															alertFrequencyMs: _alertFrequency.round(),
															detectionFps: AppConstants.defaultDetectionFps,
														);
														context.read<ConfigBloc>().add(UpdateConfigRequested(config: newConfig));
													},
												),
											),
										],
									),
								),
							),
							const SizedBox(height: 16),
							Card(
								shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
								child: Padding(
									padding: const EdgeInsets.all(16),
									child: Column(
										crossAxisAlignment: CrossAxisAlignment.start,
										children: [
											const Text('Lệnh Điều Khiển Phần Cứng', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
											const SizedBox(height: 12),
											ListTile(
												leading: const Icon(Icons.restart_alt, color: Colors.orange),
												title: const Text('Khởi động lại Pi (Reboot)'),
												onTap: () {
													context.read<ConfigBloc>().add(const SendHardwareCommand(command: 'REBOOT'));
												},
											),
											const Divider(height: 1),
											ListTile(
												leading: const Icon(Icons.replay, color: Colors.blue),
												title: const Text('Khởi động lại dịch vụ AI (Restart Service)'),
												onTap: () {
													context.read<ConfigBloc>().add(const SendHardwareCommand(command: 'RESTART_SERVICE'));
												},
											),
											const Divider(height: 1),
											ListTile(
												leading: const Icon(Icons.notifications_active, color: Colors.red),
												title: const Text('Phát còi khẩn cấp (Trigger Buzzer)'),
												onTap: () {
													context.read<ConfigBloc>().add(const SendHardwareCommand(command: 'TRIGGER_BUZZER'));
												},
											),
										],
									),
								),
							),
							const SizedBox(height: 16),
							Card(
								shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
								child: Padding(
									padding: const EdgeInsets.all(16),
									child: Column(
										crossAxisAlignment: CrossAxisAlignment.start,
										children: [
											const Text('Thông tin Kết nối Mạng', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
											const SizedBox(height: 12),
											const Text('Broker: ${AppConstants.defaultMqttBroker}:${AppConstants.defaultMqttPort}'),
											const SizedBox(height: 4),
											const Text('Device ID: ${AppConstants.defaultDeviceId}'),
											const SizedBox(height: 4),
											const Text('STUN: ${AppConstants.defaultStunServer}'),
											const SizedBox(height: 12),
											OutlinedButton.icon(
												icon: const Icon(Icons.sync),
												label: const Text('Tái kết nối MQTT Broker'),
												onPressed: () {
													context.read<ConnectionBloc>().add(const ConnectRequested());
												},
											),
										],
									),
								),
							),
						],
					);
				},
			),
		);
	}
}
