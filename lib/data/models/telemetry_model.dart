import '../../domain/entities/telemetry_entity.dart';

class TelemetryModel extends TelemetryEntity {
  const TelemetryModel({
    required super.deviceId,
    required super.timestamp,
    required super.batteryPercentage,
    required super.temperatureCelsius,
    required super.cpuUsage,
    required super.ultrasonicDistanceCm,
    required super.cameraActive,
    required super.speakerVolume,
  });

  factory TelemetryModel.fromJson(Map<String, dynamic> json) {
    return TelemetryModel(
      deviceId: json['device_id'] as String? ?? '',
      timestamp: (json['timestamp'] as num?)?.toInt() ?? 0,
      batteryPercentage: (json['battery_percentage'] as num?)?.toInt() ?? 0,
      temperatureCelsius: (json['temperature_celsius'] as num?)?.toDouble() ?? 0.0,
      cpuUsage: (json['cpu_usage'] as num?)?.toDouble() ?? 0.0,
      ultrasonicDistanceCm: (json['ultrasonic_distance_cm'] as num?)?.toDouble() ?? -1.0,
      cameraActive: json['camera_active'] as bool? ?? false,
      speakerVolume: (json['speaker_volume'] as num?)?.toInt() ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
    'device_id': deviceId,
    'timestamp': timestamp,
    'battery_percentage': batteryPercentage,
    'temperature_celsius': temperatureCelsius,
    'cpu_usage': cpuUsage,
    'ultrasonic_distance_cm': ultrasonicDistanceCm,
    'camera_active': cameraActive,
    'speaker_volume': speakerVolume,
  };

  TelemetryEntity toEntity() => this;

  factory TelemetryModel.fromEntity(TelemetryEntity entity) {
    return TelemetryModel(
      deviceId: entity.deviceId,
      timestamp: entity.timestamp,
      batteryPercentage: entity.batteryPercentage,
      temperatureCelsius: entity.temperatureCelsius,
      cpuUsage: entity.cpuUsage,
      ultrasonicDistanceCm: entity.ultrasonicDistanceCm,
      cameraActive: entity.cameraActive,
      speakerVolume: entity.speakerVolume,
    );
  }
}
