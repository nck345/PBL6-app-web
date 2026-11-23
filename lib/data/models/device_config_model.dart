import '../../core/constants/app_constants.dart';
import '../../domain/entities/device_config_entity.dart';

class DeviceConfigModel extends DeviceConfigEntity {
  const DeviceConfigModel({
    required super.distanceThresholdCm,
    required super.speakerVolume,
    required super.alertFrequencyMs,
    required super.detectionFps,
  });

  factory DeviceConfigModel.fromJson(Map<String, dynamic> json) {
    return DeviceConfigModel(
      distanceThresholdCm: (json['distance_threshold_cm'] as num?)?.toInt() ??
          AppConstants.defaultDistanceThresholdCm,
      speakerVolume: (json['speaker_volume'] as num?)?.toInt() ??
          AppConstants.defaultSpeakerVolume,
      alertFrequencyMs: (json['alert_frequency_ms'] as num?)?.toInt() ??
          AppConstants.defaultAlertFrequencyMs,
      detectionFps: (json['detection_fps'] as num?)?.toInt() ??
          AppConstants.defaultDetectionFps,
    );
  }

  Map<String, dynamic> toJson() => {
    'distance_threshold_cm': distanceThresholdCm,
    'speaker_volume': speakerVolume,
    'alert_frequency_ms': alertFrequencyMs,
    'detection_fps': detectionFps,
  };

  DeviceConfigEntity toEntity() => this;

  factory DeviceConfigModel.fromEntity(DeviceConfigEntity entity) {
    return DeviceConfigModel(
      distanceThresholdCm: entity.distanceThresholdCm,
      speakerVolume: entity.speakerVolume,
      alertFrequencyMs: entity.alertFrequencyMs,
      detectionFps: entity.detectionFps,
    );
  }
}
