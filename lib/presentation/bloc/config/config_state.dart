part of 'config_bloc.dart';

abstract class ConfigState extends Equatable {
  const ConfigState();

  @override
  List<Object?> get props => [];
}

class ConfigInitial extends ConfigState {}

class ConfigLoading extends ConfigState {}

class ConfigLoaded extends ConfigState {
  final DeviceConfigEntity config;

  const ConfigLoaded({required this.config});

  @override
  List<Object?> get props => [config];
}

class ConfigSuccess extends ConfigState {
  final String? message;
  final DeviceConfigEntity? config;

  const ConfigSuccess({this.message, this.config});

  @override
  List<Object?> get props => [message, config];
}

class ConfigFailure extends ConfigState {
  final String message;
  final DeviceConfigEntity? lastConfig;

  const ConfigFailure({
    required this.message,
    this.lastConfig,
  });

  @override
  List<Object?> get props => [message, lastConfig];
}
