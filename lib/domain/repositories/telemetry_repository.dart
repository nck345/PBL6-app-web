import '../entities/telemetry_entity.dart';

abstract class TelemetryRepository {
  Stream<TelemetryEntity> get telemetryStream;
  TelemetryEntity? get latestTelemetry;
  TelemetryEntity? get lastTelemetry => latestTelemetry;
}
