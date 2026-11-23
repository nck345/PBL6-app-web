import 'package:mqtt_client/mqtt_browser_client.dart';
import 'package:mqtt_client/mqtt_client.dart';

MqttClient createMqttClient(String broker, String clientId, int port) {
	String serverUri = broker;
	if (!serverUri.startsWith('ws://') && !serverUri.startsWith('wss://')) {
		serverUri = 'ws://$broker/mqtt';
	}
	final client = MqttBrowserClient.withPort(serverUri, clientId, port);
	client.websocketProtocols = MqttClientConstants.protocolsMultipleDefault;
	return client;
}
