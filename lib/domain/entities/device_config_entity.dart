import 'package:equatable/equatable.dart';
import '../../core/constants/app_constants.dart';

class DeviceConfigEntity extends Equatable {
  final int distanceThresholdCm;
  final int speakerVolume;
  final int alertFrequencyMs;
  final int detectionFps;

  const DeviceConfigEntity({
    required this.distanceThresholdCm,
    required this.speakerVolume,
    required this.alertFrequencyMs,
    required this.detectionFps,
  });

  static const initial = DeviceConfigEntity(
    distanceThresholdCm: AppConstants.defaultDistanceThresholdCm,
    speakerVolume: AppConstants.defaultSpeakerVolume,
    alertFrequencyMs: AppConstants.defaultAlertFrequencyMs,
    detectionFps: AppConstants.defaultDetectionFps,
  );

  static DeviceConfigEntity defaultConfig() => initial;

  DeviceConfigEntity copyWith({
    int? distanceThresholdCm,
    int? speakerVolume,
    int? alertFrequencyMs,
    int? detectionFps,
  }) {
    return DeviceConfigEntity(
      distanceThresholdCm: distanceThresholdCm ?? this.distanceThresholdCm,
      speakerVolume: speakerVolume ?? this.speakerVolume,
      alertFrequencyMs: alertFrequencyMs ?? this.alertFrequencyMs,
      detectionFps: detectionFps ?? this.detectionFps,
    );
  }

  @override
  List<Object?> get props => [
    distanceThresholdCm,
    speakerVolume,
    alertFrequencyMs,
    detectionFps,
  ];
}
