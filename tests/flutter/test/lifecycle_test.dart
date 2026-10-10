import 'dart:async';
import 'package:flet/flet.dart';
import 'package:flet_android_background/flet_android_background.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

class TestControl implements Control {
  final events = <dynamic>[];
  @override
  void addInvokeMethodListener(dynamic callback) {}
  @override
  void removeInvokeMethodListener(dynamic callback) {}
  @override
  void triggerEvent(String name, [dynamic data]) => events.add(data);
  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

void main() {
  final binding = TestWidgetsFlutterBinding.ensureInitialized();
  final messenger = binding.defaultBinaryMessenger;
  const channel = BackgroundService.channel;
  const codec = StandardMethodCodec();
  late List<MethodCall> calls;
  late TestControl firstControl;
  late BackgroundService first;
  late BackgroundService second;

  Future<void> stopped(String token) async {
    final done = Completer<void>();
    messenger.handlePlatformMessage(channel.name,
        codec.encodeMethodCall(MethodCall('stopped', token)), (_) => done.complete());
    await done.future;
  }

  setUp(() {
    BackgroundService.owner = null;
    calls = [];
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call);
      return null;
    });
    firstControl = TestControl();
    first = BackgroundService(control: firstControl)..init();
    second = BackgroundService(control: TestControl())..init();
  });

  tearDown(() {
    BackgroundService.owner = null;
    first.dispose();
    second.dispose();
    messenger.setMockMethodCallHandler(channel, null);
  });

  test('second controller cannot start or stop the owner', () async {
    await first.invoke('start', {});
    expect(await second.invoke('start', {}), contains('error'));
    await second.invoke('stop', {});
    expect(calls.map((c) => c.method), ['start']);
  });

  test('stopped event reaches owner after another controller initializes', () async {
    final token = await first.invoke('start', {}) as String;
    await stopped(token);
    expect(firstControl.events, [token]);
    expect(BackgroundService.owner, isNull);
  });

  test('stale event cannot release a new owner', () async {
    final previous = await first.invoke('start', {}) as String;
    await stopped(previous);
    await second.invoke('start', {});
    await stopped(previous);
    expect(BackgroundService.owner, same(second));
  });

  test('disposing an idle controller preserves owner event routing', () async {
    final token = await first.invoke('start', {}) as String;
    second.dispose();
    await stopped(token);
    expect(firstControl.events, [token]);
  });

  test('WifiLock option crosses the platform channel unchanged', () async {
    for (final enabled in [false, true]) {
      final token = await first.invoke('start', {'enable_wifi_lock': enabled}) as String;
      expect(calls.last.arguments['enable_wifi_lock'], enabled);
      await first.invoke('stop', {});
      await stopped(token);
      expect(BackgroundService.owner, isNull);
    }
  });

  test('native start failure releases ownership', () async {
    messenger.setMockMethodCallHandler(channel, (_) async {
      throw PlatformException(code: 'denied');
    });
    expect(await first.invoke('start', {}), contains('error'));
    expect(BackgroundService.owner, isNull);
  });
}
