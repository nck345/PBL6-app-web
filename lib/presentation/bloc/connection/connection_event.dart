part of 'connection_bloc.dart';

abstract class ConnectionEvent extends Equatable {
  const ConnectionEvent();

  @override
  List<Object?> get props => [];
}

class ConnectRequested extends ConnectionEvent {
  final String? broker;
  final int? port;
  final String? clientIdentifier;

  const ConnectRequested({
    this.broker,
    this.port,
    this.clientIdentifier,
  });

  @override
  List<Object?> get props => [broker, port, clientIdentifier];
}

class DisconnectRequested extends ConnectionEvent {
  const DisconnectRequested();
}

class ConnectionStatusChanged extends ConnectionEvent {
  final String status;

  const ConnectionStatusChanged({required this.status});

  @override
  List<Object?> get props => [status];
}
