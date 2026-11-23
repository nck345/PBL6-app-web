import 'dart:async';
import 'package:flutter/material.dart' hide ConnectionState;
import 'package:flutter/services.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:pbl6_app/core/constants/app_constants.dart';
import 'package:pbl6_app/core/services/notification_service.dart';
import 'package:pbl6_app/data/datasources/mqtt_datasource.dart';
import 'package:pbl6_app/data/datasources/webrtc_datasource.dart';
import 'package:pbl6_app/domain/entities/alert_entity.dart';
import 'package:pbl6_app/domain/entities/device_config_entity.dart';
import 'package:pbl6_app/domain/entities/telemetry_entity.dart';
import 'package:pbl6_app/domain/repositories/alert_repository.dart';
import 'package:pbl6_app/domain/repositories/config_repository.dart';
import 'package:pbl6_app/domain/repositories/telemetry_repository.dart';
import 'package:pbl6_app/presentation/bloc/alerts/alert_bloc.dart';
import 'package:pbl6_app/presentation/bloc/config/config_bloc.dart';
import 'package:pbl6_app/presentation/bloc/connection/connection_bloc.dart';
import 'package:pbl6_app/presentation/bloc/dashboard/dashboard_bloc.dart';
import 'package:pbl6_app/presentation/bloc/webrtc/webrtc_bloc.dart';

class FakeMqttDatasource implements MqttDatasource {
	final StreamController<String> _statusController = StreamController<String>.broadcast();
	bool connectSuccess = true;
	bool shouldThrow = false;
	bool isConnectedValue = false;

	@override
	Stream<String> get connectionStatusStream => _statusController.stream;

	@override
	bool get isConnected => isConnectedValue;

	@override
	Future<bool> connect({
		String? broker,
		int? port,
		String? clientIdentifier,
		String? deviceId,
	}) async {
		if (shouldThrow) throw Exception('Socket connection timeout');
		isConnectedValue = connectSuccess;
		if (connectSuccess) {
			_statusController.add('connected');
		}
		return connectSuccess;
	}

	@override
	Future<void> disconnect() async {
		isConnectedValue = false;
		_statusController.add('disconnected');
	}

	void emitStatus(String status) => _statusController.add(status);

	@override
	void dispose() => _statusController.close();

	@override
	dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class FakeTelemetryRepository implements TelemetryRepository {
	final StreamController<TelemetryEntity> _controller = StreamController<TelemetryEntity>.broadcast();
	TelemetryEntity? _latest;

	@override
	Stream<TelemetryEntity> get telemetryStream => _controller.stream;

	@override
	TelemetryEntity? get latestTelemetry => _latest;

	@override
	TelemetryEntity? get lastTelemetry => _latest;

	void emitTelemetry(TelemetryEntity entity) {
		_latest = entity;
		_controller.add(entity);
	}

	void emitError(Object error) => _controller.addError(error);

	void dispose() => _controller.close();
}

class FakeAlertRepository implements AlertRepository {
	final StreamController<AlertEntity> _controller = StreamController<AlertEntity>.broadcast();
	final List<AlertEntity> _cached = [];

	@override
	Stream<AlertEntity> get alertStream => _controller.stream;

	@override
	List<AlertEntity> get cachedAlerts => List.unmodifiable(_cached);

	@override
	List<AlertEntity> get alertHistory => List.unmodifiable(_cached);

	@override
	void clearAlerts() => _cached.clear();

	@override
	void clearHistory() => clearAlerts();

	@override
	void dismissAlert(String eventId) {
		_cached.removeWhere((a) => a.eventId == eventId);
	}

	void emitAlert(AlertEntity alert) {
		_cached.insert(0, alert);
		_controller.add(alert);
	}

	void emitError(Object error) => _controller.addError(error);

	void dispose() => _controller.close();
}

class FakeNotificationService implements NotificationService {
	final List<AlertEntity> triggeredAlerts = [];

	@override
	Future<void> showAlertNotification(AlertEntity alert) async {
		triggeredAlerts.add(alert);
	}

	@override
	Future<void> initialize({DidReceiveNotificationResponseCallback? onDidReceive}) async {}

	@override
	Future<bool> requestPermissions() async => true;

	@override
	dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class FakeConfigRepository implements ConfigRepository {
	final StreamController<DeviceConfigEntity> _controller = StreamController<DeviceConfigEntity>.broadcast();
	DeviceConfigEntity? currentConfigValue;
	String? lastCommand;
	String? lastRequestId;
	bool shouldThrow = false;

	@override
	Stream<DeviceConfigEntity> get configStream => _controller.stream;

	@override
	DeviceConfigEntity? get currentConfig => currentConfigValue;

	@override
	Future<DeviceConfigEntity?> getConfig() async {
		if (shouldThrow) throw Exception('Network timeout');
		return currentConfigValue;
	}

	@override
	Future<void> updateConfig(DeviceConfigEntity config, {String? deviceId}) async {
		if (shouldThrow) throw Exception('Failed to publish config');
		currentConfigValue = config;
		_controller.add(config);
	}

	@override
	Future<void> sendCommand(String command, {String? deviceId, String? requestId}) async {
		if (shouldThrow) throw Exception('Failed to send command');
		lastCommand = command;
		lastRequestId = requestId;
	}

	void emitConfig(DeviceConfigEntity config) {
		currentConfigValue = config;
		_controller.add(config);
	}

	void dispose() => _controller.close();
}

class FakeWebrtcDatasource implements WebrtcDatasource {
	final StreamController<RTCPeerConnectionState> _controller = StreamController<RTCPeerConnectionState>.broadcast();
	final RTCVideoRenderer fakeRenderer = RTCVideoRenderer();
	bool connectSuccess = true;
	bool shouldThrow = false;
	bool shouldThrowInit = false;
	bool micEnabled = false;
	int disconnectCallCount = 0;

	@override
	MqttDatasource get mqttDatasource => throw UnimplementedError();

	@override
	RTCVideoRenderer get videoRenderer => fakeRenderer;

	@override
	Stream<RTCPeerConnectionState> get connectionStateStream => _controller.stream;

	@override
	bool get isMicrophoneEnabled => micEnabled;

	@override
	RTCPeerConnection? get peerConnection => null;

	@override
	Future<void> initialize() async {
		if (shouldThrowInit) throw Exception('Renderer initialization failed');
	}

	@override
	Future<void> connect(String deviceId) async {
		if (shouldThrow) throw Exception('STUN/ICE negotiation failed');
		if (connectSuccess) {
			_controller.add(RTCPeerConnectionState.RTCPeerConnectionStateConnected);
		} else {
			_controller.add(RTCPeerConnectionState.RTCPeerConnectionStateFailed);
		}
	}

	@override
	Future<void> disconnect() async {
		++disconnectCallCount;
		_controller.add(RTCPeerConnectionState.RTCPeerConnectionStateClosed);
	}

	@override
	Future<void> setMicrophoneEnabled(bool enabled) async {
		micEnabled = enabled;
	}

	void emitConnectionState(RTCPeerConnectionState state) {
		_controller.add(state);
	}

	void emitError(Object error) {
		_controller.addError(error);
	}

	@override
	Future<void> dispose() async {
		await _controller.close();
	}

	@override
	dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void setupMockPermissionHandler({bool isGranted = true}) {
	TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(
		const MethodChannel('flutter.baseflow.com/permissions/methods'),
		(MethodCall methodCall) async {
			if (methodCall.method == 'checkPermissionStatus') {
				return isGranted ? 1 : 0;
			}
			if (methodCall.method == 'requestPermissions') {
				final List<dynamic> permissions = methodCall.arguments as List<dynamic>;
				final Map<int, int> result = {};
				for (final p in permissions) {
					result[p as int] = isGranted ? 1 : 0;
				}
				return result;
			}
			if (methodCall.method == 'checkServiceStatus') {
				return 1;
			}
			return null;
		},
	);
}

void clearMockPermissionHandler() {
	TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(
		const MethodChannel('flutter.baseflow.com/permissions/methods'),
		null,
	);
}

TelemetryEntity createTestTelemetry({
	String deviceId = AppConstants.defaultDeviceId,
	int? timestamp,
	int batteryPercentage = 85,
	double temperatureCelsius = 48.5,
	double cpuUsage = 32.0,
	double ultrasonicDistanceCm = 145.2,
	bool cameraActive = true,
	int speakerVolume = 80,
	double? latitude = 16.0738,
	double? longitude = 108.1499,
	double? speedKmh = 3.5,
	double? headingDegrees = 135.0,
	bool hasGpsFix = true,
	int? satellites = 8,
	double? altitudeM = 14.2,
}) {
	return TelemetryEntity(
		deviceId: deviceId,
		timestamp: timestamp ?? (DateTime.now().millisecondsSinceEpoch ~/ 1000),
		batteryPercentage: batteryPercentage,
		temperatureCelsius: temperatureCelsius,
		cpuUsage: cpuUsage,
		ultrasonicDistanceCm: ultrasonicDistanceCm,
		cameraActive: cameraActive,
		speakerVolume: speakerVolume,
		latitude: latitude,
		longitude: longitude,
		speedKmh: speedKmh,
		headingDegrees: headingDegrees,
		hasGpsFix: hasGpsFix,
		satellites: satellites,
		altitudeM: altitudeM,
	);
}

AlertEntity createTestAlert({
	String eventId = 'evt_001',
	int? timestamp,
	String alertType = 'OBSTACLE_DANGER',
	String level = 'CRITICAL',
	double distanceCm = 25.0,
	List<String>? detectedObjects,
	String message = 'Vật cản nguy hiểm phía trước',
	bool isAcknowledged = false,
}) {
	return AlertEntity(
		eventId: eventId,
		timestamp: timestamp ?? (DateTime.now().millisecondsSinceEpoch ~/ 1000),
		alertType: alertType,
		level: level,
		distanceCm: distanceCm,
		detectedObjects: detectedObjects ?? const ['stairs_down'],
		message: message,
		isAcknowledged: isAcknowledged,
	);
}

DeviceConfigEntity createTestConfig({
	int distanceThresholdCm = AppConstants.defaultDistanceThresholdCm,
	int speakerVolume = AppConstants.defaultSpeakerVolume,
	int alertFrequencyMs = AppConstants.defaultAlertFrequencyMs,
	int detectionFps = AppConstants.defaultDetectionFps,
}) {
	return DeviceConfigEntity(
		distanceThresholdCm: distanceThresholdCm,
		speakerVolume: speakerVolume,
		alertFrequencyMs: alertFrequencyMs,
		detectionFps: detectionFps,
	);
}

Widget buildTestApp({
	required Widget child,
	ConnectionBloc? connectionBloc,
	DashboardBloc? dashboardBloc,
	AlertBloc? alertBloc,
	ConfigBloc? configBloc,
	WebRtcBloc? webrtcBloc,
}) {
	return MultiBlocProvider(
		providers: [
			if (connectionBloc != null)
				BlocProvider<ConnectionBloc>.value(value: connectionBloc),
			if (dashboardBloc != null)
				BlocProvider<DashboardBloc>.value(value: dashboardBloc),
			if (alertBloc != null)
				BlocProvider<AlertBloc>.value(value: alertBloc),
			if (configBloc != null)
				BlocProvider<ConfigBloc>.value(value: configBloc),
			if (webrtcBloc != null)
				BlocProvider<WebRtcBloc>.value(value: webrtcBloc),
		],
		child: MaterialApp(
			theme: ThemeData(useMaterial3: true),
			home: child,
		),
	);
}
