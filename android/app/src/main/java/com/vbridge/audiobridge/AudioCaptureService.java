package com.vbridge.audiobridge;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioManager;
import android.media.AudioPlaybackCaptureConfiguration;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Binder;
import android.os.Build;
import android.os.IBinder;
import android.os.Process;
import android.util.Log;

import androidx.core.app.NotificationCompat;

import java.util.concurrent.atomic.AtomicBoolean;

public class AudioCaptureService extends Service {
    private static final String TAG = "VBridge.CaptureService";
    private static final String CHANNEL_ID = "vbridge_audio_channel";
    private static final int NOTIFICATION_ID = 101;

    public static final String ACTION_START = "com.vbridge.action.START";
    public static final String ACTION_STOP = "com.vbridge.action.STOP";
    public static final String EXTRA_RESULT_DATA = "extra_result_data";
    public static final String EXTRA_TARGET_IP = "extra_target_ip";
    public static final String EXTRA_TARGET_PORT = "extra_target_port";
    public static final String EXTRA_SESSION_ID = "extra_session_id";
    public static final String EXTRA_USE_MIC = "extra_use_mic";
    public static final String EXTRA_MUTE_SPEAKER = "extra_mute_speaker";

    private final IBinder binder = new LocalBinder();

    public class LocalBinder extends Binder {
        public AudioCaptureService getService() {
            return AudioCaptureService.this;
        }
    }

    public interface AudioLevelListener {
        void onAudioLevel(int levelPercent);
    }

    private AudioLevelListener levelListener;
    private MediaProjection mediaProjection;
    private AudioRecord audioRecord;
    private AudioStreamer audioStreamer;
    private Thread captureThread;

    private AudioManager audioManager;
    private int originalMusicVolume = -1;
    private boolean isSpeakerMutedByService = false;

    private final AtomicBoolean isCapturing = new AtomicBoolean(false);

    private static final int SAMPLE_RATE = 48000;
    private static final int CHANNEL_CONFIG = AudioFormat.CHANNEL_IN_STEREO;
    private static final int AUDIO_FORMAT = AudioFormat.ENCODING_PCM_16BIT;

    public void setAudioLevelListener(AudioLevelListener listener) {
        this.levelListener = listener;
    }

    @Override
    public IBinder onBind(Intent intent) {
        return binder;
    }

    @Override
    public void onCreate() {
        super.onCreate();
        audioManager = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_NOT_STICKY;

        String action = intent.getAction();
        if (ACTION_START.equals(action)) {
            String ip = intent.getStringExtra(EXTRA_TARGET_IP);
            int port = intent.getIntExtra(EXTRA_TARGET_PORT, 58001);
            int sessionId = intent.getIntExtra(EXTRA_SESSION_ID, 1);
            boolean useMic = intent.getBooleanExtra(EXTRA_USE_MIC, false);
            boolean muteSpeaker = intent.getBooleanExtra(EXTRA_MUTE_SPEAKER, true);
            Intent projectionData = intent.getParcelableExtra(EXTRA_RESULT_DATA);

            startForegroundServiceNotification();
            startAudioCapture(ip, port, sessionId, useMic, muteSpeaker, projectionData);
        } else if (ACTION_STOP.equals(action)) {
            stopAudioCapture();
            stopForeground(true);
            stopSelf();
        }

        return START_NOT_STICKY;
    }

    private void startForegroundServiceNotification() {
        Intent notificationIntent = new Intent(this, MainActivity.class);
        PendingIntent pendingIntent = PendingIntent.getActivity(
                this, 0, notificationIntent,
                PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT
        );

        Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                .setContentTitle(getString(R.string.notification_title))
                .setContentText(getString(R.string.notification_desc))
                .setSmallIcon(android.R.drawable.ic_btn_speak_now)
                .setContentIntent(pendingIntent)
                .setOngoing(true)
                .setPriority(NotificationCompat.PRIORITY_LOW)
                .build();

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
        } else {
            startForeground(NOTIFICATION_ID, notification);
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID,
                    getString(R.string.notification_channel_name),
                    NotificationManager.IMPORTANCE_LOW
            );
            channel.setDescription("Shows active status of VBridge audio streaming");
            NotificationManager manager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
            if (manager != null) {
                manager.createNotificationChannel(channel);
            }
        }
    }

    private void startAudioCapture(String targetIp, int targetPort, int sessionId, boolean useMic, boolean muteSpeaker, Intent projectionData) {
        if (isCapturing.get()) return;

        try {
            audioStreamer = new AudioStreamer(targetIp, targetPort, sessionId);
            audioStreamer.start();

            int minBufferSize = AudioRecord.getMinBufferSize(SAMPLE_RATE, CHANNEL_CONFIG, AUDIO_FORMAT);
            int bufferSizeInBytes = Math.max(minBufferSize, 3840 * 4); // buffer for ~80ms

            if (!useMic && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q && projectionData != null) {
                // System Audio Capture using AudioPlaybackCaptureConfiguration
                MediaProjectionManager projectionManager = (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
                mediaProjection = projectionManager.getMediaProjection(MainActivity.RESULT_OK, projectionData);

                // Add all matching usages so ANY and EVERY app's audio is captured
                AudioPlaybackCaptureConfiguration.Builder configBuilder = new AudioPlaybackCaptureConfiguration.Builder(mediaProjection);
                configBuilder.addMatchingUsage(AudioAttributes.USAGE_MEDIA);
                configBuilder.addMatchingUsage(AudioAttributes.USAGE_GAME);
                configBuilder.addMatchingUsage(AudioAttributes.USAGE_UNKNOWN);

                try {
                    configBuilder.addMatchingUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE);
                    configBuilder.addMatchingUsage(AudioAttributes.USAGE_ASSISTANCE_SONIFICATION);
                    configBuilder.addMatchingUsage(AudioAttributes.USAGE_ASSISTANT);
                    configBuilder.addMatchingUsage(AudioAttributes.USAGE_ALARM);
                    configBuilder.addMatchingUsage(AudioAttributes.USAGE_NOTIFICATION);
                    configBuilder.addMatchingUsage(AudioAttributes.USAGE_NOTIFICATION_RINGTONE);
                    configBuilder.addMatchingUsage(AudioAttributes.USAGE_NOTIFICATION_COMMUNICATION_REQUEST);
                    configBuilder.addMatchingUsage(AudioAttributes.USAGE_NOTIFICATION_COMMUNICATION_INSTANT);
                    configBuilder.addMatchingUsage(AudioAttributes.USAGE_NOTIFICATION_COMMUNICATION_DELAYED);
                    configBuilder.addMatchingUsage(AudioAttributes.USAGE_NOTIFICATION_EVENT);
                } catch (Exception ignored) {
                }

                AudioPlaybackCaptureConfiguration config = configBuilder.build();

                AudioFormat audioFormat = new AudioFormat.Builder()
                        .setEncoding(AUDIO_FORMAT)
                        .setSampleRate(SAMPLE_RATE)
                        .setChannelMask(CHANNEL_CONFIG)
                        .build();

                audioRecord = new AudioRecord.Builder()
                        .setAudioFormat(audioFormat)
                        .setBufferSizeInBytes(bufferSizeInBytes)
                        .setAudioPlaybackCaptureConfig(config)
                        .build();

                Log.i(TAG, "Initialized AudioPlaybackCapture AudioRecord for all application usages");
            } else {
                // Fallback to Microphone Capture
                audioRecord = new AudioRecord(
                        MediaRecorder.AudioSource.MIC,
                        SAMPLE_RATE,
                        CHANNEL_CONFIG,
                        AUDIO_FORMAT,
                        bufferSizeInBytes
                );
                Log.i(TAG, "Initialized Microphone AudioRecord");
            }

            if (audioRecord.getState() != AudioRecord.STATE_INITIALIZED) {
                Log.e(TAG, "AudioRecord failed to initialize!");
                stopAudioCapture();
                return;
            }

            // Do not force STREAM_MUSIC to 0 as that halts AudioPlaybackCapture on Android
            Log.i(TAG, "Starting audio capture with full system audio stream");

            audioRecord.startRecording();
            isCapturing.set(true);

            captureThread = new Thread(this::captureLoop, "VBridge-CaptureLoop");
            captureThread.start();
            Log.i(TAG, "Audio recording started successfully.");

        } catch (Exception e) {
            Log.e(TAG, "Failed to start audio capture: " + e.getMessage(), e);
            stopAudioCapture();
        }
    }

    private void captureLoop() {
        Process.setThreadPriority(Process.THREAD_PRIORITY_URGENT_AUDIO);

        // Chunk size: 960 stereo 16-bit samples = 960 * 2 channels * 2 bytes = 3840 bytes = 20ms
        int chunkBytes = 3840;
        byte[] audioBuffer = new byte[chunkBytes];

        while (isCapturing.get() && audioRecord != null) {
            int bytesRead = audioRecord.read(audioBuffer, 0, chunkBytes);
            if (bytesRead > 0) {
                if (audioStreamer != null) {
                    audioStreamer.sendPcmFrame(audioBuffer, 0, bytesRead);
                }

                // Compute quick peak audio level for UI progress bar
                if (levelListener != null) {
                    int maxAmp = 0;
                    for (int i = 0; i < bytesRead - 1; i += 2) {
                        short sample = (short) ((audioBuffer[i] & 0xFF) | (audioBuffer[i + 1] << 8));
                        int abs = Math.abs(sample);
                        if (abs > maxAmp) maxAmp = abs;
                    }
                    int percent = Math.min(100, (maxAmp * 100) / 32768);
                    levelListener.onAudioLevel(percent);
                }
            }
        }
    }

    public synchronized void stopAudioCapture() {
        isCapturing.set(false);

        // Restore original phone speaker volume
        if (isSpeakerMutedByService && audioManager != null && originalMusicVolume >= 0) {
            try {
                audioManager.setStreamVolume(AudioManager.STREAM_MUSIC, originalMusicVolume, 0);
                Log.i(TAG, "Restored phone speaker volume to " + originalMusicVolume);
            } catch (Exception ignored) {
            }
            isSpeakerMutedByService = false;
            originalMusicVolume = -1;
        }

        if (captureThread != null) {
            captureThread.interrupt();
            captureThread = null;
        }

        if (audioRecord != null) {
            try {
                if (audioRecord.getRecordingState() == AudioRecord.RECORDSTATE_RECORDING) {
                    audioRecord.stop();
                }
                audioRecord.release();
            } catch (Exception ignored) {
            }
            audioRecord = null;
        }

        if (mediaProjection != null) {
            try {
                mediaProjection.stop();
            } catch (Exception ignored) {
            }
            mediaProjection = null;
        }

        if (audioStreamer != null) {
            audioStreamer.stop();
            audioStreamer = null;
        }

        Log.i(TAG, "Audio capture stopped.");
    }

    public boolean isStreaming() {
        return isCapturing.get();
    }

    @Override
    public void onDestroy() {
        stopAudioCapture();
        super.onDestroy();
    }
}
