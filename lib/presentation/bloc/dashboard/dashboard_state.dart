part of 'dashboard_bloc.dart';

abstract class DashboardState extends Equatable {
  const DashboardState();

  @override
  List<Object?> get props => [];
}

class DashboardInitial extends DashboardState {}

class DashboardLoading extends DashboardState {}

class DashboardLoaded extends DashboardState {
  final TelemetryEntity telemetry;
  final bool isStale;

  const DashboardLoaded({
    required this.telemetry,
    this.isStale = false,
  });

  DashboardLoaded copyWith({
    TelemetryEntity? telemetry,
    bool? isStale,
  }) {
    return DashboardLoaded(
      telemetry: telemetry ?? this.telemetry,
      isStale: isStale ?? this.isStale,
    );
  }

  @override
  List<Object?> get props => [telemetry, isStale];
}

class DashboardError extends DashboardState {
  final String message;

  const DashboardError({required this.message});

  @override
  List<Object?> get props => [message];
}
