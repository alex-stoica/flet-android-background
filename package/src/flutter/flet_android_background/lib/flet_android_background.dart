import 'package:flet/flet.dart';
import 'package:flutter/services.dart';

class Extension extends FletExtension {
  @override
  FletService? createService(Control control) =>
      control.type == 'flet_android_background'
          ? BackgroundService(control: control)
          : null;
}

class BackgroundService extends FletService {
  BackgroundService({required super.control});
  static const channel = MethodChannel('flet_android_background');
  static BackgroundService? owner;
  static int sequence = 0;
  String? token;

  @override
  void init() {
    super.init();
    control.addInvokeMethodListener(invoke);
    channel.setMethodCallHandler((call) async {
      final active = owner;
      if (call.method == 'stopped' && active?.token == call.arguments) {
        owner = null;
        active?.token = null;
        active?.control.triggerEvent('stopped', call.arguments);
      }
    });
  }

  Future<dynamic> invoke(String method, dynamic arguments) async {
    if (method == 'start') {
      if (owner != null) return {'error': 'A background task already owns this service'};
      owner = this;
      token = '${DateTime.now().microsecondsSinceEpoch}-${sequence++}';
    } else if (method == 'stop' && owner != this) {
      return null;
    }
    try {
      final requested = token;
      final result = await channel.invokeMethod(method, {...?arguments, 'owner': token});
      return method == 'start' ? requested : result;
    } on PlatformException catch (error) {
      if (method == 'start' && owner == this) {
        owner = null;
        token = null;
      }
      return {'error': error.message ?? error.code};
    }
  }

  @override
  void dispose() {
    control.removeInvokeMethodListener(invoke);
    if (owner == this) {
      invoke('stop', <String, dynamic>{});
    }
    super.dispose();
  }
}
