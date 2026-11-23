import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../core/constants/app_constants.dart';
import '../bloc/dashboard/dashboard_bloc.dart';

class GpsMapScreen extends StatefulWidget {
	final String deviceId;
	const GpsMapScreen({super.key, this.deviceId = AppConstants.defaultDeviceId});

	@override
	State<GpsMapScreen> createState() => _GpsMapScreenState();
}

class _GpsMapScreenState extends State<GpsMapScreen> {
	final MapController _mapController = MapController();
	final List<LatLng> _routePoints = [];
	bool _followUser = true;
	bool _showRoute = true;
	double _currentZoom = 16.5;
	static const LatLng _defaultLocation = LatLng(16.0738, 108.1499);

	void _recenter(LatLng target) {
		setState(() => _followUser = true);
		_mapController.move(target, _currentZoom);
	}

	void _zoom(bool inOut, LatLng center) {
		setState(() {
			_currentZoom = (inOut ? _currentZoom + 1.0 : _currentZoom - 1.0).clamp(4.0, 19.0);
		});
		_mapController.move(center, _currentZoom);
	}

	@override
	Widget build(BuildContext context) {
		return BlocConsumer<DashboardBloc, DashboardState>(
			listener: (context, state) {
				if (state is DashboardLoaded && state.telemetry.isGpsAvailable) {
					final newPoint = LatLng(state.telemetry.latitude!, state.telemetry.longitude!);
					if (_routePoints.isEmpty ||
							_routePoints.last.latitude != newPoint.latitude ||
							_routePoints.last.longitude != newPoint.longitude) {
						setState(() {
							_routePoints.add(newPoint);
							if (_routePoints.length > 500) _routePoints.removeAt(0);
						});
					}
					if (_followUser) {
						_mapController.move(newPoint, _currentZoom);
					}
				}
			},
			builder: (context, state) {
				LatLng currentTarget = _defaultLocation;
				bool hasFix = false;
				int satellites = 0;
				double speed = 0.0;
				double heading = 0.0;
				double altitude = 0.0;
				String coordsText = 'Chưa có tín hiệu GPS';

				if (state is DashboardLoaded) {
					final t = state.telemetry;
					hasFix = t.isGpsAvailable;
					satellites = t.satellites ?? 0;
					speed = t.speedKmh ?? 0.0;
					heading = t.headingDegrees ?? 0.0;
					altitude = t.altitudeM ?? 0.0;
					coordsText = t.coordinatesDisplay;
					if (hasFix) {
						currentTarget = LatLng(t.latitude!, t.longitude!);
					} else if (_routePoints.isNotEmpty) {
						currentTarget = _routePoints.last;
					}
				}

				return Scaffold(
					appBar: AppBar(
						title: Row(
							children: [
								Expanded(
									child: Column(
										crossAxisAlignment: CrossAxisAlignment.start,
										mainAxisSize: MainAxisSize.min,
										children: [
											const Text(
												'Bản đồ Giám sát GPS',
												style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
												maxLines: 1,
												overflow: TextOverflow.ellipsis,
											),
											Text('Thiết bị: ${widget.deviceId}', style: const TextStyle(fontSize: 11, color: Colors.grey)),
										],
									),
								),
								Container(
									padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
									decoration: BoxDecoration(
										color: hasFix ? Colors.green.shade50 : Colors.amber.shade50,
										borderRadius: BorderRadius.circular(10),
										border: Border.all(color: hasFix ? Colors.green.shade300 : Colors.amber.shade400),
									),
									child: Row(
										mainAxisSize: MainAxisSize.min,
										children: [
											Icon(
												hasFix ? Icons.gps_fixed : Icons.gps_not_fixed,
												color: hasFix ? Colors.green.shade700 : Colors.amber.shade800,
												size: 13,
											),
											const SizedBox(width: 4),
											Text(
												hasFix ? 'Đã định vị ($satellites vệ tinh)' : 'Mất GPS',
												style: TextStyle(
													fontSize: 10,
													fontWeight: FontWeight.w600,
													color: hasFix ? Colors.green.shade800 : Colors.amber.shade900,
												),
											),
										],
									),
								),
							],
						),
					),
					body: Stack(
						children: [
							FlutterMap(
								mapController: _mapController,
								options: MapOptions(
									initialCenter: currentTarget,
									initialZoom: _currentZoom,
									onPositionChanged: (pos, hasGesture) {
										if (hasGesture && _followUser) {
											setState(() => _followUser = false);
										}
									},
								),
								children: [
									TileLayer(
										urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
										userAgentPackageName: 'com.pbl6.assistive_monitor',
									),
									if (_showRoute && _routePoints.length >= 2)
										PolylineLayer(
											polylines: [
												Polyline(
													points: _routePoints,
													strokeWidth: 4.0,
													color: Colors.blueAccent.withValues(alpha: 0.85),
												),
											],
										),
									MarkerLayer(
										markers: [
											Marker(
												point: currentTarget,
												width: 60,
												height: 60,
												child: _DeviceWearerMarker(
													heading: heading,
													hasFix: hasFix,
												),
											),
										],
									),
								],
							),
							Positioned(
								top: 16,
								right: 16,
								child: Column(
									mainAxisSize: MainAxisSize.min,
									children: [
										FloatingActionButton.small(
											heroTag: 'gps_recenter_btn',
											tooltip: 'Khóa tâm vào người đeo',
											backgroundColor: _followUser ? Colors.blueAccent : Colors.white,
											foregroundColor: _followUser ? Colors.white : Colors.black87,
											onPressed: () => _recenter(currentTarget),
											child: const Icon(Icons.my_location),
										),
										const SizedBox(height: 8),
										FloatingActionButton.small(
											heroTag: 'gps_zoom_in_btn',
											tooltip: 'Phóng to',
											backgroundColor: Colors.white,
											foregroundColor: Colors.black87,
											onPressed: () => _zoom(true, currentTarget),
											child: const Icon(Icons.add),
										),
										const SizedBox(height: 8),
										FloatingActionButton.small(
											heroTag: 'gps_zoom_out_btn',
											tooltip: 'Thu nhỏ',
											backgroundColor: Colors.white,
											foregroundColor: Colors.black87,
											onPressed: () => _zoom(false, currentTarget),
											child: const Icon(Icons.remove),
										),
										const SizedBox(height: 8),
										FloatingActionButton.small(
											heroTag: 'gps_route_toggle_btn',
											tooltip: _showRoute ? 'Ẩn lộ trình' : 'Hiện lộ trình',
											backgroundColor: _showRoute ? Colors.blue.shade50 : Colors.white,
											foregroundColor: Colors.blueAccent,
											onPressed: () => setState(() => _showRoute = !_showRoute),
											child: const Icon(Icons.timeline),
										),
									],
								),
							),
							Positioned(
								bottom: 16,
								left: 16,
								right: 16,
								child: Card(
									elevation: 4,
									shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
									child: Padding(
										padding: const EdgeInsets.all(12),
										child: Column(
											mainAxisSize: MainAxisSize.min,
											crossAxisAlignment: CrossAxisAlignment.start,
											children: [
												Row(
													children: [
														Icon(
															hasFix ? Icons.location_on : Icons.location_off,
															color: hasFix ? Colors.redAccent : Colors.grey,
															size: 18,
														),
														const SizedBox(width: 6),
														Expanded(
															child: Text(
																coordsText,
																style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
																maxLines: 1,
																overflow: TextOverflow.ellipsis,
															),
														),
														if (hasFix) ...[
															const SizedBox(width: 6),
															Text(
																'${speed.toStringAsFixed(1)} km/h',
																style: const TextStyle(
																	fontWeight: FontWeight.bold,
																	fontSize: 13,
																	color: Colors.blueAccent,
																),
															),
														],
													],
												),
												const Divider(height: 14),
												Wrap(
													alignment: WrapAlignment.spaceBetween,
													crossAxisAlignment: WrapCrossAlignment.center,
													spacing: 8,
													runSpacing: 4,
													children: [
														Text(
															'Độ cao: ${altitude.toStringAsFixed(1)}m | Hướng: ${heading.toStringAsFixed(0)}°',
															style: TextStyle(fontSize: 11, color: Colors.grey[700]),
														),
														TextButton.icon(
															style: TextButton.styleFrom(
																padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 0),
																visualDensity: VisualDensity.compact,
															),
															icon: const Icon(Icons.open_in_new, size: 13),
															label: const Text('Google Maps', style: TextStyle(fontSize: 11)),
															onPressed: hasFix
																? () async {
																		final uri = Uri.parse(
																			'https://www.google.com/maps/search/?api=1&query=${currentTarget.latitude},${currentTarget.longitude}',
																		);
																		if (await canLaunchUrl(uri)) {
																			await launchUrl(uri, mode: LaunchMode.externalApplication);
																		}
																	}
																: null,
														),
													],
												),
											],
										),
									),
								),
							),
						],
					),
				);
			},
		);
	}
}

class _DeviceWearerMarker extends StatelessWidget {
	final double heading;
	final bool hasFix;
	const _DeviceWearerMarker({required this.heading, required this.hasFix});

	@override
	Widget build(BuildContext context) {
		return Stack(
			alignment: Alignment.center,
			children: [
				Container(
					width: 44,
					height: 44,
					decoration: BoxDecoration(
						shape: BoxShape.circle,
						color: (hasFix ? Colors.blueAccent : Colors.grey).withValues(alpha: 0.25),
					),
				),
				Container(
					width: 28,
					height: 28,
					decoration: BoxDecoration(
						shape: BoxShape.circle,
						color: hasFix ? Colors.blueAccent : Colors.grey,
						border: Border.all(color: Colors.white, width: 2.5),
						boxShadow: const [
							BoxShadow(
								color: Colors.black26,
								blurRadius: 4,
								offset: Offset(0, 2),
							),
						],
					),
					child: Transform.rotate(
						angle: heading * (3.1415926535 / 180),
						child: const Icon(
							Icons.navigation,
							color: Colors.white,
							size: 15,
						),
					),
				),
			],
		);
	}
}
