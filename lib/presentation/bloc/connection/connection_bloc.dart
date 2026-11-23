import 'dart:async';
import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import '../../../core/constants/app_constants.dart';
import '../../../data/datasources/mqtt_datasource.dart';

part 'connection_event.dart';
part 'connection_state.dart';

class ConnectionBloc extends Bloc<ConnectionEvent, ConnectionState> {
  final MqttDatasource mqttDatasource;
  StreamSubscription<String>? _statusSubscription;

  ConnectionBloc({required this.mqttDatasource}) : super(ConnectionInitial()) {
    on<ConnectRequested>(_onConnectRequested);
    on<DisconnectRequested>(_onDisconnectRequested);
    on<ConnectionStatusChanged>(_onConnectionStatusChanged);
  }

  Future<void> _onConnectRequested(
    ConnectRequested event,
    Emitter<ConnectionState> emit,
  ) async {
    emit(ConnectionLoading());
    await _statusSubscription?.cancel();
    _statusSubscription = mqttDatasource.connectionStatusStream.listen(
      (status) => add(ConnectionStatusChanged(status: status)),
      onError: (error) => add(ConnectionStatusChanged(status: 'error: $error')),
    );

    try {
      final success = await mqttDatasource.connect(
        broker: event.broker ?? AppConstants.defaultMqttBroker,
        port: event.port ?? AppConstants.defaultMqttPort,
        clientIdentifier: event.clientIdentifier,
      );
      if (!success) {
        emit(const ConnectionFailure(message: 'Không thể kết nối tới MQTT broker'));
      }
    } catch (e) {
      emit(ConnectionFailure(message: e.toString()));
    }
  }

  Future<void> _onDisconnectRequested(
    DisconnectRequested event,
    Emitter<ConnectionState> emit,
  ) async {
    emit(ConnectionLoading());
    await _statusSubscription?.cancel();
    _statusSubscription = null;
    await mqttDatasource.disconnect();
    emit(ConnectionInitial());
  }

  void _onConnectionStatusChanged(
    ConnectionStatusChanged event,
    Emitter<ConnectionState> emit,
  ) {
    final status = event.status.toLowerCase();
    if (status == 'connected') {
      emit(ConnectionSuccess(status: event.status));
    } else if (status == 'disconnected') {
      emit(const ConnectionFailure(message: 'Mất kết nối với MQTT broker'));
    } else if (status == 'connecting' || status == 'reconnecting') {
      emit(ConnectionLoading());
    } else if (status.startsWith('error')) {
      emit(ConnectionFailure(message: event.status));
    } else {
      emit(ConnectionSuccess(status: event.status));
    }
  }

  @override
  Future<void> close() {
    _statusSubscription?.cancel();
    return super.close();
  }
}
