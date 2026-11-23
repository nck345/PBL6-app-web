import 'package:equatable/equatable.dart';

class AlertEntity extends Equatable {
  final String eventId;
  final int timestamp;
  final String alertType;
  final String level;
  final double distanceCm;
  final List<String> detectedObjects;
  final String message;
  final bool isAcknowledged;

  const AlertEntity({
    required this.eventId,
    required this.timestamp,
    required this.alertType,
    required this.level,
    required this.distanceCm,
    required this.detectedObjects,
    required this.message,
    this.isAcknowledged = false,
  });

  bool get isCritical => level.toUpperCase() == 'CRITICAL';
  bool get isWarning => level.toUpperCase() == 'WARNING';
  bool get isInfo => level.toUpperCase() == 'INFO';
  DateTime get dateTime => DateTime.fromMillisecondsSinceEpoch(timestamp * 1000);

  AlertEntity copyWith({
    String? eventId,
    int? timestamp,
    String? alertType,
    String? level,
    double? distanceCm,
    List<String>? detectedObjects,
    String? message,
    bool? isAcknowledged,
  }) {
    return AlertEntity(
      eventId: eventId ?? this.eventId,
      timestamp: timestamp ?? this.timestamp,
      alertType: alertType ?? this.alertType,
      level: level ?? this.level,
      distanceCm: distanceCm ?? this.distanceCm,
      detectedObjects: detectedObjects ?? this.detectedObjects,
      message: message ?? this.message,
      isAcknowledged: isAcknowledged ?? this.isAcknowledged,
    );
  }

  @override
  List<Object?> get props => [
    eventId,
    timestamp,
    alertType,
    level,
    distanceCm,
    detectedObjects,
    message,
    isAcknowledged,
  ];
}
