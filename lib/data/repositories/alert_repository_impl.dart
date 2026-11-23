import 'dart:async';
import '../../domain/entities/alert_entity.dart';
import '../../domain/repositories/alert_repository.dart';
import '../datasources/mqtt_datasource.dart';
import '../models/alert_model.dart';

class AlertRepositoryImpl implements AlertRepository {
  final MqttDatasource mqttDataSource;
  final List<AlertEntity> _history = [];
  static const int maxHistorySize = 100;
  late final StreamController<AlertEntity> _controller;
  StreamSubscription? _subscription;

  AlertRepositoryImpl({required this.mqttDataSource}) {
    _controller = StreamController<AlertEntity>.broadcast();
    _subscription = mqttDataSource.alertStream.listen((json) {
      try {
        final entity = AlertModel.fromJson(json).toEntity();
        _history.insert(0, entity);
        if (_history.length > maxHistorySize) {
          _history.removeLast();
        }
        _controller.add(entity);
      } catch (_) {}
    });
  }

  @override
  Stream<AlertEntity> get alertStream => _controller.stream;

  @override
  List<AlertEntity> get cachedAlerts => List.unmodifiable(_history);

  @override
  List<AlertEntity> get alertHistory => List.unmodifiable(_history);

  @override
  void clearAlerts() {
    _history.clear();
  }

  @override
  void clearHistory() {
    clearAlerts();
  }

  @override
  void dismissAlert(String eventId) {
    _history.removeWhere((a) => a.eventId == eventId);
  }

  void dispose() {
    _subscription?.cancel();
    _controller.close();
  }
}
