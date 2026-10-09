package com.vbridge.audiobridge;

import android.Manifest;
import android.app.Activity;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.media.projection.MediaProjectionManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Looper;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
import android.widget.ProgressBar;
import android.widget.RadioButton;
import android.widget.RadioGroup;
import android.widget.TextView;
import android.widget.Toast;

import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.cardview.widget.CardView;
import androidx.core.app.ActivityCompat;
import androidx.core.content.ContextCompat;

import com.google.android.material.textfield.TextInputEditText;
import com.journeyapps.barcodescanner.ScanContract;
import com.journeyapps.barcodescanner.ScanOptions;

public class MainActivity extends AppCompatActivity implements ControlClient.ConnectionListener {

    private static final int PERMISSION_REQ_CODE = 1001;
    private static final String PREFS_NAME = "vbridge_prefs";
    private static final String PREF_LAST_IP = "last_server_ip";
    private static final String PREF_LAST_PORT = "last_server_port";
    private static final String PREF_LAST_CODE = "last_pairing_code";
    private static final String PREF_AUTO_CONNECT = "auto_connect_enabled";
    private static final String PREF_LAST_DEVICE_NAME = "last_device_name";

    // UI elements
    private CardView cardRecentDevice;
    private TextView tvRecentDeviceName;
    private TextView tvRecentDeviceDetails;
    private Button btnQuickConnect;
    private CheckBox chkAutoConnect;

    private TextInputEditText etServerIp;
    private TextInputEditText etServerPort;
    private TextInputEditText etPairingCode;
    private Button btnScanQr;
    private Button btnConnect;
    private TextView tvConnectionStatus;
    private TextView tvLatency;
    private RadioGroup rgAudioSource;
    private RadioButton rbInternalAudio;
    private RadioButton rbMicAudio;
    private CheckBox chkMutePhoneSpeaker;
    private Button btnToggleStream;
    private ProgressBar pbAudioLevel;

    private SharedPreferences prefs;
    private ControlClient controlClient;
    private AudioCaptureService audioService;
    private boolean isServiceBound = false;

    private int currentSessionId = 0;
    private int currentUdpPort = 58001;
    private boolean isConnectedToLaptop = false;
    private boolean isStreaming = false;

    private MediaProjectionManager projectionManager;
    private ActivityResultLauncher<Intent> projectionLauncher;
    private Intent pendingProjectionData;

    // QR Code Scanner Launcher
    private final ActivityResultLauncher<ScanOptions> qrScannerLauncher = registerForActivityResult(
            new ScanContract(),
            result -> {
                if (result.getContents() != null) {
                    parseAndApplyQrCode(result.getContents());
                }
            }
    );

    // Camera Permission Launcher for QR Scanner
    private final ActivityResultLauncher<String> cameraPermissionLauncher = registerForActivityResult(
            new ActivityResultContracts.RequestPermission(),
            isGranted -> {
                if (isGranted) {
                    launchQrScanner();
                } else {
                    Toast.makeText(this, "Camera permission is required to scan the QR code.", Toast.LENGTH_SHORT).show();
                }
            }
    );

    private final ServiceConnection serviceConnection = new ServiceConnection() {
        @Override
        public void onServiceConnected(ComponentName name, IBinder service) {
            AudioCaptureService.LocalBinder binder = (AudioCaptureService.LocalBinder) service;
            audioService = binder.getService();
            isServiceBound = true;

            audioService.setAudioLevelListener(level -> runOnUiThread(() -> {
                if (pbAudioLevel != null) {
                    pbAudioLevel.setProgress(level);
                }
            }));
        }

        @Override
        public void onServiceDisconnected(ComponentName name) {
            audioService = null;
            isServiceBound = false;
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_main);

        prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);

        initViews();
        checkPermissions();
        setupMediaProjectionLauncher();
        bindAudioService();
        loadSavedConnections();
    }

    private void initViews() {
        cardRecentDevice = findViewById(R.id.cardRecentDevice);
        tvRecentDeviceName = findViewById(R.id.tvRecentDeviceName);
        tvRecentDeviceDetails = findViewById(R.id.tvRecentDeviceDetails);
        btnQuickConnect = findViewById(R.id.btnQuickConnect);
        chkAutoConnect = findViewById(R.id.chkAutoConnect);

        etServerIp = findViewById(R.id.etServerIp);
        etServerPort = findViewById(R.id.etServerPort);
        etPairingCode = findViewById(R.id.etPairingCode);
        btnScanQr = findViewById(R.id.btnScanQr);
        btnConnect = findViewById(R.id.btnConnect);
        tvConnectionStatus = findViewById(R.id.tvConnectionStatus);
        tvLatency = findViewById(R.id.tvLatency);
        rgAudioSource = findViewById(R.id.rgAudioSource);
        rbInternalAudio = findViewById(R.id.rbInternalAudio);
        rbMicAudio = findViewById(R.id.rbMicAudio);
        chkMutePhoneSpeaker = findViewById(R.id.chkMutePhoneSpeaker);
        btnToggleStream = findViewById(R.id.btnToggleStream);
        pbAudioLevel = findViewById(R.id.pbAudioLevel);

        btnScanQr.setOnClickListener(v -> checkCameraAndScan());
        btnConnect.setOnClickListener(v -> toggleConnection());
        btnToggleStream.setOnClickListener(v -> toggleStreaming());

        if (btnQuickConnect != null) {
            btnQuickConnect.setOnClickListener(v -> toggleConnection());
        }

        if (chkAutoConnect != null) {
            chkAutoConnect.setOnCheckedChangeListener((buttonView, isChecked) -> {
                prefs.edit().putBoolean(PREF_AUTO_CONNECT, isChecked).apply();
            });
        }
    }

    private void loadSavedConnections() {
        String savedIp = prefs.getString(PREF_LAST_IP, "");
        int savedPort = prefs.getInt(PREF_LAST_PORT, 58000);
        String savedCode = prefs.getString(PREF_LAST_CODE, "1234");
        boolean autoConnect = prefs.getBoolean(PREF_AUTO_CONNECT, false);

        if (!savedIp.isEmpty()) {
            etServerIp.setText(savedIp);
            etServerPort.setText(String.valueOf(savedPort));
            etPairingCode.setText(savedCode);

            if (cardRecentDevice != null) {
                cardRecentDevice.setVisibility(View.VISIBLE);
                tvRecentDeviceName.setText("💻 Windows Laptop");
                tvRecentDeviceDetails.setText("IP: " + savedIp + " : " + savedPort + "  (Code: " + savedCode + ")");
                btnQuickConnect.setText("⚡ Reconnect to " + savedIp);
            }

            if (chkAutoConnect != null) {
                chkAutoConnect.setChecked(autoConnect);
            }

            // If auto-connect is enabled, automatically trigger connection
            if (autoConnect) {
                new Handler(Looper.getMainLooper()).postDelayed(() -> {
                    if (!isConnectedToLaptop) {
                        Toast.makeText(this, "⚡ Auto-connecting to " + savedIp + "...", Toast.LENGTH_SHORT).show();
                        toggleConnection();
                    }
                }, 600);
            }
        }
    }

    private void saveLastConnection(String ip, int port, String code) {
        prefs.edit()
                .putString(PREF_LAST_IP, ip)
                .putInt(PREF_LAST_PORT, port)
                .putString(PREF_LAST_CODE, code)
                .apply();

        runOnUiThread(() -> {
            if (cardRecentDevice != null) {
                cardRecentDevice.setVisibility(View.VISIBLE);
                tvRecentDeviceDetails.setText("IP: " + ip + " : " + port + "  (Code: " + code + ")");
                btnQuickConnect.setText("⚡ Reconnect to " + ip);
            }
        });
    }

    private void checkCameraAndScan() {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            launchQrScanner();
        } else {
            cameraPermissionLauncher.launch(Manifest.permission.CAMERA);
        }
    }

    private void launchQrScanner() {
        ScanOptions options = new ScanOptions();
        options.setCaptureActivity(CustomScannerActivity.class);
        options.setPrompt("");
        options.setBeepEnabled(true);
        options.setOrientationLocked(false);
        options.setBarcodeImageEnabled(false);
        options.setDesiredBarcodeFormats(ScanOptions.QR_CODE);
        qrScannerLauncher.launch(options);
    }

    private void parseAndApplyQrCode(String qrData) {
        try {
            if (qrData.startsWith("vbridge://")) {
                Uri uri = Uri.parse(qrData);
                String host = uri.getHost();
                int port = uri.getPort() != -1 ? uri.getPort() : 58000;
                String code = uri.getQueryParameter("code");
                if (code == null || code.isEmpty()) code = "1234";

                if (host != null && !host.isEmpty()) {
                    etServerIp.setText(host);
                    etServerPort.setText(String.valueOf(port));
                    etPairingCode.setText(code);

                    Toast.makeText(this, "QR Scanned: " + host, Toast.LENGTH_SHORT).show();

                    if (!isConnectedToLaptop) {
                        toggleConnection();
                    }
                    return;
                }
            } else if (qrData.contains(":") || qrData.matches("^\\d+\\.\\d+\\.\\d+\\.\\d+.*")) {
                String[] parts = qrData.replace("http://", "").replace("https://", "").split(":");
                etServerIp.setText(parts[0].trim());
                if (parts.length > 1) {
                    etServerPort.setText(parts[1].trim());
                }
                if (!isConnectedToLaptop) {
                    toggleConnection();
                }
                return;
            }
            Toast.makeText(this, "Scanned: " + qrData, Toast.LENGTH_SHORT).show();
        } catch (Exception e) {
            Toast.makeText(this, "Could not parse QR: " + e.getMessage(), Toast.LENGTH_SHORT).show();
        }
    }

    private void setupMediaProjectionLauncher() {
        projectionLauncher = registerForActivityResult(
                new ActivityResultContracts.StartActivityForResult(),
                result -> {
                    if (result.getResultCode() == Activity.RESULT_OK && result.getData() != null) {
                        pendingProjectionData = result.getData();
                        launchAudioService(pendingProjectionData);
                    } else {
                        Toast.makeText(this, "Media projection permission was denied.", Toast.LENGTH_SHORT).show();
                        setStreamingUiState(false);
                    }
                }
        );
    }

    private void checkPermissions() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED ||
                    ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(
                        this,
                        new String[]{Manifest.permission.RECORD_AUDIO, Manifest.permission.POST_NOTIFICATIONS},
                        PERMISSION_REQ_CODE
                );
            }
        } else {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
                ActivityCompat.requestPermissions(
                        this,
                        new String[]{Manifest.permission.RECORD_AUDIO},
                        PERMISSION_REQ_CODE
                );
            }
        }
    }

    private void bindAudioService() {
        Intent intent = new Intent(this, AudioCaptureService.class);
        bindService(intent, serviceConnection, Context.BIND_AUTO_CREATE);
    }

    private void toggleConnection() {
        if (!isConnectedToLaptop) {
            String ip = etServerIp.getText().toString().trim();
            String portStr = etServerPort.getText().toString().trim();
            String code = etPairingCode.getText().toString().trim();

            if (ip.isEmpty()) {
                Toast.makeText(this, "Please enter Laptop IP address or Scan QR code", Toast.LENGTH_SHORT).show();
                return;
            }

            int port = portStr.isEmpty() ? 58000 : Integer.parseInt(portStr);

            tvConnectionStatus.setText("🟡 Connecting...");
            tvConnectionStatus.setTextColor(ContextCompat.getColor(this, R.color.primary));
            btnConnect.setEnabled(false);
            if (btnQuickConnect != null) btnQuickConnect.setEnabled(false);
            if (btnScanQr != null) btnScanQr.setEnabled(false);

            controlClient = new ControlClient(ip, port, code, this);
            controlClient.connect();
        } else {
            if (isStreaming) {
                stopAudioStreaming();
            }
            if (controlClient != null) {
                controlClient.disconnect();
            }
            setConnectionUiState(false);
        }
    }

    private void toggleStreaming() {
        if (!isStreaming) {
            startAudioStreaming();
        } else {
            stopAudioStreaming();
        }
    }

    private void startAudioStreaming() {
        if (!isConnectedToLaptop) {
            Toast.makeText(this, "Connect to laptop first!", Toast.LENGTH_SHORT).show();
            return;
        }

        boolean useMic = rbMicAudio.isChecked();

        if (!useMic && Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            projectionManager = (MediaProjectionManager) getSystemService(Context.MEDIA_PROJECTION_SERVICE);
            if (projectionManager != null) {
                projectionLauncher.launch(projectionManager.createScreenCaptureIntent());
            }
        } else {
            launchAudioService(null);
        }
    }

    private void launchAudioService(Intent projectionData) {
        String ip = etServerIp.getText().toString().trim();
        boolean useMic = rbMicAudio.isChecked();
        boolean muteSpeaker = chkMutePhoneSpeaker != null && chkMutePhoneSpeaker.isChecked();

        Intent serviceIntent = new Intent(this, AudioCaptureService.class);
        serviceIntent.setAction(AudioCaptureService.ACTION_START);
        serviceIntent.putExtra(AudioCaptureService.EXTRA_TARGET_IP, ip);
        serviceIntent.putExtra(AudioCaptureService.EXTRA_TARGET_PORT, currentUdpPort);
        serviceIntent.putExtra(AudioCaptureService.EXTRA_SESSION_ID, currentSessionId);
        serviceIntent.putExtra(AudioCaptureService.EXTRA_USE_MIC, useMic);
        serviceIntent.putExtra(AudioCaptureService.EXTRA_MUTE_SPEAKER, muteSpeaker);

        if (projectionData != null) {
            serviceIntent.putExtra(AudioCaptureService.EXTRA_RESULT_DATA, projectionData);
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent);
        } else {
            startService(serviceIntent);
        }

        setStreamingUiState(true);
    }

    private void stopAudioStreaming() {
        Intent serviceIntent = new Intent(this, AudioCaptureService.class);
        serviceIntent.setAction(AudioCaptureService.ACTION_STOP);
        startService(serviceIntent);

        setStreamingUiState(false);
    }

    private void setConnectionUiState(boolean connected) {
        isConnectedToLaptop = connected;
        btnConnect.setEnabled(true);
        if (btnQuickConnect != null) btnQuickConnect.setEnabled(!connected);
        if (btnScanQr != null) btnScanQr.setEnabled(!connected);

        if (connected) {
            btnConnect.setText("Disconnect");
            btnConnect.setBackgroundColor(ContextCompat.getColor(this, R.color.google_red));
            btnConnect.setTextColor(ContextCompat.getColor(this, R.color.google_red_on));
            tvConnectionStatus.setText("🟢 Connected");
            tvConnectionStatus.setTextColor(ContextCompat.getColor(this, R.color.google_green));
            etServerIp.setEnabled(false);
            etServerPort.setEnabled(false);
            etPairingCode.setEnabled(false);
        } else {
            btnConnect.setText("Connect to Laptop");
            btnConnect.setBackgroundColor(ContextCompat.getColor(this, R.color.primary));
            btnConnect.setTextColor(ContextCompat.getColor(this, R.color.on_primary));
            if (isStreaming) {
                tvConnectionStatus.setText("🟡 Streaming (Reconnecting Link...)");
                tvConnectionStatus.setTextColor(ContextCompat.getColor(this, R.color.primary));
            } else {
                tvConnectionStatus.setText("🔴 Offline");
                tvConnectionStatus.setTextColor(ContextCompat.getColor(this, R.color.google_red));
            }
            tvLatency.setText("-- ms");
            etServerIp.setEnabled(true);
            etServerPort.setEnabled(true);
            etPairingCode.setEnabled(true);
        }
    }

    private void setStreamingUiState(boolean streaming) {
        isStreaming = streaming;
        if (streaming) {
            btnToggleStream.setText("⏹ Stop Audio Streaming");
            btnToggleStream.setBackgroundColor(ContextCompat.getColor(this, R.color.google_red));
            btnToggleStream.setTextColor(ContextCompat.getColor(this, R.color.google_red_on));
        } else {
            btnToggleStream.setText("▶ Start Audio Streaming");
            btnToggleStream.setBackgroundColor(ContextCompat.getColor(this, R.color.google_green));
            btnToggleStream.setTextColor(ContextCompat.getColor(this, R.color.google_green_on));
            pbAudioLevel.setProgress(0);
        }
    }

    @Override
    public void onConnected(int sessionId, int udpPort, int sampleRate, int channels) {
        runOnUiThread(() -> {
            currentSessionId = sessionId;
            currentUdpPort = udpPort;
            setConnectionUiState(true);

            String ip = etServerIp.getText().toString().trim();
            int port = Integer.parseInt(etServerPort.getText().toString().trim());
            String code = etPairingCode.getText().toString().trim();
            saveLastConnection(ip, port, code);

            Toast.makeText(MainActivity.this, "Paired with Windows Laptop!", Toast.LENGTH_SHORT).show();
        });
    }

    @Override
    public void onDisconnected(String reason) {
        runOnUiThread(() -> {
            setConnectionUiState(false);
        });
    }

    @Override
    public void onLatencyMeasured(long rttMs) {
        runOnUiThread(() -> {
            if (tvLatency != null) {
                tvLatency.setText(rttMs + " ms");
            }
        });
    }

    @Override
    public void onError(String error) {
        runOnUiThread(() -> {
            Toast.makeText(MainActivity.this, "Error: " + error, Toast.LENGTH_LONG).show();
            setConnectionUiState(false);
        });
    }

    @Override
    protected void onDestroy() {
        if (isServiceBound) {
            unbindService(serviceConnection);
            isServiceBound = false;
        }
        if (controlClient != null) {
            controlClient.disconnect();
        }
        super.onDestroy();
    }
}
