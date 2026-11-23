part of 'webrtc_bloc.dart';
abstract class WebRtcEvent extends Equatable {
	const WebRtcEvent();
	@override
	List<Object?> get props => [];
}
class InitializeWebRtcEvent extends WebRtcEvent {
	const InitializeWebRtcEvent();
}
class ConnectWebRtcEvent extends WebRtcEvent {
	final String deviceId;
	const ConnectWebRtcEvent({this.deviceId = AppConstants.defaultDeviceId});
	@override
	List<Object?> get props => [deviceId];
}
class DisconnectWebRtcEvent extends WebRtcEvent {
	const DisconnectWebRtcEvent();
}
class TogglePushToTalkEvent extends WebRtcEvent {
	final bool isTalking;
	const TogglePushToTalkEvent({required this.isTalking});
	@override
	List<Object?> get props => [isTalking];
}
class _WebRtcConnectionStateChanged extends WebRtcEvent {
	final RTCPeerConnectionState connectionState;
	const _WebRtcConnectionStateChanged(this.connectionState);
	@override
	List<Object?> get props => [connectionState];
}
class _WebRtcErrorOccurred extends WebRtcEvent {
	final String message;
	const _WebRtcErrorOccurred(this.message);
	@override
	List<Object?> get props => [message];
}
