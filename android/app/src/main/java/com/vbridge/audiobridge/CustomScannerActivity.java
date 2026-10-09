package com.vbridge.audiobridge;

import android.animation.ObjectAnimator;
import android.animation.ValueAnimator;
import android.content.pm.PackageManager;
import android.os.Bundle;
import android.view.KeyEvent;
import android.view.View;
import android.view.animation.AccelerateDecelerateInterpolator;
import android.widget.ImageButton;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;

import com.journeyapps.barcodescanner.CaptureManager;
import com.journeyapps.barcodescanner.DecoratedBarcodeView;

public class CustomScannerActivity extends AppCompatActivity implements DecoratedBarcodeView.TorchListener {

    private CaptureManager capture;
    private DecoratedBarcodeView barcodeScannerView;
    private ImageButton btnTorch;
    private ImageButton btnBack;
    private TextView tvTorchState;
    private View scanLaser;
    private View viewTargetFrame;
    private ObjectAnimator laserAnimator;
    private boolean isTorchOn = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_custom_scanner);

        barcodeScannerView = findViewById(R.id.zxing_barcode_scanner);
        barcodeScannerView.setTorchListener(this);

        btnTorch = findViewById(R.id.btnTorch);
        btnBack = findViewById(R.id.btnBack);
        tvTorchState = findViewById(R.id.tvTorchState);
        scanLaser = findViewById(R.id.scanLaser);
        viewTargetFrame = findViewById(R.id.viewTargetFrame);

        // Check if device has flashlight
        if (!hasFlash()) {
            btnTorch.setVisibility(View.GONE);
        } else {
            btnTorch.setOnClickListener(v -> toggleTorch());
        }

        btnBack.setOnClickListener(v -> finish());

        // Initialize ZXing CaptureManager
        capture = new CaptureManager(this, barcodeScannerView);
        capture.initializeFromIntent(getIntent(), savedInstanceState);
        capture.decode();

        // Start laser scan line animation
        startLaserAnimation();
    }

    private void startLaserAnimation() {
        viewTargetFrame.post(() -> {
            float startY = 0f;
            float endY = viewTargetFrame.getHeight() - scanLaser.getHeight();

            laserAnimator = ObjectAnimator.ofFloat(scanLaser, "translationY", startY, endY);
            laserAnimator.setDuration(1600);
            laserAnimator.setRepeatMode(ValueAnimator.REVERSE);
            laserAnimator.setRepeatCount(ValueAnimator.INFINITE);
            laserAnimator.setInterpolator(new AccelerateDecelerateInterpolator());
            laserAnimator.start();
        });
    }

    private boolean hasFlash() {
        return getApplicationContext().getPackageManager()
                .hasSystemFeature(PackageManager.FEATURE_CAMERA_FLASH);
    }

    private void toggleTorch() {
        if (isTorchOn) {
            barcodeScannerView.setTorchOff();
        } else {
            barcodeScannerView.setTorchOn();
        }
    }

    @Override
    public void onTorchOn() {
        isTorchOn = true;
        btnTorch.setColorFilter(0xFFFDE293); // Glowing amber
        tvTorchState.setText("🔦 Flashlight ON");
    }

    @Override
    public void onTorchOff() {
        isTorchOn = false;
        btnTorch.setColorFilter(0xFFA8C7FA); // Material Blue
        tvTorchState.setText("⚡ Auto-detecting QR Code...");
    }

    @Override
    protected void onResume() {
        super.onResume();
        capture.onResume();
        if (laserAnimator != null && laserAnimator.isPaused()) {
            laserAnimator.resume();
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        capture.onPause();
        if (laserAnimator != null && laserAnimator.isRunning()) {
            laserAnimator.pause();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        capture.onDestroy();
        if (laserAnimator != null) {
            laserAnimator.cancel();
        }
    }

    @Override
    protected void onSaveInstanceState(@NonNull Bundle outState) {
        super.onSaveInstanceState(outState);
        capture.onSaveInstanceState(outState);
    }

    @Override
    public boolean onKeyDown(int keyCode, KeyEvent event) {
        return barcodeScannerView.onKeyDown(keyCode, event) || super.onKeyDown(keyCode, event);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, @NonNull String[] permissions, @NonNull int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        capture.onRequestPermissionsResult(requestCode, permissions, grantResults);
    }
}
