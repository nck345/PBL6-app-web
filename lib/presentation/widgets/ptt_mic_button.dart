import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:permission_handler/permission_handler.dart';
import '../bloc/webrtc/webrtc_bloc.dart';

class PttMicButton extends StatefulWidget {
	final double size;
	const PttMicButton({super.key, this.size = 72});

	@override
	State<PttMicButton> createState() => _PttMicButtonState();
}

class _PttMicButtonState extends State<PttMicButton> with SingleTickerProviderStateMixin {
	late AnimationController _animCtrl;
	bool _isPressed = false;
	bool _isPointerDown = false;

	@override
	void initState() {
		super.initState();
		_animCtrl = AnimationController(
			vsync: this,
			duration: const Duration(milliseconds: 600),
			lowerBound: 1.0,
			upperBound: 1.18,
		);
	}

	@override
	void dispose() {
		_animCtrl.dispose();
		super.dispose();
	}

	Future<void> _handlePressDown() async {
		_isPointerDown = true;
		if (!kIsWeb) {
			final status = await Permission.microphone.status;
			if (!status.isGranted) {
				final req = await Permission.microphone.request();
				if (!req.isGranted) {
					if (mounted) {
						ScaffoldMessenger.of(context).showSnackBar(
							const SnackBar(content: Text('Vui lòng cấp quyền Microphone để đàm thoại')),
						);
					}
					return;
				}
			}
		}
		if (!_isPointerDown || !mounted) return;
		setState(() => _isPressed = true);
		_animCtrl.repeat(reverse: true);
		try {
			context.read<WebRtcBloc>().add(const TogglePushToTalkEvent(isTalking: true));
		} catch (_) {}
	}

	void _handlePressUp() {
		_isPointerDown = false;
		if (!_isPressed || !mounted) return;
		setState(() => _isPressed = false);
		_animCtrl.stop();
		_animCtrl.animateTo(1.0);
		try {
			context.read<WebRtcBloc>().add(const TogglePushToTalkEvent(isTalking: false));
		} catch (_) {}
	}

	@override
	Widget build(BuildContext context) {
		return BlocBuilder<WebRtcBloc, WebRtcState>(
			builder: (context, state) {
				final isConnected = state is WebRtcConnected;
				final isTalking = state is WebRtcConnected && state.isPttActive;
				final effectiveColor = !isConnected
					? Colors.grey[400]
					: (isTalking ? Colors.redAccent : Theme.of(context).colorScheme.primary);

				return GestureDetector(
					onTapDown: isConnected ? (_) => _handlePressDown() : null,
					onTapUp: isConnected ? (_) => _handlePressUp() : null,
					onTapCancel: isConnected ? () => _handlePressUp() : null,
					child: AnimatedBuilder(
						animation: _animCtrl,
						builder: (context, child) {
							return Transform.scale(
								scale: isTalking ? _animCtrl.value : 1.0,
								child: Container(
									width: widget.size,
									height: widget.size,
									decoration: BoxDecoration(
										shape: BoxShape.circle,
										color: effectiveColor,
										boxShadow: [
											BoxShadow(
												color: effectiveColor!.withValues(alpha: isTalking ? 0.6 : 0.3),
												blurRadius: isTalking ? 18 : 8,
												spreadRadius: isTalking ? 4 : 1,
											),
										],
									),
									child: Column(
										mainAxisAlignment: MainAxisAlignment.center,
										children: [
											Icon(
												isTalking ? Icons.mic : Icons.mic_none,
												color: Colors.white,
												size: widget.size * 0.42,
											),
											const SizedBox(height: 2),
											Text(
												isTalking ? 'ĐANG NÓI' : 'GIỮ ĐỂ NÓI',
												style: TextStyle(
													color: Colors.white,
													fontSize: widget.size * 0.12,
													fontWeight: FontWeight.bold,
												),
											),
										],
									),
								),
							);
						},
					),
				);
			},
		);
	}
}
