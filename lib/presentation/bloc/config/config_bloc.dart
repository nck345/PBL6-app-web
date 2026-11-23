import 'dart:async';
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../domain/entities/device_config_entity.dart';
import '../../../domain/repositories/config_repository.dart';

part 'config_event.dart';
part 'config_state.dart';

class ConfigBloc extends Bloc<ConfigEvent, ConfigState> {
  final ConfigRepository configRepository;
  DeviceConfigEntity? _currentConfig;
  StreamSubscription<DeviceConfigEntity>? _configSubscription;

  ConfigBloc({required this.configRepository}) : super(ConfigInitial()) {
    on<LoadConfig>(_onLoadConfig);
    on<ConfigUpdated>(_onConfigUpdated);
    on<UpdateConfigRequested>(_onUpdateConfigRequested);
    on<SendHardwareCommand>(_onSendHardwareCommand);
    on<_ConfigErrorOccurred>(_onConfigErrorOccurred);
  }

  Future<void> _onLoadConfig(
    LoadConfig event,
    Emitter<ConfigState> emit,
  ) async {
    emit(ConfigLoading());
    await _configSubscription?.cancel();
    _configSubscription = configRepository.configStream.listen(
      (cfg) => add(ConfigUpdated(config: cfg)),
      onError: (err) => add(_ConfigErrorOccurred(err.toString())),
    );

    try {
      final config = await configRepository.getConfig();
      final resolved = config ?? DeviceConfigEntity.defaultConfig();
      _currentConfig = resolved;
      emit(ConfigLoaded(config: resolved));
    } catch (e) {
      emit(ConfigFailure(message: e.toString(), lastConfig: _currentConfig));
    }
  }

  void _onConfigUpdated(
    ConfigUpdated event,
    Emitter<ConfigState> emit,
  ) {
    _currentConfig = event.config;
    emit(ConfigLoaded(config: event.config));
  }

  void _onConfigErrorOccurred(
    _ConfigErrorOccurred event,
    Emitter<ConfigState> emit,
  ) {
    emit(ConfigFailure(message: event.message, lastConfig: _currentConfig));
  }

  Future<void> _onUpdateConfigRequested(
    UpdateConfigRequested event,
    Emitter<ConfigState> emit,
  ) async {
    emit(ConfigLoading());
    try {
      await configRepository.updateConfig(event.config);
      _currentConfig = event.config;
      emit(ConfigSuccess(message: 'Cập nhật cấu hình thành công', config: event.config));
      emit(ConfigLoaded(config: event.config));
    } catch (e) {
      emit(ConfigFailure(message: e.toString(), lastConfig: _currentConfig));
    }
  }

  Future<void> _onSendHardwareCommand(
    SendHardwareCommand event,
    Emitter<ConfigState> emit,
  ) async {
    emit(ConfigLoading());
    try {
      await configRepository.sendCommand(event.command, requestId: event.requestId);
      emit(ConfigSuccess(message: 'Lệnh ${event.command} đã được gửi', config: _currentConfig));
      if (_currentConfig != null) {
        emit(ConfigLoaded(config: _currentConfig!));
      }
    } catch (e) {
      emit(ConfigFailure(message: e.toString(), lastConfig: _currentConfig));
    }
  }

  @override
  Future<void> close() {
    _configSubscription?.cancel();
    return super.close();
  }
}
