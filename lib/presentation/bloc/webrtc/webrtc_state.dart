part of 'webrtc_bloc.dart';
abstract class WebRtcState extends Equatable {
	const WebRtcState();
	@override
	List<Object?> get props => [];
}
class WebRtcInitial extends WebRtcState {
	const WebRtcInitial();
}
class WebRtcConnecting extends WebRtcState {
	const WebRtcConnecting();
}
class WebRtcConnected extends WebRtcState {
	final RTCVideoRenderer renderer;
	final bool isPttActive;
	const WebRtcConnected({required this.renderer, this.isPttActive = false});
	WebRtcConnected copyWith({RTCVideoRenderer? renderer, bool? isPttActive}) {
		return WebRtcConnected(
			renderer: renderer ?? this.renderer,
			isPttActive: isPttActive ?? this.isPttActive,
		);
	}
	@override
	List<Object?> get props => [renderer, isPttActive];
}
class WebRtcDisconnected extends WebRtcState {
	const WebRtcDisconnected();
}
class WebRtcFailure extends WebRtcState {
	final String message;
	const WebRtcFailure({required this.message});
	@override
	List<Object?> get props => [message];
}
