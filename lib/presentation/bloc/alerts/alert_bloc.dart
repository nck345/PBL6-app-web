import 'dart:async';
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/services/notification_service.dart';
import '../../../domain/entities/alert_entity.dart';
import '../../../domain/repositories/alert_repository.dart';

part 'alert_event.dart';
part 'alert_state.dart';

class AlertBloc extends Bloc<AlertEvent, AlertState> {
  final AlertRepository alertRepository;
  final NotificationService? notificationService;
  final int maxHistory;

  final List<AlertEntity> _history = [];
  StreamSubscription<AlertEntity>? _alertSubscription;

  AlertBloc({
    required this.alertRepository,
    this.notificationService,
    this.maxHistory = 100,
  }) : super(AlertInitial()) {
    on<StartAlertSubscription>(_onStartAlertSubscription);
    on<AlertReceived>(_onAlertReceived);
    on<AcknowledgeAlert>(_onAcknowledgeAlert);
    on<ClearAlerts>(_onClearAlerts);
    on<_AlertErrorOccurred>(_onAlertErrorOccurred);
  }

  Future<void> _onStartAlertSubscription(
    StartAlertSubscription event,
    Emitter<AlertState> emit,
  ) async {
    emit(AlertInitial());
    _history.clear();
    _history.addAll(alertRepository.cachedAlerts);

    if (_history.isEmpty) {
      emit(AlertEmpty());
    } else {
      emit(AlertActive(
        latestAlert: _history.first,
        alertHistory: List.unmodifiable(_history),
      ));
    }

    await _alertSubscription?.cancel();
    _alertSubscription = alertRepository.alertStream.listen(
      (alert) => add(AlertReceived(alert: alert)),
      onError: (error) => add(_AlertErrorOccurred(error.toString())),
    );
  }

  Future<void> _onAlertReceived(
    AlertReceived event,
    Emitter<AlertState> emit,
  ) async {
    final alert = event.alert;

    if (alert.level.toUpperCase() == 'CRITICAL') {
      try {
        await notificationService?.showAlertNotification(alert);
      } catch (_) {}
    }

    _history.insert(0, alert);
    if (_history.length > maxHistory) {
      _history.removeLast();
    }

    emit(AlertActive(
      latestAlert: alert,
      alertHistory: List.unmodifiable(_history),
    ));
  }

  void _onAcknowledgeAlert(
    AcknowledgeAlert event,
    Emitter<AlertState> emit,
  ) {
    final index = _history.indexWhere((a) => a.eventId == event.eventId);
    if (index != -1) {
      final updated = _history[index].copyWith(isAcknowledged: true);
      _history[index] = updated;
    }

    if (_history.isEmpty) {
      emit(AlertEmpty());
    } else {
      emit(AlertActive(
        latestAlert: _history.first,
        alertHistory: List.unmodifiable(_history),
      ));
    }
  }

  void _onClearAlerts(
    ClearAlerts event,
    Emitter<AlertState> emit,
  ) {
    _history.clear();
    alertRepository.clearAlerts();
    emit(AlertEmpty());
  }

  void _onAlertErrorOccurred(
    _AlertErrorOccurred event,
    Emitter<AlertState> emit,
  ) {
    emit(AlertError(message: event.message));
  }

  @override
  Future<void> close() {
    _alertSubscription?.cancel();
    return super.close();
  }
}
