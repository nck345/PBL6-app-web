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

  const TelemetryEntity({
    required this.deviceId,
    required this.timestamp,
    required this.batteryPercentage,
    required this.temperatureCelsius,
    required this.cpuUsage,
    required this.ultrasonicDistanceCm,
    required this.cameraActive,
    required this.speakerVolume,
  });

  bool get isObstacleNear => ultrasonicDistanceCm >= 0 && ultrasonicDistanceCm < 80.0;
  bool get isBatteryLow => batteryPercentage < 20;
  bool get isOverheating => temperatureCelsius > 70.0;

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
  ];
}
