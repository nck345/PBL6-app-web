import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'core/constants/app_constants.dart';
import 'core/services/notification_service.dart';
import 'data/datasources/mqtt_datasource.dart';
import 'data/datasources/webrtc_datasource.dart';
import 'data/repositories/alert_repository_impl.dart';
import 'data/repositories/config_repository_impl.dart';
import 'data/repositories/telemetry_repository_impl.dart';
import 'domain/repositories/alert_repository.dart';
import 'domain/repositories/config_repository.dart';
import 'domain/repositories/telemetry_repository.dart';
import 'presentation/bloc/alerts/alert_bloc.dart';
import 'presentation/bloc/config/config_bloc.dart';
import 'presentation/bloc/connection/connection_bloc.dart';
import 'presentation/bloc/dashboard/dashboard_bloc.dart';
import 'presentation/bloc/webrtc/webrtc_bloc.dart';
import 'presentation/screens/main_navigation_screen.dart';

void main() async {
	WidgetsFlutterBinding.ensureInitialized();
	final notificationService = NotificationService();
	await notificationService.initialize();

	final mqttDatasource = MqttDatasource();
	final webrtcDatasource = WebrtcDatasource(mqttDatasource: mqttDatasource);

	final telemetryRepository = TelemetryRepositoryImpl(mqttDataSource: mqttDatasource);
	final alertRepository = AlertRepositoryImpl(mqttDataSource: mqttDatasource);
	final configRepository = ConfigRepositoryImpl(mqttDataSource: mqttDatasource);

	runApp(
		AppProviders(
			mqttDatasource: mqttDatasource,
			webrtcDatasource: webrtcDatasource,
			telemetryRepository: telemetryRepository,
			alertRepository: alertRepository,
			configRepository: configRepository,
			notificationService: notificationService,
		),
	);
}

class AppProviders extends StatelessWidget {
	final MqttDatasource mqttDatasource;
	final WebrtcDatasource webrtcDatasource;
	final TelemetryRepository telemetryRepository;
	final AlertRepository alertRepository;
	final ConfigRepository configRepository;
	final NotificationService notificationService;

	const AppProviders({
		super.key,
		required this.mqttDatasource,
		required this.webrtcDatasource,
		required this.telemetryRepository,
		required this.alertRepository,
		required this.configRepository,
		required this.notificationService,
	});

	@override
	Widget build(BuildContext context) {
		return MultiRepositoryProvider(
			providers: [
				RepositoryProvider<MqttDatasource>.value(value: mqttDatasource),
				RepositoryProvider<WebrtcDatasource>.value(value: webrtcDatasource),
				RepositoryProvider<TelemetryRepository>.value(value: telemetryRepository),
				RepositoryProvider<AlertRepository>.value(value: alertRepository),
				RepositoryProvider<ConfigRepository>.value(value: configRepository),
			],
			child: MultiBlocProvider(
				providers: [
					BlocProvider<ConnectionBloc>(
						create: (_) => ConnectionBloc(mqttDatasource: mqttDatasource)
							..add(const ConnectRequested()),
					),
					BlocProvider<DashboardBloc>(
						create: (_) => DashboardBloc(telemetryRepository: telemetryRepository)
							..add(const StartTelemetrySubscription()),
					),
					BlocProvider<AlertBloc>(
						create: (_) => AlertBloc(
							alertRepository: alertRepository,
							notificationService: notificationService,
						)..add(const StartAlertSubscription()),
					),
					BlocProvider<ConfigBloc>(
						create: (_) => ConfigBloc(configRepository: configRepository)
							..add(const LoadConfig()),
					),
					BlocProvider<WebRtcBloc>(
						create: (_) => WebRtcBloc(webrtcDatasource: webrtcDatasource)
							..add(const InitializeWebRtcEvent()),
					),
				],
				child: const AssistiveMonitorApp(),
			),
		);
	}
}

class AssistiveMonitorApp extends StatelessWidget {
	const AssistiveMonitorApp({super.key});

	@override
	Widget build(BuildContext context) {
		return MaterialApp(
			title: AppConstants.appTitle,
			debugShowCheckedModeBanner: false,
			theme: ThemeData(
				useMaterial3: true,
				colorScheme: ColorScheme.fromSeed(
					seedColor: Colors.blueAccent,
					brightness: Brightness.light,
				),
				cardTheme: const CardThemeData(
					elevation: 1,
					margin: EdgeInsets.zero,
				),
			),
			darkTheme: ThemeData(
				useMaterial3: true,
				colorScheme: ColorScheme.fromSeed(
					seedColor: Colors.blueAccent,
					brightness: Brightness.dark,
				),
			),
			themeMode: ThemeMode.system,
			home: const MainNavigationScreen(),
		);
	}
}
