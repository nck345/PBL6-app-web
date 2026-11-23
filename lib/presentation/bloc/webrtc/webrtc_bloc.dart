import 'dart:async';
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import '../../../core/constants/app_constants.dart';
import '../../../data/datasources/webrtc_datasource.dart';
part 'webrtc_event.dart';
part 'webrtc_state.dart';
class WebRtcBloc extends Bloc<WebRtcEvent, WebRtcState> {
	final WebrtcDatasource webrtcDatasource;
	final Duration pttCutoffDuration;
	StreamSubscription<RTCPeerConnectionState>? _connectionStateSub;
	Timer? _pttCutoffTimer;
	WebRtcBloc({
		required this.webrtcDatasource,
		this.pttCutoffDuration = const Duration(seconds: 60),
	}) : super(const WebRtcInitial()) {
		on<InitializeWebRtcEvent>(_onInitialize);
		on<ConnectWebRtcEvent>(_onConnect);
		on<DisconnectWebRtcEvent>(_onDisconnect);
		on<TogglePushToTalkEvent>(_onTogglePushToTalk);
		on<_WebRtcConnectionStateChanged>(_onConnectionStateChanged);
		on<_WebRtcErrorOccurred>(_onErrorOccurred);
	}
	Future<void> _onInitialize(InitializeWebRtcEvent event, Emitter<WebRtcState> emit) async {
		try {
			await webrtcDatasource.initialize();
			emit(const WebRtcInitial());
		} catch (e) {
			emit(WebRtcFailure(message: 'Initialization failed: $e'));
		}
	}
	Future<void> _onConnect(ConnectWebRtcEvent event, Emitter<WebRtcState> emit) async {
		emit(const WebRtcConnecting());
		await _connectionStateSub?.cancel();
		_connectionStateSub = webrtcDatasource.connectionStateStream.listen(
			(state) => add(_WebRtcConnectionStateChanged(state)),
			onError: (err) => add(_WebRtcErrorOccurred(err.toString())),
		);
		try {
			await webrtcDatasource.connect(event.deviceId);
		} catch (e) {
			emit(WebRtcFailure(message: e.toString()));
		}
	}
	Future<void> _onDisconnect(DisconnectWebRtcEvent event, Emitter<WebRtcState> emit) async {
		_pttCutoffTimer?.cancel();
		_pttCutoffTimer = null;
		await _connectionStateSub?.cancel();
		_connectionStateSub = null;
		await webrtcDatasource.disconnect();
		emit(const WebRtcDisconnected());
	}
	Future<void> _onTogglePushToTalk(TogglePushToTalkEvent event, Emitter<WebRtcState> emit) async {
		if (state is WebRtcConnected) {
			final current = state as WebRtcConnected;
			_pttCutoffTimer?.cancel();
			if (event.isTalking) {
				_pttCutoffTimer = Timer(pttCutoffDuration, () {
					add(const TogglePushToTalkEvent(isTalking: false));
				});
			} else {
				_pttCutoffTimer = null;
			}
			await webrtcDatasource.setMicrophoneEnabled(event.isTalking);
			emit(current.copyWith(isPttActive: event.isTalking));
		}
	}
	void _onConnectionStateChanged(_WebRtcConnectionStateChanged event, Emitter<WebRtcState> emit) {
		switch (event.connectionState) {
			case RTCPeerConnectionState.RTCPeerConnectionStateConnected:
				emit(WebRtcConnected(renderer: webrtcDatasource.videoRenderer, isPttActive: false));
				break;
			case RTCPeerConnectionState.RTCPeerConnectionStateConnecting:
				emit(const WebRtcConnecting());
				break;
			case RTCPeerConnectionState.RTCPeerConnectionStateFailed:
				_pttCutoffTimer?.cancel();
				_pttCutoffTimer = null;
				emit(const WebRtcFailure(message: 'WebRTC PeerConnection failed'));
				break;
			case RTCPeerConnectionState.RTCPeerConnectionStateDisconnected:
			case RTCPeerConnectionState.RTCPeerConnectionStateClosed:
				_pttCutoffTimer?.cancel();
				_pttCutoffTimer = null;
				emit(const WebRtcDisconnected());
				break;
			case RTCPeerConnectionState.RTCPeerConnectionStateNew:
				break;
		}
	}
	void _onErrorOccurred(_WebRtcErrorOccurred event, Emitter<WebRtcState> emit) {
		_pttCutoffTimer?.cancel();
		_pttCutoffTimer = null;
		emit(WebRtcFailure(message: event.message));
	}
	@override
	Future<void> close() async {
		_pttCutoffTimer?.cancel();
		await _connectionStateSub?.cancel();
		return super.close();
	}
}
