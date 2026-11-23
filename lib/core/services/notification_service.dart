import 'dart:async';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:permission_handler/permission_handler.dart';
import '../../domain/entities/alert_entity.dart';

class NotificationService {
  final FlutterLocalNotificationsPlugin _notifications;
  static const String channelId = 'pbl6_critical_alerts';
  static const String channelName = 'PBL6 Critical Alerts';
  static const String channelDesc = 'Urgent hazard warnings with sound and vibration';

  NotificationService({FlutterLocalNotificationsPlugin? plugin})
      : _notifications = plugin ?? FlutterLocalNotificationsPlugin();

  Future<void> initialize({DidReceiveNotificationResponseCallback? onDidReceive}) async {
    const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
    const initSettings = InitializationSettings(android: androidSettings);
    await _notifications.initialize(
      settings: initSettings,
      onDidReceiveNotificationResponse: onDidReceive,
    );
    final androidPlugin = _notifications.resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin>();
    if (androidPlugin != null) {
      const channel = AndroidNotificationChannel(
        channelId,
        channelName,
        description: channelDesc,
        importance: Importance.max,
        playSound: true,
        enableVibration: true,
      );
      await androidPlugin.createNotificationChannel(channel);
    }
  }

  Future<bool> requestPermissions() async {
    final status = await Permission.notification.request();
    return status.isGranted;
  }

  Future<void> showAlertNotification(AlertEntity alert) async {
    final androidDetails = AndroidNotificationDetails(
      channelId,
      channelName,
      channelDescription: channelDesc,
      importance: Importance.max,
      priority: Priority.high,
      fullScreenIntent: true,
      enableVibration: true,
      playSound: true,
      styleInformation: BigTextStyleInformation(
        alert.message,
        contentTitle: '[${alert.level}] ${alert.alertType}',
        summaryText: alert.detectedObjects.isNotEmpty
            ? 'Vật thể: ${alert.detectedObjects.join(', ')}'
            : null,
      ),
    );
    final details = NotificationDetails(android: androidDetails);
    final noteId = alert.eventId.hashCode & 0x7FFFFFFF;
    await _notifications.show(
      id: noteId,
      title: '[${alert.level}] ${alert.alertType}',
      body: alert.message,
      notificationDetails: details,
      payload: alert.eventId,
    );
  }
}
