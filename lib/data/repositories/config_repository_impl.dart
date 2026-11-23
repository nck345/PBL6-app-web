import 'dart:async';
import '../../core/constants/app_constants.dart';
import '../../domain/entities/device_config_entity.dart';
import '../../domain/repositories/config_repository.dart';
import '../datasources/mqtt_datasource.dart';
import '../models/device_config_model.dart';

class ConfigRepositoryImpl implements ConfigRepository {
  final MqttDatasource mqttDataSource;
  DeviceConfigEntity? _currentConfig;
  late final StreamController<DeviceConfigEntity> _controller;
  StreamSubscription? _subscription;

  ConfigRepositoryImpl({required this.mqttDataSource}) {
    _controller = StreamController<DeviceConfigEntity>.broadcast();
    _subscription = mqttDataSource.configStream.listen((json) {
      try {
        final entity = DeviceConfigModel.fromJson(json).toEntity();
        _currentConfig = entity;
        _controller.add(entity);
      } catch (_) {}
    });
  }

  @override
  Stream<DeviceConfigEntity> get configStream => _controller.stream;

  @override
  DeviceConfigEntity? get currentConfig => _currentConfig;

  @override
  Future<DeviceConfigEntity?> getConfig() async {
    return _currentConfig;
  }

  @override
  Future<void> updateConfig(DeviceConfigEntity config, {String? deviceId}) async {
    final targetDevice = deviceId ?? AppConstants.defaultDeviceId;
    final model = DeviceConfigModel.fromEntity(config);
    await mqttDataSource.publishConfig(targetDevice, model.toJson());
    _currentConfig = config;
  }

  @override
  Future<void> sendCommand(String command, {String? deviceId, String? requestId}) async {
    final targetDevice = deviceId ?? AppConstants.defaultDeviceId;
    await mqttDataSource.publishCommand(targetDevice, command, requestId: requestId);
  }

  void dispose() {
    _subscription?.cancel();
    _controller.close();
  }
}
