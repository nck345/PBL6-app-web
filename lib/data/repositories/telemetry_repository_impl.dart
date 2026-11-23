import 'dart:async';
import '../../domain/entities/telemetry_entity.dart';
import '../../domain/repositories/telemetry_repository.dart';
import '../datasources/mqtt_datasource.dart';
import '../models/telemetry_model.dart';

class TelemetryRepositoryImpl implements TelemetryRepository {
  final MqttDatasource mqttDataSource;
  TelemetryEntity? _lastTelemetry;
  late final StreamController<TelemetryEntity> _controller;
  StreamSubscription? _subscription;

  TelemetryRepositoryImpl({required this.mqttDataSource}) {
    _controller = StreamController<TelemetryEntity>.broadcast();
    _subscription = mqttDataSource.telemetryStream.listen((json) {
      try {
        final entity = TelemetryModel.fromJson(json).toEntity();
        _lastTelemetry = entity;
        _controller.add(entity);
      } catch (_) {}
    });
  }

  @override
  Stream<TelemetryEntity> get telemetryStream => _controller.stream;

  @override
  TelemetryEntity? get latestTelemetry => _lastTelemetry;

  @override
  TelemetryEntity? get lastTelemetry => _lastTelemetry;

  void dispose() {
    _subscription?.cancel();
    _controller.close();
  }
}
