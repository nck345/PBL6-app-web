part of 'config_bloc.dart';

abstract class ConfigEvent extends Equatable {
  const ConfigEvent();

  @override
  List<Object?> get props => [];
}

class LoadConfig extends ConfigEvent {
  const LoadConfig();
}

class ConfigUpdated extends ConfigEvent {
  final DeviceConfigEntity config;

  const ConfigUpdated({required this.config});

  @override
  List<Object?> get props => [config];
}

class UpdateConfigRequested extends ConfigEvent {
  final DeviceConfigEntity config;

  const UpdateConfigRequested({required this.config});

  @override
  List<Object?> get props => [config];
}

class SendHardwareCommand extends ConfigEvent {
  final String command;
  final String? requestId;

  const SendHardwareCommand({
    required this.command,
    this.requestId,
  });

  @override
  List<Object?> get props => [command, requestId];
}

class _ConfigErrorOccurred extends ConfigEvent {
  final String message;

  const _ConfigErrorOccurred(this.message);

  @override
  List<Object?> get props => [message];
}
