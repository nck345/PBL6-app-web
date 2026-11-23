import '../../domain/entities/alert_entity.dart';

class AlertModel extends AlertEntity {
  const AlertModel({
    required super.eventId,
    required super.timestamp,
    required super.alertType,
    required super.level,
    required super.distanceCm,
    required super.detectedObjects,
    required super.message,
    super.isAcknowledged = false,
  });

  factory AlertModel.fromJson(Map<String, dynamic> json) {
    return AlertModel(
      eventId: json['event_id'] as String? ?? '',
      timestamp: (json['timestamp'] as num?)?.toInt() ?? 0,
      alertType: json['alert_type'] as String? ?? 'UNKNOWN',
      level: json['level'] as String? ?? 'INFO',
      distanceCm: (json['distance_cm'] as num?)?.toDouble() ?? -1.0,
      detectedObjects: (json['detected_objects'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          const [],
      message: json['message'] as String? ?? '',
      isAcknowledged: json['is_acknowledged'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
    'event_id': eventId,
    'timestamp': timestamp,
    'alert_type': alertType,
    'level': level,
    'distance_cm': distanceCm,
    'detected_objects': detectedObjects,
    'message': message,
  };

  AlertEntity toEntity() => this;

  factory AlertModel.fromEntity(AlertEntity entity) {
    return AlertModel(
      eventId: entity.eventId,
      timestamp: entity.timestamp,
      alertType: entity.alertType,
      level: entity.level,
      distanceCm: entity.distanceCm,
      detectedObjects: entity.detectedObjects,
      message: entity.message,
      isAcknowledged: entity.isAcknowledged,
    );
  }
}
