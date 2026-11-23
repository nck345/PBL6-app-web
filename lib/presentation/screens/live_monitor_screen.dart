import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import '../../core/constants/app_constants.dart';
import '../bloc/dashboard/dashboard_bloc.dart';
import '../bloc/webrtc/webrtc_bloc.dart';
import '../widgets/ptt_mic_button.dart';

class LiveMonitorScreen extends StatefulWidget {
	final String deviceId;
	const LiveMonitorScreen({super.key, this.deviceId = AppConstants.defaultDeviceId});

	@override
	State<LiveMonitorScreen> createState() => _LiveMonitorScreenState();
}

class _LiveMonitorScreenState extends State<LiveMonitorScreen> {
	@override
	void initState() {
		super.initState();
		WidgetsBinding.instance.addPostFrameCallback((_) {
			final bloc = context.read<WebRtcBloc>();
			if (bloc.state is WebRtcInitial || bloc.state is WebRtcDisconnected) {
				bloc.add(ConnectWebRtcEvent(deviceId: widget.deviceId));
			}
		});
	}

	@override
	Widget build(BuildContext context) {
		return Scaffold(
			backgroundColor: Colors.black,
			appBar: AppBar(
				backgroundColor: Colors.black54,
				elevation: 0,
				iconTheme: const IconThemeData(color: Colors.white),
				title: Text(
					'POV Trực tiếp (${widget.deviceId})',
					style: const TextStyle(color: Colors.white, fontSize: 16),
				),
				actions: [
					IconButton(
						icon: const Icon(Icons.refresh, color: Colors.white),
						tooltip: 'Kết nối lại luồng WebRTC',
						onPressed: () {
							context.read<WebRtcBloc>().add(ConnectWebRtcEvent(deviceId: widget.deviceId));
						},
					),
				],
			),
			body: Stack(
				children: [
					Positioned.fill(
						child: BlocBuilder<WebRtcBloc, WebRtcState>(
							builder: (context, state) {
								if (state is WebRtcConnected) {
									return RTCVideoView(
										state.renderer,
										objectFit: RTCVideoViewObjectFit.RTCVideoViewObjectFitCover,
									);
								}
								if (state is WebRtcConnecting) {
									return const Center(
										child: Column(
											mainAxisSize: MainAxisSize.min,
											children: [
												CircularProgressIndicator(color: Colors.white),
												SizedBox(height: 16),
												Text(
													'Đang bắt tay WebRTC P2P...',
													style: TextStyle(color: Colors.white70),
												),
											],
										),
									);
								}
								if (state is WebRtcFailure) {
									return Center(
										child: Padding(
											padding: const EdgeInsets.all(24),
											child: Column(
												mainAxisSize: MainAxisSize.min,
												children: [
													const Icon(Icons.error_outline, color: Colors.redAccent, size: 48),
													const SizedBox(height: 12),
													Text(
														state.message,
														style: const TextStyle(color: Colors.white70),
														textAlign: TextAlign.center,
													),
													const SizedBox(height: 16),
													ElevatedButton.icon(
														icon: const Icon(Icons.refresh),
														label: const Text('Thử lại'),
														onPressed: () {
															context.read<WebRtcBloc>().add(ConnectWebRtcEvent(deviceId: widget.deviceId));
														},
													),
												],
											),
										),
									);
								}
								return Center(
									child: Column(
										mainAxisSize: MainAxisSize.min,
										children: [
											const Icon(Icons.videocam_off, color: Colors.white38, size: 56),
											const SizedBox(height: 12),
											const Text('Chưa kết nối luồng video', style: TextStyle(color: Colors.white70)),
											const SizedBox(height: 16),
											ElevatedButton.icon(
												icon: const Icon(Icons.play_arrow),
												label: const Text('Bật Camera'),
												onPressed: () {
													context.read<WebRtcBloc>().add(ConnectWebRtcEvent(deviceId: widget.deviceId));
												},
											),
										],
									),
								);
							},
						),
					),
					Positioned(
						top: 16,
						left: 16,
						right: 16,
						child: BlocBuilder<DashboardBloc, DashboardState>(
							builder: (context, state) {
								if (state is DashboardLoaded) {
									final dist = state.telemetry.ultrasonicDistanceCm;
									final isDanger = dist < 60;
									return Container(
										padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
										decoration: BoxDecoration(
											color: isDanger ? Colors.red.withValues(alpha: 0.85) : Colors.black54,
											borderRadius: BorderRadius.circular(20),
										),
										child: Row(
											mainAxisSize: MainAxisSize.min,
											children: [
												Icon(
													isDanger ? Icons.warning : Icons.radar,
													color: Colors.white,
													size: 18,
												),
												const SizedBox(width: 8),
												Text(
													'Vật cản: ${dist.toStringAsFixed(1)} cm ${isDanger ? "- NGUY HIỂM" : ""}',
													style: const TextStyle(
														color: Colors.white,
														fontWeight: FontWeight.bold,
														fontSize: 13,
													),
												),
											],
										),
									);
								}
								return const SizedBox.shrink();
							},
						),
					),
					Positioned(
						bottom: 32,
						left: 0,
						right: 0,
						child: Column(
							mainAxisSize: MainAxisSize.min,
							children: [
								Container(
									padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
									decoration: BoxDecoration(
										color: Colors.black45,
										borderRadius: BorderRadius.circular(16),
									),
									child: const Text(
										'Nhấn giữ nút mic để nói qua loa Raspberry Pi',
										style: TextStyle(color: Colors.white70, fontSize: 12),
									),
								),
								const SizedBox(height: 12),
								const PttMicButton(size: 78),
							],
						),
					),
				],
			),
		);
	}
}
