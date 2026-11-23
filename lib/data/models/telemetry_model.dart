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
    super.latitude,
    super.longitude,
    super.speedKmh,
    super.headingDegrees,
    super.hasGpsFix = false,
    super.satellites,
    super.altitudeM,
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
      latitude: (json['latitude'] as num?)?.toDouble(),
      longitude: (json['longitude'] as num?)?.toDouble(),
      speedKmh: (json['speed_kmh'] as num?)?.toDouble(),
      headingDegrees: (json['heading_degrees'] as num?)?.toDouble(),
      hasGpsFix: json['has_gps_fix'] as bool? ?? false,
      satellites: (json['satellites'] as num?)?.toInt(),
      altitudeM: (json['altitude_m'] as num?)?.toDouble(),
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
    'latitude': latitude,
    'longitude': longitude,
    'speed_kmh': speedKmh,
    'heading_degrees': headingDegrees,
    'has_gps_fix': hasGpsFix,
    'satellites': satellites,
    'altitude_m': altitudeM,
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
      latitude: entity.latitude,
      longitude: entity.longitude,
      speedKmh: entity.speedKmh,
      headingDegrees: entity.headingDegrees,
      hasGpsFix: entity.hasGpsFix,
      satellites: entity.satellites,
      altitudeM: entity.altitudeM,
    );
  }
}
