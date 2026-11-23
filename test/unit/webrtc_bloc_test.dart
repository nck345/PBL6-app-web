import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:pbl6_app/data/datasources/mqtt_datasource.dart';
import 'package:pbl6_app/data/datasources/webrtc_datasource.dart';
import 'package:pbl6_app/presentation/bloc/webrtc/webrtc_bloc.dart';
class FakeWebrtcDatasource implements WebrtcDatasource {
	final StreamController<RTCPeerConnectionState> _controller = StreamController<RTCPeerConnectionState>.broadcast();
	final RTCVideoRenderer fakeRenderer = RTCVideoRenderer();
	bool connectSuccess = true;
	bool shouldThrow = false;
	bool shouldThrowInit = false;
	bool micEnabled = false;
	int disconnectCallCount = 0;
	@override
	MqttDatasource get mqttDatasource => throw UnimplementedError();
	@override
	RTCVideoRenderer get videoRenderer => fakeRenderer;
	@override
	Stream<RTCPeerConnectionState> get connectionStateStream => _controller.stream;
	@override
	bool get isMicrophoneEnabled => micEnabled;
	@override
	RTCPeerConnection? get peerConnection => null;
	@override
	Future<void> initialize() async {
		if (shouldThrowInit) throw Exception('Renderer initialization failed');
	}
	@override
	Future<void> connect(String deviceId) async {
		if (shouldThrow) throw Exception('STUN/ICE negotiation failed');
		if (connectSuccess) {
			_controller.add(RTCPeerConnectionState.RTCPeerConnectionStateConnected);
		} else {
			_controller.add(RTCPeerConnectionState.RTCPeerConnectionStateFailed);
		}
	}
	@override
	Future<void> disconnect() async {
		++disconnectCallCount;
		_controller.add(RTCPeerConnectionState.RTCPeerConnectionStateClosed);
	}
	@override
	Future<void> setMicrophoneEnabled(bool enabled) async {
		micEnabled = enabled;
	}
	void emitConnectionState(RTCPeerConnectionState state) {
		_controller.add(state);
	}
	void emitError(Object error) {
		_controller.addError(error);
	}
	@override
	Future<void> dispose() async {
		await _controller.close();
	}
	@override
	dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
void main() {
	group('WebRtcBloc Unit Tests', () {
		late FakeWebrtcDatasource fakeDatasource;
		late WebRtcBloc bloc;
		setUp(() {
			fakeDatasource = FakeWebrtcDatasource();
			bloc = WebRtcBloc(webrtcDatasource: fakeDatasource);
		});
		tearDown(() async {
			await bloc.close();
			await fakeDatasource.dispose();
		});
		test('Initial state is WebRtcInitial', () {
			expect(bloc.state, equals(const WebRtcInitial()));
		});
		test('InitializeWebRtcEvent success maintains WebRtcInitial', () async {
			final expected = [const WebRtcInitial()];
			expectLater(bloc.stream, emitsInOrder(expected));
			bloc.add(const InitializeWebRtcEvent());
		});
		test('InitializeWebRtcEvent failure emits WebRtcFailure', () async {
			fakeDatasource.shouldThrowInit = true;
			final expected = [const WebRtcFailure(message: 'Initialization failed: Exception: Renderer initialization failed')];
			expectLater(bloc.stream, emitsInOrder(expected));
			bloc.add(const InitializeWebRtcEvent());
		});
		test('ConnectWebRtcEvent emits [WebRtcConnecting, WebRtcConnected] on success', () async {
			final expected = [
				const WebRtcConnecting(),
				WebRtcConnected(renderer: fakeDatasource.fakeRenderer, isPttActive: false),
			];
			expectLater(bloc.stream, emitsInOrder(expected));
			bloc.add(const ConnectWebRtcEvent());
		});
		test('ConnectWebRtcEvent emits [WebRtcConnecting, WebRtcFailure] when connect throws', () async {
			fakeDatasource.shouldThrow = true;
			final expected = [
				const WebRtcConnecting(),
				const WebRtcFailure(message: 'Exception: STUN/ICE negotiation failed'),
			];
			expectLater(bloc.stream, emitsInOrder(expected));
			bloc.add(const ConnectWebRtcEvent());
		});
		test('ConnectWebRtcEvent emits [WebRtcConnecting, WebRtcFailure] when state fails', () async {
			fakeDatasource.connectSuccess = false;
			final expected = [
				const WebRtcConnecting(),
				const WebRtcFailure(message: 'WebRTC PeerConnection failed'),
			];
			expectLater(bloc.stream, emitsInOrder(expected));
			bloc.add(const ConnectWebRtcEvent());
		});
		test('TogglePushToTalkEvent toggles isPttActive and microphone when connected', () async {
			bloc.add(const ConnectWebRtcEvent());
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(bloc.state, isA<WebRtcConnected>());
			bloc.add(const TogglePushToTalkEvent(isTalking: true));
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(bloc.state, equals(WebRtcConnected(
				renderer: fakeDatasource.fakeRenderer,
				isPttActive: true,
			)));
			expect(fakeDatasource.micEnabled, isTrue);
			bloc.add(const TogglePushToTalkEvent(isTalking: false));
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(bloc.state, equals(WebRtcConnected(
				renderer: fakeDatasource.fakeRenderer,
				isPttActive: false,
			)));
			expect(fakeDatasource.micEnabled, isFalse);
		});
		test('TogglePushToTalkEvent is ignored when not connected', () async {
			bloc.add(const TogglePushToTalkEvent(isTalking: true));
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(bloc.state, equals(const WebRtcInitial()));
			expect(fakeDatasource.micEnabled, isFalse);
		});
		test('DisconnectWebRtcEvent emits WebRtcDisconnected and invokes disconnect', () async {
			bloc.add(const ConnectWebRtcEvent());
			await Future<void>.delayed(const Duration(milliseconds: 50));
			bloc.add(const DisconnectWebRtcEvent());
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(bloc.state, equals(const WebRtcDisconnected()));
			expect(fakeDatasource.disconnectCallCount, equals(1));
		});
		test('Remote disconnection emits WebRtcDisconnected', () async {
			bloc.add(const ConnectWebRtcEvent());
			await Future<void>.delayed(const Duration(milliseconds: 50));
			fakeDatasource.emitConnectionState(RTCPeerConnectionState.RTCPeerConnectionStateDisconnected);
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(bloc.state, equals(const WebRtcDisconnected()));
		});
		test('Remote closed state emits WebRtcDisconnected', () async {
			bloc.add(const ConnectWebRtcEvent());
			await Future<void>.delayed(const Duration(milliseconds: 50));
			fakeDatasource.emitConnectionState(RTCPeerConnectionState.RTCPeerConnectionStateClosed);
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(bloc.state, equals(const WebRtcDisconnected()));
		});
		test('Remote failed state emits WebRtcFailure', () async {
			bloc.add(const ConnectWebRtcEvent());
			await Future<void>.delayed(const Duration(milliseconds: 50));
			fakeDatasource.emitConnectionState(RTCPeerConnectionState.RTCPeerConnectionStateFailed);
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(bloc.state, equals(const WebRtcFailure(message: 'WebRTC PeerConnection failed')));
		});
		test('Remote connecting state emits WebRtcConnecting', () async {
			bloc.add(const ConnectWebRtcEvent());
			await Future<void>.delayed(const Duration(milliseconds: 50));
			fakeDatasource.emitConnectionState(RTCPeerConnectionState.RTCPeerConnectionStateConnecting);
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(bloc.state, equals(const WebRtcConnecting()));
		});
		test('Connection state stream error emits WebRtcFailure', () async {
			bloc.add(const ConnectWebRtcEvent());
			await Future<void>.delayed(const Duration(milliseconds: 50));
			fakeDatasource.emitError('Stream error on peer connection');
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(bloc.state, equals(const WebRtcFailure(message: 'Stream error on peer connection')));
		});
		test('PTT auto-cutoff triggers after continuous hold exceeds cutoff duration', () async {
			final shortCutoffBloc = WebRtcBloc(
				webrtcDatasource: fakeDatasource,
				pttCutoffDuration: const Duration(milliseconds: 100),
			);
			shortCutoffBloc.add(const ConnectWebRtcEvent());
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(shortCutoffBloc.state, isA<WebRtcConnected>());
			shortCutoffBloc.add(const TogglePushToTalkEvent(isTalking: true));
			await Future<void>.delayed(const Duration(milliseconds: 50));
			expect(shortCutoffBloc.state, equals(WebRtcConnected(renderer: fakeDatasource.fakeRenderer, isPttActive: true)));
			expect(fakeDatasource.micEnabled, isTrue);
			await Future<void>.delayed(const Duration(milliseconds: 150));
			expect(shortCutoffBloc.state, equals(WebRtcConnected(renderer: fakeDatasource.fakeRenderer, isPttActive: false)));
			expect(fakeDatasource.micEnabled, isFalse);
			await shortCutoffBloc.close();
		});
	});
}
