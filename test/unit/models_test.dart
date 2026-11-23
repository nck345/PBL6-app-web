import 'package:flutter_test/flutter_test.dart';
import 'package:pbl6_app/data/models/alert_model.dart';
import 'package:pbl6_app/data/models/device_config_model.dart';
import 'package:pbl6_app/data/models/telemetry_model.dart';
import 'package:pbl6_app/domain/entities/alert_entity.dart';
import 'package:pbl6_app/domain/entities/device_config_entity.dart';
import 'package:pbl6_app/domain/entities/telemetry_entity.dart';

void main() {
  group('TelemetryModel Unit Tests', () {
    const rawJson = <String, dynamic>{
      'device_id': 'pi4_01',
      'timestamp': 1732312000,
      'battery_percentage': 85,
      'temperature_celsius': 48.5,
      'cpu_usage': 32.0,
      'ultrasonic_distance_cm': 145.2,
      'camera_active': true,
      'speaker_volume': 80,
    };

    test('fromJson parses standard valid JSON matching MQTT schema', () {
      final model = TelemetryModel.fromJson(rawJson);
      expect(model.deviceId, 'pi4_01');
      expect(model.timestamp, 1732312000);
      expect(model.batteryPercentage, 85);
      expect(model.temperatureCelsius, 48.5);
      expect(model.cpuUsage, 32.0);
      expect(model.ultrasonicDistanceCm, 145.2);
      expect(model.cameraActive, isTrue);
      expect(model.speakerVolume, 80);
    });

    test('toJson produces correct map keys matching MQTT contract', () {
      final model = TelemetryModel.fromJson(rawJson);
      final jsonOutput = model.toJson();
      expect(jsonOutput['device_id'], 'pi4_01');
      expect(jsonOutput['battery_percentage'], 85);
      expect(jsonOutput['ultrasonic_distance_cm'], 145.2);
      expect(jsonOutput['speaker_volume'], 80);
    });

    test('JSON roundtrip preserves equality', () {
      final model = TelemetryModel.fromJson(rawJson);
      final recreated = TelemetryModel.fromJson(model.toJson());
      expect(recreated, equals(model));
    });

    test('toEntity maps all fields correctly to TelemetryEntity', () {
      final model = TelemetryModel.fromJson(rawJson);
      final entity = model.toEntity();
      expect(entity, isA<TelemetryEntity>());
      expect(entity.deviceId, model.deviceId);
      expect(entity.ultrasonicDistanceCm, model.ultrasonicDistanceCm);
      expect(entity.batteryPercentage, model.batteryPercentage);
    });

    test('Coerces integer values to double for floating point fields', () {
      final intJson = <String, dynamic>{
        'device_id': 'pi4_01',
        'timestamp': 1732312000,
        'battery_percentage': 100,
        'temperature_celsius': 50,
        'cpu_usage': 40,
        'ultrasonic_distance_cm': 200,
        'camera_active': false,
        'speaker_volume': 90,
      };
      final model = TelemetryModel.fromJson(intJson);
      expect(model.temperatureCelsius, 50.0);
      expect(model.cpuUsage, 40.0);
      expect(model.ultrasonicDistanceCm, 200.0);
    });

    test('Handles out-of-range distance value -1.0 correctly', () {
      final outOfRangeJson = Map<String, dynamic>.from(rawJson)
        ..['ultrasonic_distance_cm'] = -1.0;
      final model = TelemetryModel.fromJson(outOfRangeJson);
      expect(model.ultrasonicDistanceCm, -1.0);
    });

    test('Helper getters correctly identify status', () {
      const nearModel = TelemetryModel(
        deviceId: 'pi4_01',
        timestamp: 1732312000,
        batteryPercentage: 15,
        temperatureCelsius: 75.0,
        cpuUsage: 80.0,
        ultrasonicDistanceCm: 30.0,
        cameraActive: true,
        speakerVolume: 80,
      );
      expect(nearModel.isObstacleNear, isTrue);
      expect(nearModel.isBatteryLow, isTrue);
      expect(nearModel.isOverheating, isTrue);
    });
  });

  group('AlertModel Unit Tests', () {
    const rawAlertJson = <String, dynamic>{
      'event_id': 'evt_9981',
      'timestamp': 1732312015,
      'alert_type': 'OBSTACLE_DANGER',
      'level': 'CRITICAL',
      'distance_cm': 25.0,
      'detected_objects': ['stairs_down', 'puddle'],
      'message': 'Phát hiện bậc tam cấp đi xuống ở cự ly gần!',
    };

    test('fromJson parses standard alert JSON correctly', () {
      final model = AlertModel.fromJson(rawAlertJson);
      expect(model.eventId, 'evt_9981');
      expect(model.timestamp, 1732312015);
      expect(model.alertType, 'OBSTACLE_DANGER');
      expect(model.level, 'CRITICAL');
      expect(model.distanceCm, 25.0);
      expect(model.detectedObjects, ['stairs_down', 'puddle']);
      expect(model.message, 'Phát hiện bậc tam cấp đi xuống ở cự ly gần!');
      expect(model.isAcknowledged, isFalse);
      expect(model.isCritical, isTrue);
      expect(model.isWarning, isFalse);
    });

    test('toJson produces correct schema', () {
      final model = AlertModel.fromJson(rawAlertJson);
      final jsonOutput = model.toJson();
      expect(jsonOutput['event_id'], 'evt_9981');
      expect(jsonOutput['level'], 'CRITICAL');
      expect(jsonOutput['detected_objects'], ['stairs_down', 'puddle']);
    });

    test('JSON roundtrip preserves equality', () {
      final model = AlertModel.fromJson(rawAlertJson);
      final recreated = AlertModel.fromJson(model.toJson());
      expect(recreated, equals(model));
    });

    test('toEntity converts properly and preserves acknowledge state', () {
      final model = AlertModel.fromJson(rawAlertJson);
      final entity = model.toEntity();
      expect(entity, isA<AlertEntity>());
      expect(entity.eventId, 'evt_9981');
      expect(entity.isAcknowledged, isFalse);

      final acknowledged = entity.copyWith(isAcknowledged: true);
      expect(acknowledged.isAcknowledged, isTrue);
      expect(acknowledged.eventId, entity.eventId);
    });

    test('Handles null or missing detected_objects gracefully as empty list', () {
      final noObjectsJson = <String, dynamic>{
        'event_id': 'evt_0001',
        'timestamp': 1732312020,
        'alert_type': 'LOW_BATTERY',
        'level': 'WARNING',
        'distance_cm': -1.0,
        'message': 'Pin yếu dưới 15%',
      };
      final model = AlertModel.fromJson(noObjectsJson);
      expect(model.detectedObjects, isEmpty);
      expect(model.isWarning, isTrue);
    });
  });

  group('DeviceConfigModel Unit Tests', () {
    const rawConfigJson = <String, dynamic>{
      'distance_threshold_cm': 80,
      'speaker_volume': 90,
      'alert_frequency_ms': 500,
      'detection_fps': 15,
    };

    test('fromJson parses config parameters correctly', () {
      final model = DeviceConfigModel.fromJson(rawConfigJson);
      expect(model.distanceThresholdCm, 80);
      expect(model.speakerVolume, 90);
      expect(model.alertFrequencyMs, 500);
      expect(model.detectionFps, 15);
    });

    test('toJson outputs exact contract keys', () {
      final model = DeviceConfigModel.fromJson(rawConfigJson);
      final jsonOutput = model.toJson();
      expect(jsonOutput['distance_threshold_cm'], 80);
      expect(jsonOutput['speaker_volume'], 90);
      expect(jsonOutput['alert_frequency_ms'], 500);
      expect(jsonOutput['detection_fps'], 15);
    });

    test('JSON roundtrip preserves equality', () {
      final model = DeviceConfigModel.fromJson(rawConfigJson);
      final recreated = DeviceConfigModel.fromJson(model.toJson());
      expect(recreated, equals(model));
    });

    test('toEntity produces DeviceConfigEntity', () {
      final model = DeviceConfigModel.fromJson(rawConfigJson);
      final entity = model.toEntity();
      expect(entity, isA<DeviceConfigEntity>());
      expect(entity.distanceThresholdCm, 80);
    });

    test('defaultConfig produces valid fallback entity', () {
      final def = DeviceConfigEntity.defaultConfig();
      expect(def.distanceThresholdCm, 80);
      expect(def.speakerVolume, 80);
      expect(def.alertFrequencyMs, 500);
      expect(def.detectionFps, 15);
    });

    test('copyWith modifies only specified fields', () {
      final def = DeviceConfigEntity.defaultConfig();
      final updated = def.copyWith(speakerVolume: 100);
      expect(updated.speakerVolume, 100);
      expect(updated.distanceThresholdCm, def.distanceThresholdCm);
    });
  });
}
