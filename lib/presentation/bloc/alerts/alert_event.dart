part of 'alert_bloc.dart';

abstract class AlertEvent extends Equatable {
  const AlertEvent();

  @override
  List<Object?> get props => [];
}

class StartAlertSubscription extends AlertEvent {
  const StartAlertSubscription();
}

class AlertReceived extends AlertEvent {
  final AlertEntity alert;

  const AlertReceived({required this.alert});

  @override
  List<Object?> get props => [alert];
}

class ClearAlerts extends AlertEvent {
  const ClearAlerts();
}

class AcknowledgeAlert extends AlertEvent {
  final String eventId;

  const AcknowledgeAlert({required this.eventId});

  @override
  List<Object?> get props => [eventId];
}

class _AlertErrorOccurred extends AlertEvent {
  final String message;

  const _AlertErrorOccurred(this.message);

  @override
  List<Object?> get props => [message];
}
