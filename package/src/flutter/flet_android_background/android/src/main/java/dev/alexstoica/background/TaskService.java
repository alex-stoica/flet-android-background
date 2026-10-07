package dev.alexstoica.background;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;

public class TaskService extends Service {
    static BackgroundPlugin owner;
    private static final String CHANNEL = "python_background";

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
        } catch (Exception error) {
            failure = error;
            stopSelf();
        }
        owner.onStarted(failure);
        return START_NOT_STICKY;
    }

    @Override public void onTaskRemoved(Intent intent) { stopSelf(); }
    @Override public void onTimeout(int startId) { stopSelf(); }
    @Override public void onTimeout(int startId, int type) { stopSelf(); }

    @Override public void onDestroy() {
        BackgroundPlugin previous = owner;
        owner = null;
        stopForeground(STOP_FOREGROUND_REMOVE);
        if (previous != null) previous.onStopped();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
