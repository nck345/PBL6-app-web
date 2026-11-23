class AppConstants {
  static const String appTitle = 'PBL6 Assistive Monitor';
  static const String defaultMqttBroker = 'broker.hivemq.com';
  static const int defaultMqttPort = 1883;
  static const int defaultMqttWebsocketPort = 8000;
  static const String defaultDeviceId = 'pi4_01';
  static const String defaultStunServer = 'stun:stun.l.google.com:19302';

  static const int defaultDistanceThresholdCm = 80;
  static const int defaultSpeakerVolume = 80;
  static const int defaultAlertFrequencyMs = 500;
  static const int defaultDetectionFps = 15;

  static String telemetryTopic(String deviceId) => 'pbl6/$deviceId/telemetry';
  static String alertTopic(String deviceId) => 'pbl6/$deviceId/alert';
  static String configTopic(String deviceId) => 'pbl6/$deviceId/config';
  static String commandTopic(String deviceId) => 'pbl6/$deviceId/command';
  static String statusTopic(String deviceId) => 'pbl6/$deviceId/status';
  static String webrtcOfferTopic(String deviceId) => 'pbl6/$deviceId/webrtc/offer';
  static String webrtcAnswerTopic(String deviceId) => 'pbl6/$deviceId/webrtc/answer';
  static String webrtcIceTopic(String deviceId) => 'pbl6/$deviceId/webrtc/ice_candidate';
}
