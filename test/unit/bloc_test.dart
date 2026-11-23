import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/core/services/notification_service.dart';
import 'package:pbl6_app/data/datasources/mqtt_datasource.dart';
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

// Test Fakes (zero external dependencies)

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

  void emitError(Object error) => _controller.addError(error);

  void dispose() => _controller.close();
}

// Unit Tests

void main() {
  group('ConnectionBloc Unit Tests', () {
    late FakeMqttDatasource fakeMqtt;
    late ConnectionBloc bloc;

    setUp(() {
      fakeMqtt = FakeMqttDatasource();
      bloc = ConnectionBloc(mqttDatasource: fakeMqtt);
    });

    tearDown(() async {
      await bloc.close();
      fakeMqtt.dispose();
    });

    test('Initial state is ConnectionInitial', () {
      expect(bloc.state, equals(ConnectionInitial()));
    });

    test('ConnectRequested success emits [ConnectionLoading, ConnectionSuccess]', () async {
      final expected = [
        ConnectionLoading(),
        const ConnectionSuccess(status: 'connected'),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const ConnectRequested());
    });

    test('ConnectRequested failure emits [ConnectionLoading, ConnectionFailure]', () async {
      fakeMqtt.connectSuccess = false;
      final expected = [
        ConnectionLoading(),
        const ConnectionFailure(message: 'Không thể kết nối tới MQTT broker'),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const ConnectRequested());
    });

    test('ConnectRequested exception emits [ConnectionLoading, ConnectionFailure]', () async {
      fakeMqtt.shouldThrow = true;
      final expected = [
        ConnectionLoading(),
        predicate<ConnectionState>((s) => s is ConnectionFailure),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const ConnectRequested());
    });

    test('DisconnectRequested emits [ConnectionLoading, ConnectionInitial]', () async {
      final expected = [
        ConnectionLoading(),
        ConnectionInitial(),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const DisconnectRequested());
    });

    test('External status update to disconnected emits ConnectionFailure', () async {
      bloc.add(const ConnectionStatusChanged(status: 'disconnected'));
      await expectLater(
        bloc.stream,
        emits(const ConnectionFailure(message: 'Mất kết nối với MQTT broker')),
      );
    });
  });

  group('DashboardBloc Unit Tests', () {
    late FakeTelemetryRepository fakeRepo;
    late DashboardBloc bloc;

    const sampleTelemetry = TelemetryEntity(
      deviceId: 'pi4_01',
      timestamp: 1732312000,
      batteryPercentage: 85,
      temperatureCelsius: 48.5,
      cpuUsage: 32.0,
      ultrasonicDistanceCm: 145.2,
      cameraActive: true,
      speakerVolume: 80,
    );

    setUp(() {
      fakeRepo = FakeTelemetryRepository();
      bloc = DashboardBloc(
        telemetryRepository: fakeRepo,
        staleTimeout: const Duration(milliseconds: 100),
      );
    });

    tearDown(() async {
      await bloc.close();
      fakeRepo.dispose();
    });

    test('Initial state is DashboardInitial', () {
      expect(bloc.state, equals(DashboardInitial()));
    });

    test('StartTelemetrySubscription emits Loading then Loaded when data arrives', () async {
      final expected = [
        DashboardLoading(),
        const DashboardLoaded(telemetry: sampleTelemetry, isStale: false),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const StartTelemetrySubscription());
      await pumpEventQueue();
      fakeRepo.emitTelemetry(sampleTelemetry);
    });

    test('Telemetry staleness timer flags isStale=true after timeout', () async {
      final expected = [
        DashboardLoading(),
        const DashboardLoaded(telemetry: sampleTelemetry, isStale: false),
        const DashboardLoaded(telemetry: sampleTelemetry, isStale: true),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const StartTelemetrySubscription());
      await pumpEventQueue();
      fakeRepo.emitTelemetry(sampleTelemetry);

      await Future.delayed(const Duration(milliseconds: 150));
    });

    test('Telemetry stream error emits DashboardError', () async {
      final expected = [
        DashboardLoading(),
        predicate<DashboardState>((s) => s is DashboardError),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const StartTelemetrySubscription());
      await pumpEventQueue();
      fakeRepo.emitError('Telemetry parsing error');
    });

    test('StopTelemetrySubscription emits DashboardInitial', () async {
      bloc.add(const StopTelemetrySubscription());
      await expectLater(bloc.stream, emits(DashboardInitial()));
    });
  });

  group('AlertBloc Unit Tests', () {
    late FakeAlertRepository fakeRepo;
    late FakeNotificationService fakeNotification;
    late AlertBloc bloc;

    const criticalAlert = AlertEntity(
      eventId: 'evt_critical_01',
      timestamp: 1732312015,
      alertType: 'OBSTACLE_DANGER',
      level: 'CRITICAL',
      distanceCm: 25.0,
      detectedObjects: ['stairs_down'],
      message: 'Nguy hiểm: Bậc thang phía trước!',
    );

    const warningAlert = AlertEntity(
      eventId: 'evt_warning_01',
      timestamp: 1732312010,
      alertType: 'LOW_BATTERY',
      level: 'WARNING',
      distanceCm: -1.0,
      detectedObjects: [],
      message: 'Cảnh báo: Pin dưới 15%',
    );

    setUp(() {
      fakeRepo = FakeAlertRepository();
      fakeNotification = FakeNotificationService();
      bloc = AlertBloc(
        alertRepository: fakeRepo,
        notificationService: fakeNotification,
      );
    });

    tearDown(() async {
      await bloc.close();
      fakeRepo.dispose();
    });

    test('Initial state is AlertInitial, subscription on empty repo emits AlertEmpty', () async {
      expect(bloc.state, equals(AlertInitial()));

      final expected = [
        AlertInitial(),
        AlertEmpty(),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const StartAlertSubscription());
    });

    test('Receiving CRITICAL alert triggers NotificationService and emits AlertActive', () async {
      final expected = [
        AlertInitial(),
        AlertEmpty(),
        const AlertActive(latestAlert: criticalAlert, alertHistory: [criticalAlert]),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const StartAlertSubscription());
      await pumpEventQueue();
      fakeRepo.emitAlert(criticalAlert);

      await pumpEventQueue();
      expect(fakeNotification.triggeredAlerts, contains(criticalAlert));
    });

    test('Receiving WARNING alert does NOT trigger NotificationService heads-up', () async {
      bloc.add(const StartAlertSubscription());
      await pumpEventQueue();
      fakeRepo.emitAlert(warningAlert);

      await pumpEventQueue();
      expect(fakeNotification.triggeredAlerts, isEmpty);
      expect(bloc.state, isA<AlertActive>());
    });

    test('AcknowledgeAlert marks matching alert as acknowledged', () async {
      bloc.add(const StartAlertSubscription());
      fakeRepo.emitAlert(criticalAlert);
      await pumpEventQueue();

      bloc.add(const AcknowledgeAlert(eventId: 'evt_critical_01'));
      await pumpEventQueue();

      final state = bloc.state as AlertActive;
      expect(state.latestAlert.isAcknowledged, isTrue);
    });

    test('ClearAlerts empties history and emits AlertEmpty', () async {
      bloc.add(const StartAlertSubscription());
      fakeRepo.emitAlert(criticalAlert);
      await pumpEventQueue();

      bloc.add(const ClearAlerts());
      await expectLater(bloc.stream, emits(AlertEmpty()));
    });
  });

  group('ConfigBloc Unit Tests', () {
    late FakeConfigRepository fakeRepo;
    late ConfigBloc bloc;

    final sampleConfig = DeviceConfigEntity.defaultConfig();

    setUp(() {
      fakeRepo = FakeConfigRepository();
      bloc = ConfigBloc(configRepository: fakeRepo);
    });

    tearDown(() async {
      await bloc.close();
      fakeRepo.dispose();
    });

    test('Initial state is ConfigInitial', () {
      expect(bloc.state, equals(ConfigInitial()));
    });

    test('LoadConfig success emits [ConfigLoading, ConfigLoaded]', () async {
      fakeRepo.currentConfigValue = sampleConfig;
      final expected = [
        ConfigLoading(),
        ConfigLoaded(config: sampleConfig),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const LoadConfig());
    });

    test('LoadConfig failure emits [ConfigLoading, ConfigFailure]', () async {
      fakeRepo.shouldThrow = true;
      final expected = [
        ConfigLoading(),
        predicate<ConfigState>((s) => s is ConfigFailure),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const LoadConfig());
    });

    test('UpdateConfigRequested emits [ConfigLoading, ConfigSuccess, ConfigLoaded]', () async {
      final updatedConfig = DeviceConfigEntity(
        distanceThresholdCm: 100,
        speakerVolume: 95,
        alertFrequencyMs: 400,
        detectionFps: 20,
      );
      final expected = [
        ConfigLoading(),
        ConfigSuccess(message: 'Cập nhật cấu hình thành công', config: updatedConfig),
        ConfigLoaded(config: updatedConfig),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(UpdateConfigRequested(config: updatedConfig));
    });

    test('SendHardwareCommand emits [ConfigLoading, ConfigSuccess, ConfigLoaded]', () async {
      fakeRepo.currentConfigValue = sampleConfig;
      bloc.add(const LoadConfig());
      await pumpEventQueue();

      final expected = [
        ConfigLoading(),
        ConfigSuccess(message: 'Lệnh REBOOT đã được gửi', config: sampleConfig),
        ConfigLoaded(config: sampleConfig),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      bloc.add(const SendHardwareCommand(command: 'REBOOT'));
      await pumpEventQueue();
      expect(fakeRepo.lastCommand, 'REBOOT');
    });

    test('Config stream error emits ConfigFailure without throwing emitter assertion', () async {
      fakeRepo.currentConfigValue = sampleConfig;
      bloc.add(const LoadConfig());
      await pumpEventQueue();

      expect(bloc.state, isA<ConfigLoaded>());

      final expected = [
        predicate<ConfigState>(
          (s) =>
              s is ConfigFailure &&
              s.message.contains('Stream broker connection error') &&
              s.lastConfig == sampleConfig,
        ),
      ];
      expectLater(bloc.stream, emitsInOrder(expected));

      fakeRepo.emitError('Stream broker connection error');
      await pumpEventQueue();
    });
  });
}
