import '../entities/alert_entity.dart';

abstract class AlertRepository {
  Stream<AlertEntity> get alertStream;
  List<AlertEntity> get cachedAlerts;
  List<AlertEntity> get alertHistory => cachedAlerts;
  void clearAlerts();
  void clearHistory();
  void dismissAlert(String eventId);
}
