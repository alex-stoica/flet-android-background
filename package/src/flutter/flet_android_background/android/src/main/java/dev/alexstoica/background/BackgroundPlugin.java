package dev.alexstoica.background;

import android.Manifest;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import io.flutter.embedding.engine.plugins.FlutterPlugin;
import io.flutter.embedding.engine.plugins.activity.ActivityAware;
import io.flutter.embedding.engine.plugins.activity.ActivityPluginBinding;
import io.flutter.plugin.common.MethodCall;
import io.flutter.plugin.common.MethodChannel;
import io.flutter.plugin.common.PluginRegistry.RequestPermissionsResultListener;
import java.util.ArrayList;

public class BackgroundPlugin implements FlutterPlugin, ActivityAware,
        MethodChannel.MethodCallHandler, RequestPermissionsResultListener {
    private Context context;
    private MethodChannel channel;
    private ActivityPluginBinding binding;
    private MethodChannel.Result permission;
    private MethodChannel.Result starting;
    private final ArrayList<MethodChannel.Result> stopping = new ArrayList<>();
    private String token;
    private static final int REQUEST = 7141;

    @Override public void onAttachedToEngine(FlutterPluginBinding engine) {
        context = engine.getApplicationContext();
        channel = new MethodChannel(engine.getBinaryMessenger(), "flet_android_background");
        channel.setMethodCallHandler(this);
    }

    @Override public void onMethodCall(MethodCall call, MethodChannel.Result result) {
        try {
            switch (call.method) {
                case "permission":
                    if (Build.VERSION.SDK_INT < 33 || context.checkSelfPermission(
                            Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED) {
                        result.success(true);
                    } else if (binding == null || permission != null) {
                        result.error("permission", "No activity or permission request already pending", null);
                    } else {
                        permission = result;
                        binding.getActivity().requestPermissions(
                            new String[]{Manifest.permission.POST_NOTIFICATIONS}, REQUEST);
                    }
                    break;
                case "start":
                    if (TaskService.owner != null) {
                        result.error("running", "A background task already owns this service", null);
                        break;
                    }
                    Intent intent = new Intent(context, TaskService.class)
                        .putExtra("id", ((Number) call.argument("id")).intValue())
                        .putExtra("title", (String) call.argument("title"))
                        .putExtra("body", (String) call.argument("body"));
                    token = call.argument("owner");
                    if (token == null) throw new IllegalArgumentException("Missing service owner");
                    TaskService.owner = this;
                    starting = result;
                    try {
                        if (Build.VERSION.SDK_INT >= 26) context.startForegroundService(intent);
                        else context.startService(intent);
                    } catch (Exception error) {
                        TaskService.owner = null;
                        onStarted(error);
                    }
                    break;
                case "stop":
                    if (TaskService.owner != this || !token.equals(call.argument("owner"))) {
                        result.success(null);
                    } else {
                        stopping.add(result);
                        context.stopService(new Intent(context, TaskService.class));
                    }
                    break;
                default:
                    result.notImplemented();
            }
        } catch (Exception error) {
            result.error("native", error.toString(), null);
        }
    }

    void onStarted(Exception error) {
        if (starting == null) return;
        MethodChannel.Result result = starting;
        starting = null;
        if (error == null) result.success(null);
        else result.error("start", error.toString(), null);
    }

    void onStopped() {
        onStarted(new IllegalStateException("Service stopped during startup"));
        if (channel != null) channel.invokeMethod("stopped", token);
        token = null;
        for (MethodChannel.Result result : stopping) result.success(null);
        stopping.clear();
    }

    @Override public boolean onRequestPermissionsResult(int code, String[] names, int[] grants) {
        if (code != REQUEST || permission == null) return false;
        permission.success(grants.length > 0 && grants[0] == PackageManager.PERMISSION_GRANTED);
        permission = null;
        return true;
    }

    @Override public void onAttachedToActivity(ActivityPluginBinding activity) {
        binding = activity;
        binding.addRequestPermissionsResultListener(this);
    }
    @Override public void onDetachedFromActivity() {
        if (binding != null) binding.removeRequestPermissionsResultListener(this);
        binding = null;
        if (permission != null) {
            permission.error("activity", "Activity detached during permission request", null);
            permission = null;
        }
    }
    @Override public void onDetachedFromActivityForConfigChanges() { onDetachedFromActivity(); }
    @Override public void onReattachedToActivityForConfigChanges(ActivityPluginBinding activity) {
        onAttachedToActivity(activity);
    }
    @Override public void onDetachedFromEngine(FlutterPluginBinding engine) {
        onDetachedFromActivity();
        channel.setMethodCallHandler(null);
        channel = null;
        if (TaskService.owner == this) {
            onStopped();
            context.stopService(new Intent(context, TaskService.class));
        }
    }
}
