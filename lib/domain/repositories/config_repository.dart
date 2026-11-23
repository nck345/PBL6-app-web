import '../entities/device_config_entity.dart';

abstract class ConfigRepository {
  Stream<DeviceConfigEntity> get configStream;
  DeviceConfigEntity? get currentConfig;
  Future<DeviceConfigEntity?> getConfig();
  Future<void> updateConfig(DeviceConfigEntity config, {String? deviceId});
  Future<void> sendCommand(String command, {String? deviceId, String? requestId});
}
