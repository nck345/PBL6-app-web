part of 'dashboard_bloc.dart';

abstract class DashboardEvent extends Equatable {
  const DashboardEvent();

  @override
  List<Object?> get props => [];
}

class StartTelemetrySubscription extends DashboardEvent {
  const StartTelemetrySubscription();
}

class TelemetryUpdated extends DashboardEvent {
  final TelemetryEntity telemetry;
  final bool isStale;

  const TelemetryUpdated({
    required this.telemetry,
    this.isStale = false,
  });

  @override
  List<Object?> get props => [telemetry, isStale];
}

class StopTelemetrySubscription extends DashboardEvent {
  const StopTelemetrySubscription();
}

class _TelemetryStaleDetected extends DashboardEvent {
  const _TelemetryStaleDetected();
}

class _TelemetryErrorOccurred extends DashboardEvent {
  final String message;

  const _TelemetryErrorOccurred(this.message);

  @override
  List<Object?> get props => [message];
}
