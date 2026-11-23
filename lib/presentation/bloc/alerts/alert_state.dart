part of 'alert_bloc.dart';

abstract class AlertState extends Equatable {
  const AlertState();

  @override
  List<Object?> get props => [];
}

class AlertInitial extends AlertState {}

class AlertEmpty extends AlertState {}

class AlertActive extends AlertState {
  final AlertEntity latestAlert;
  final List<AlertEntity> alertHistory;

  const AlertActive({
    required this.latestAlert,
    required this.alertHistory,
  });

  @override
  List<Object?> get props => [latestAlert, alertHistory];
}

class AlertError extends AlertState {
  final String message;

  const AlertError({required this.message});

  @override
  List<Object?> get props => [message];
}
