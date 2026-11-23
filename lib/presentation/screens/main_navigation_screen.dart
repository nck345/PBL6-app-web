import 'package:flutter/material.dart';
import 'alert_history_screen.dart';
import 'home_dashboard_screen.dart';
import 'live_monitor_screen.dart';
import 'settings_screen.dart';

class MainNavigationScreen extends StatefulWidget {
	const MainNavigationScreen({super.key});

	@override
	State<MainNavigationScreen> createState() => _MainNavigationScreenState();
}

class _MainNavigationScreenState extends State<MainNavigationScreen> {
	int _selectedIndex = 0;

	@override
	Widget build(BuildContext context) {
		final screens = [
			HomeDashboardScreen(
				onNavigateToLive: () => setState(() => _selectedIndex = 1),
			),
			const LiveMonitorScreen(),
			const AlertHistoryScreen(),
			const SettingsScreen(),
		];

		return Scaffold(
			body: IndexedStack(
				index: _selectedIndex,
				children: screens,
			),
			bottomNavigationBar: NavigationBar(
				selectedIndex: _selectedIndex,
				onDestinationSelected: (idx) => setState(() => _selectedIndex = idx),
				destinations: const [
					NavigationDestination(
						icon: Icon(Icons.dashboard_outlined),
						selectedIcon: Icon(Icons.dashboard),
						label: 'Tổng quan',
					),
					NavigationDestination(
						icon: Icon(Icons.videocam_outlined),
						selectedIcon: Icon(Icons.videocam),
						label: 'Camera POV',
					),
					NavigationDestination(
						icon: Icon(Icons.notifications_outlined),
						selectedIcon: Icon(Icons.notifications),
						label: 'Cảnh báo',
					),
					NavigationDestination(
						icon: Icon(Icons.settings_outlined),
						selectedIcon: Icon(Icons.settings),
						label: 'Cài đặt',
					),
				],
			),
		);
	}
}
