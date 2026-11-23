import 'dart:async';
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../domain/entities/telemetry_entity.dart';
import '../../../domain/repositories/telemetry_repository.dart';

part 'dashboard_event.dart';
part 'dashboard_state.dart';

class DashboardBloc extends Bloc<DashboardEvent, DashboardState> {
  final TelemetryRepository telemetryRepository;
  final Duration staleTimeout;

  StreamSubscription<TelemetryEntity>? _telemetrySubscription;
  Timer? _staleTimer;

  DashboardBloc({
    required this.telemetryRepository,
    this.staleTimeout = const Duration(seconds: 10),
  }) : super(DashboardInitial()) {
    on<StartTelemetrySubscription>(_onStartTelemetrySubscription);
    on<TelemetryUpdated>(_onTelemetryUpdated);
    on<StopTelemetrySubscription>(_onStopTelemetrySubscription);
    on<_TelemetryStaleDetected>(_onTelemetryStaleDetected);
    on<_TelemetryErrorOccurred>(_onTelemetryErrorOccurred);
  }

  Future<void> _onStartTelemetrySubscription(
    StartTelemetrySubscription event,
    Emitter<DashboardState> emit,
  ) async {
    emit(DashboardLoading());
    final latest = telemetryRepository.latestTelemetry;
    if (latest != null) {
      emit(DashboardLoaded(telemetry: latest, isStale: false));
      _resetStaleTimer();
    }

    await _telemetrySubscription?.cancel();
    _telemetrySubscription = telemetryRepository.telemetryStream.listen(
      (telemetry) => add(TelemetryUpdated(telemetry: telemetry)),
      onError: (error) => add(_TelemetryErrorOccurred(error.toString())),
    );
  }

  void _onTelemetryUpdated(
    TelemetryUpdated event,
    Emitter<DashboardState> emit,
  ) {
    _resetStaleTimer();
    emit(DashboardLoaded(telemetry: event.telemetry, isStale: event.isStale));
  }

  Future<void> _onStopTelemetrySubscription(
    StopTelemetrySubscription event,
    Emitter<DashboardState> emit,
  ) async {
    _staleTimer?.cancel();
    _staleTimer = null;
    await _telemetrySubscription?.cancel();
    _telemetrySubscription = null;
    emit(DashboardInitial());
  }

  void _onTelemetryStaleDetected(
    _TelemetryStaleDetected event,
    Emitter<DashboardState> emit,
  ) {
    if (state is DashboardLoaded) {
      final current = (state as DashboardLoaded).telemetry;
      emit(DashboardLoaded(telemetry: current, isStale: true));
    }
  }

  void _onTelemetryErrorOccurred(
    _TelemetryErrorOccurred event,
    Emitter<DashboardState> emit,
  ) {
    _staleTimer?.cancel();
    _staleTimer = null;
    emit(DashboardError(message: event.message));
  }

  void _resetStaleTimer() {
    _staleTimer?.cancel();
    _staleTimer = Timer(staleTimeout, () {
      add(const _TelemetryStaleDetected());
    });
  }

  @override
  Future<void> close() {
    _staleTimer?.cancel();
    _telemetrySubscription?.cancel();
    return super.close();
  }
}
