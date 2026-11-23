part of 'connection_bloc.dart';

abstract class ConnectionState extends Equatable {
  const ConnectionState();

  @override
  List<Object?> get props => [];
}

class ConnectionInitial extends ConnectionState {}

class ConnectionLoading extends ConnectionState {}

class ConnectionSuccess extends ConnectionState {
  final String status;

  const ConnectionSuccess({required this.status});

  @override
  List<Object?> get props => [status];
}

class ConnectionFailure extends ConnectionState {
  final String message;

  const ConnectionFailure({required this.message});

  @override
  List<Object?> get props => [message];
}
