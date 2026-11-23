import 'package:equatable/equatable.dart';

class TelemetryEntity extends Equatable {
  final String deviceId;
  final int timestamp;
  final int batteryPercentage;
  final double temperatureCelsius;
  final double cpuUsage;
  final double ultrasonicDistanceCm;
  final bool cameraActive;
  final int speakerVolume;
  final double? latitude;
  final double? longitude;
  final double? speedKmh;
  final double? headingDegrees;
  final bool hasGpsFix;
  final int? satellites;
  final double? altitudeM;

  const TelemetryEntity({
    required this.deviceId,
    required this.timestamp,
    required this.batteryPercentage,
    required this.temperatureCelsius,
    required this.cpuUsage,
    required this.ultrasonicDistanceCm,
    required this.cameraActive,
    required this.speakerVolume,
    this.latitude,
    this.longitude,
    this.speedKmh,
    this.headingDegrees,
    this.hasGpsFix = false,
    this.satellites,
    this.altitudeM,
  });

  bool get isSensorConnected => ultrasonicDistanceCm >= 0.0;
  bool get isObstacleNear => isSensorConnected && ultrasonicDistanceCm < 80.0;
  bool get isBatteryLow => batteryPercentage < 20;
  bool get isOverheating => temperatureCelsius > 70.0;
  bool get isGpsAvailable => hasGpsFix && latitude != null && longitude != null;
  String get coordinatesDisplay => isGpsAvailable
      ? '${latitude!.toStringAsFixed(6)}°, ${longitude!.toStringAsFixed(6)}°'
      : 'Chưa có tín hiệu GPS';

  @override
  List<Object?> get props => [
    deviceId,
    timestamp,
    batteryPercentage,
    temperatureCelsius,
    cpuUsage,
    ultrasonicDistanceCm,
    cameraActive,
    speakerVolume,
    latitude,
    longitude,
    speedKmh,
    headingDegrees,
    hasGpsFix,
    satellites,
    altitudeM,
  ];
}
