import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:mqtt_client/mqtt_client.dart';
import 'package:uuid/uuid.dart';
import '../../core/constants/app_constants.dart';
import 'mqtt_client_factory.dart';

class MqttDatasource {
  MqttClient? _client;
  String? _currentDeviceId;

  final StreamController<String> _statusController =
      StreamController<String>.broadcast();
  final StreamController<Map<String, dynamic>> _telemetryController =
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _alertController =
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _configController =
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _commandController =
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _deviceStatusController =
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _webrtcAnswerController =
      StreamController<Map<String, dynamic>>.broadcast();
  final StreamController<Map<String, dynamic>> _webrtcIceController =
      StreamController<Map<String, dynamic>>.broadcast();

  Stream<String> get connectionStatusStream => _statusController.stream;
  Stream<Map<String, dynamic>> get telemetryStream => _telemetryController.stream;
  Stream<Map<String, dynamic>> get alertStream => _alertController.stream;
  Stream<Map<String, dynamic>> get configStream => _configController.stream;
  Stream<Map<String, dynamic>> get commandStream => _commandController.stream;
  Stream<Map<String, dynamic>> get deviceStatusStream => _deviceStatusController.stream;
  Stream<Map<String, dynamic>> get webrtcAnswerStream => _webrtcAnswerController.stream;
  Stream<Map<String, dynamic>> get webrtcIceStream => _webrtcIceController.stream;

  bool get isConnected => _client?.connectionStatus?.state == MqttConnectionState.connected;

  Future<bool> connect({
    String broker = AppConstants.defaultMqttBroker,
    int port = AppConstants.defaultMqttPort,
    String? clientIdentifier,
    String deviceId = AppConstants.defaultDeviceId,
  }) async {
    if (_client != null) {
      _client?.disconnect();
    }
    _currentDeviceId = deviceId;
    final clientId = clientIdentifier ?? 'pbl6_app_${const Uuid().v4().substring(0, 8)}';
    _statusController.add('connecting');

    final effectivePort = (port == AppConstants.defaultMqttPort && kIsWeb)
        ? AppConstants.defaultMqttWebsocketPort
        : port;
    final client = createMqttClient(broker, clientId, effectivePort);
    client.keepAlivePeriod = 30;
    client.autoReconnect = true;
    client.resubscribeOnAutoReconnect = true;
    client.logging(on: false);

    final lwtPayload = jsonEncode({
      'status': 'offline',
      'timestamp': DateTime.now().millisecondsSinceEpoch ~/ 1000,
    });
    client.connectionMessage = MqttConnectMessage()
        .withClientIdentifier(clientId)
        .startClean()
        .withWillTopic(AppConstants.statusTopic(deviceId))
        .withWillMessage(lwtPayload)
        .withWillQos(MqttQos.atLeastOnce)
        .withWillRetain();

    client.onConnected = () {
      _statusController.add('connected');
      _subscribeToTopics(deviceId);
    };
    client.onDisconnected = () {
      _statusController.add('disconnected');
    };
    client.onAutoReconnect = () {
      _statusController.add('reconnecting');
    };
    client.onAutoReconnected = () {
      _statusController.add('connected');
    };

    client.setProtocolV311();
    _client = client;
    try {
      final status = await client.connect().timeout(
        const Duration(seconds: 8),
        onTimeout: () {
          _statusController.add('error');
          return null;
        },
      );
      if (status?.state == MqttConnectionState.connected) {
        _listenToUpdates();
        return true;
      }
      _statusController.add('error');
      return false;
    } catch (_) {
      _statusController.add('error');
      return false;
    }
  }

  void _subscribeToTopics(String deviceId) {
    if (_client == null) return;
    _client!.subscribe(AppConstants.telemetryTopic(deviceId), MqttQos.atMostOnce);
    _client!.subscribe(AppConstants.alertTopic(deviceId), MqttQos.atLeastOnce);
    _client!.subscribe(AppConstants.configTopic(deviceId), MqttQos.atLeastOnce);
    _client!.subscribe(AppConstants.commandTopic(deviceId), MqttQos.atLeastOnce);
    _client!.subscribe(AppConstants.statusTopic(deviceId), MqttQos.atLeastOnce);
    _client!.subscribe(AppConstants.webrtcAnswerTopic(deviceId), MqttQos.atLeastOnce);
    _client!.subscribe(AppConstants.webrtcIceTopic(deviceId), MqttQos.atLeastOnce);
  }

  void subscribeWebRtc(String deviceId) {
    if (_client == null || !isConnected) return;
    _client!.subscribe(AppConstants.webrtcAnswerTopic(deviceId), MqttQos.atLeastOnce);
    _client!.subscribe(AppConstants.webrtcIceTopic(deviceId), MqttQos.atLeastOnce);
  }

  void unsubscribeWebRtc(String deviceId) {
    if (_client == null || !isConnected) return;
    _client!.unsubscribe(AppConstants.webrtcAnswerTopic(deviceId));
    _client!.unsubscribe(AppConstants.webrtcIceTopic(deviceId));
  }

  void _listenToUpdates() {
    _client?.updates?.listen((List<MqttReceivedMessage<MqttMessage>> messages) {
      for (final msg in messages) {
        final topic = msg.topic;
        final pubMsg = msg.payload as MqttPublishMessage;
        final payloadStr = MqttPublishPayload.bytesToStringAsString(pubMsg.payload.message);
        if (payloadStr.isEmpty) continue;
        try {
          final decoded = jsonDecode(payloadStr);
          if (decoded is! Map<String, dynamic>) continue;
          if (_currentDeviceId == null) continue;
          if (topic == AppConstants.telemetryTopic(_currentDeviceId!)) {
            _telemetryController.add(decoded);
          } else if (topic == AppConstants.alertTopic(_currentDeviceId!)) {
            _alertController.add(decoded);
          } else if (topic == AppConstants.configTopic(_currentDeviceId!)) {
            _configController.add(decoded);
          } else if (topic == AppConstants.commandTopic(_currentDeviceId!)) {
            _commandController.add(decoded);
          } else if (topic == AppConstants.statusTopic(_currentDeviceId!)) {
            _deviceStatusController.add(decoded);
          } else if (topic == AppConstants.webrtcAnswerTopic(_currentDeviceId!)) {
            _webrtcAnswerController.add(decoded);
          } else if (topic == AppConstants.webrtcIceTopic(_currentDeviceId!)) {
            _webrtcIceController.add(decoded);
          }
        } catch (_) {}
      }
    });
  }

  Future<void> publish(
    String topic,
    String payload, {
    MqttQos qos = MqttQos.atLeastOnce,
    bool retain = false,
  }) async {
    if (!isConnected) throw StateError('MQTT client is not connected');
    final builder = MqttClientPayloadBuilder();
    builder.addString(payload);
    _client!.publishMessage(topic, qos, builder.payload!, retain: retain);
  }

  Future<void> publishConfig(String deviceId, Map<String, dynamic> configJson) async {
    await publish(
      AppConstants.configTopic(deviceId),
      jsonEncode(configJson),
      qos: MqttQos.atLeastOnce,
      retain: true,
    );
  }

  Future<void> publishCommand(String deviceId, String command, {String? requestId}) async {
    final data = <String, dynamic>{'command': command};
    if (requestId != null) data['request_id'] = requestId;
    await publish(
      AppConstants.commandTopic(deviceId),
      jsonEncode(data),
      qos: MqttQos.atLeastOnce,
      retain: false,
    );
  }

  Future<void> publishStatus(String deviceId, String status) async {
    final data = {
      'status': status,
      'timestamp': DateTime.now().millisecondsSinceEpoch ~/ 1000,
    };
    await publish(
      AppConstants.statusTopic(deviceId),
      jsonEncode(data),
      qos: MqttQos.atLeastOnce,
      retain: true,
    );
  }

  Future<void> publishWebRtcOffer(String deviceId, Map<String, dynamic> offerJson) async {
    await publish(
      AppConstants.webrtcOfferTopic(deviceId),
      jsonEncode(offerJson),
      qos: MqttQos.atLeastOnce,
    );
  }

  Future<void> publishWebRtcIce(String deviceId, Map<String, dynamic> iceJson) async {
    await publish(
      AppConstants.webrtcIceTopic(deviceId),
      jsonEncode(iceJson),
      qos: MqttQos.atLeastOnce,
    );
  }

  Future<void> publishWebRtcCandidate(String deviceId, Map<String, dynamic> candidateJson) async =>
      publishWebRtcIce(deviceId, candidateJson);

  Future<void> disconnect() async {
    _client?.disconnect();
    _statusController.add('disconnected');
  }

  void dispose() {
    _client?.disconnect();
    _statusController.close();
    _telemetryController.close();
    _alertController.close();
    _configController.close();
    _commandController.close();
    _deviceStatusController.close();
    _webrtcAnswerController.close();
    _webrtcIceController.close();
  }
}

typedef MqttDataSource = MqttDatasource;
