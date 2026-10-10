package dev.alexstoica.background;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.net.wifi.WifiManager;
import android.os.IBinder;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;

public class TaskService extends Service {
    static BackgroundPlugin owner;
    private static final String CHANNEL = "python_background";
    private WifiManager.WifiLock wifiLock;
    private PowerManager.WakeLock cpuLock;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final Runnable expireCpuLock = this::stopSelf;

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (owner == null || intent == null || "stop".equals(intent.getAction())) {
            stopSelf();
            return START_NOT_STICKY;
        }
        Exception failure = null;
        try {
            Notification.Builder builder;
            if (Build.VERSION.SDK_INT >= 26) {
                getSystemService(NotificationManager.class).createNotificationChannel(
                    new NotificationChannel(CHANNEL, "Background tasks", NotificationManager.IMPORTANCE_LOW));
                builder = new Notification.Builder(this, CHANNEL);
            } else {
                builder = new Notification.Builder(this);
            }
            PendingIntent stop = PendingIntent.getService(this, 0,
                new Intent(this, TaskService.class).setAction("stop"), PendingIntent.FLAG_IMMUTABLE);
            Intent launch = getPackageManager().getLaunchIntentForPackage(getPackageName());
            builder.setContentTitle(intent.getStringExtra("title"))
                .setContentText(intent.getStringExtra("body"))
                .setSmallIcon(getApplicationInfo().icon).setOngoing(true)
                .addAction(new Notification.Action.Builder(null, "Stop", stop).build());
            if (launch != null) builder.setContentIntent(PendingIntent.getActivity(
                this, 0, launch, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT));
            startForeground(intent.getIntExtra("id", 1), builder.build());
            if (intent.getBooleanExtra("enable_cpu_lock", false) && cpuLock == null) {
                long seconds = intent.getLongExtra("cpu_lock_timeout", 3600L);
                if (seconds < 1 || seconds > 21600) {
                    throw new IllegalArgumentException("CPU lock timeout must be 1–21600 seconds");
                }
                PowerManager power = getSystemService(PowerManager.class);
                if (power == null) throw new IllegalStateException("Power service unavailable");
                cpuLock = power.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,
                    "flet_android_background:cpu");
                cpuLock.setReferenceCounted(false);
                cpuLock.acquire(seconds * 1000L);
                handler.postDelayed(expireCpuLock, seconds * 1000L);
            }
            if (intent.getBooleanExtra("enable_wifi_lock", false) && wifiLock == null) {
                WifiManager wifi = getApplicationContext().getSystemService(WifiManager.class);
                if (wifi == null) throw new IllegalStateException("Wi-Fi service unavailable");
                wifiLock = wifi.createWifiLock(
                    WifiManager.WIFI_MODE_FULL_HIGH_PERF, "flet_android_background:wifi");
                wifiLock.setReferenceCounted(false);
                wifiLock.acquire();
            }
        } catch (Exception error) {
            failure = error;
            releaseLocks();
            stopSelf();
        }
        owner.onStarted(failure);
        return START_NOT_STICKY;
    }

    private void releaseLocks() {
        handler.removeCallbacks(expireCpuLock);
        if (cpuLock != null) {
            if (cpuLock.isHeld()) cpuLock.release();
            cpuLock = null;
        }
        if (wifiLock != null) {
            if (wifiLock.isHeld()) wifiLock.release();
            wifiLock = null;
        }
    }

    @Override public void onTaskRemoved(Intent intent) { stopSelf(); }
    @Override public void onTimeout(int startId) { stopSelf(); }
    @Override public void onTimeout(int startId, int type) { stopSelf(); }

    @Override public void onDestroy() {
        BackgroundPlugin previous = owner;
        owner = null;
        releaseLocks();
        stopForeground(STOP_FOREGROUND_REMOVE);
        if (previous != null) previous.onStopped();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
