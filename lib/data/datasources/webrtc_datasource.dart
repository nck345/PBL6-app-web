import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_webrtc/flutter_webrtc.dart';
import 'package:permission_handler/permission_handler.dart';
import '../../core/constants/app_constants.dart';
import 'mqtt_datasource.dart';
class WebrtcDatasource {
	final MqttDatasource mqttDatasource;
	final RTCVideoRenderer _videoRenderer = RTCVideoRenderer();
	RTCPeerConnection? _peerConnection;
	MediaStream? _localStream;
	MediaStream? _remoteStream;
	StreamSubscription<Map<String, dynamic>>? _answerSubscription;
	StreamSubscription<Map<String, dynamic>>? _iceSubscription;
	final List<RTCIceCandidate> _pendingIceCandidates = [];
	final StreamController<RTCPeerConnectionState> _connectionStateController = StreamController<RTCPeerConnectionState>.broadcast();
	bool _isMicrophoneEnabled = false;
	WebrtcDatasource({required this.mqttDatasource});
	RTCVideoRenderer get videoRenderer => _videoRenderer;
	Stream<RTCPeerConnectionState> get connectionStateStream => _connectionStateController.stream;
	bool get isMicrophoneEnabled => _isMicrophoneEnabled;
	RTCPeerConnection? get peerConnection => _peerConnection;
	Future<void> initialize() async {
		await _videoRenderer.initialize();
	}
	Future<void> connect(String deviceId) async {
		if (!mqttDatasource.isConnected) throw StateError('MQTT datasource is not connected');
		await disconnect();
		_connectionStateController.add(RTCPeerConnectionState.RTCPeerConnectionStateConnecting);
		mqttDatasource.subscribeWebRtc(deviceId);
		final config = {
			'iceServers': [
				{'urls': AppConstants.defaultStunServer}
			],
			'sdpSemantics': 'unified-plan',
		};
		final constraints = {
			'mandatory': {},
			'optional': [
				{'DtlsSrtpKeyAgreement': true},
			],
		};
		_peerConnection = await createPeerConnection(config, constraints);
		_pendingIceCandidates.clear();
		try {
			final micGranted = kIsWeb || (await Permission.microphone.request()).isGranted;
			if (micGranted) {
				_localStream = await navigator.mediaDevices.getUserMedia({
					'audio': true,
					'video': false,
				});
				for (final track in _localStream!.getAudioTracks()) {
					track.enabled = false;
					await _peerConnection!.addTrack(track, _localStream!);
				}
			}
		} catch (_) {}
		_peerConnection!.onTrack = (RTCTrackEvent event) {
			if (event.track.kind == 'video' && event.streams.isNotEmpty) {
				_remoteStream = event.streams[0];
				_videoRenderer.srcObject = _remoteStream;
			}
		};
		_peerConnection!.onAddStream = (MediaStream stream) {
			if (stream.getVideoTracks().isNotEmpty) {
				_remoteStream = stream;
				_videoRenderer.srcObject = _remoteStream;
			}
		};
		_peerConnection!.onConnectionState = (RTCPeerConnectionState state) {
			_connectionStateController.add(state);
		};
		_peerConnection!.onIceCandidate = (RTCIceCandidate candidate) {
			if (candidate.candidate != null && candidate.candidate!.isNotEmpty) {
				mqttDatasource.publishWebRtcIce(deviceId, {
					'candidate': candidate.candidate,
					'sdpMid': candidate.sdpMid,
					'sdpMLineIndex': candidate.sdpMLineIndex,
					'sender': 'app',
				});
			}
		};
		_answerSubscription = mqttDatasource.webrtcAnswerStream.listen((data) async {
			final sdp = data['sdp'] as String?;
			final type = data['type'] as String? ?? 'answer';
			if (sdp != null && sdp.isNotEmpty && _peerConnection != null) {
				await _peerConnection!.setRemoteDescription(RTCSessionDescription(sdp, type));
				for (final cand in _pendingIceCandidates) {
					await _peerConnection!.addCandidate(cand);
				}
				_pendingIceCandidates.clear();
			}
		});
		_iceSubscription = mqttDatasource.webrtcIceStream.listen((data) async {
			final sender = data['sender'] as String?;
			if (sender == 'app' || sender == 'app_client') return;
			final candidateStr = data['candidate'] as String?;
			final sdpMid = data['sdpMid'] as String?;
			final sdpMLineIndex = data['sdpMLineIndex'] as int?;
			if (candidateStr != null && _peerConnection != null) {
				final candidate = RTCIceCandidate(candidateStr, sdpMid, sdpMLineIndex);
				final remoteDesc = await _peerConnection!.getRemoteDescription();
				if (remoteDesc != null) {
					await _peerConnection!.addCandidate(candidate);
				} else {
					_pendingIceCandidates.add(candidate);
				}
			}
		});
		final offer = await _peerConnection!.createOffer({
			'offerToReceiveVideo': 1,
			'offerToReceiveAudio': 0,
		});
		await _peerConnection!.setLocalDescription(offer);
		await mqttDatasource.publishWebRtcOffer(deviceId, {
			'sdp': offer.sdp,
			'type': 'offer',
			'caller': 'app_client',
		});
	}
	Future<void> setMicrophoneEnabled(bool enabled) async {
		_isMicrophoneEnabled = enabled;
		if (_localStream != null) {
			for (final track in _localStream!.getAudioTracks()) {
				track.enabled = enabled;
			}
		}
	}
	Future<void> disconnect() async {
		await _answerSubscription?.cancel();
		_answerSubscription = null;
		await _iceSubscription?.cancel();
		_iceSubscription = null;
		_pendingIceCandidates.clear();
		if (_localStream != null) {
			for (final track in _localStream!.getTracks()) {
				track.stop();
			}
			await _localStream!.dispose();
			_localStream = null;
		}
		_videoRenderer.srcObject = null;
		_remoteStream = null;
		if (_peerConnection != null) {
			await _peerConnection!.close();
			_peerConnection = null;
		}
		_isMicrophoneEnabled = false;
		_connectionStateController.add(RTCPeerConnectionState.RTCPeerConnectionStateClosed);
	}
	Future<void> dispose() async {
		await disconnect();
		await _videoRenderer.dispose();
		await _connectionStateController.close();
	}
}
