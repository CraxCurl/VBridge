package com.vbridge.audiobridge;

import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;

import org.json.JSONObject;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.SocketTimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;

public class ControlClient {
    private static final String TAG = "VBridge.ControlClient";

    public interface ConnectionListener {
        void onConnected(int sessionId, int udpPort, int sampleRate, int channels);
        void onDisconnected(String reason);
        void onLatencyMeasured(long rttMs);
        void onError(String error);
    }

    private String serverIp;
    private int serverPort;
    private String pairingCode;
    private ConnectionListener listener;

    private Socket socket;
    private DataInputStream in;
    private DataOutputStream out;

    private final AtomicBoolean isRunning = new AtomicBoolean(false);
    private final AtomicBoolean isConnected = new AtomicBoolean(false);
    private final Handler mainHandler = new Handler(Looper.getMainLooper());

    private Thread workerThread;
    private Thread pingThread;

    public ControlClient(String serverIp, int serverPort, String pairingCode, ConnectionListener listener) {
        this.serverIp = serverIp;
        this.serverPort = serverPort;
        this.pairingCode = pairingCode;
        this.listener = listener;
    }

    public synchronized void connect() {
        if (isRunning.get()) return;
        isRunning.set(true);

        workerThread = new Thread(this::runConnectionLoop, "VBridge-ControlThread");
        workerThread.start();
    }

    public synchronized void disconnect() {
        isRunning.set(false);
        isConnected.set(false);
        closeSocket();

        if (workerThread != null) {
            workerThread.interrupt();
            workerThread = null;
        }
        if (pingThread != null) {
            pingThread.interrupt();
            pingThread = null;
        }

        if (listener != null) {
            mainHandler.post(() -> listener.onDisconnected("Disconnected by user"));
        }
    }

    private void closeSocket() {
        try {
            if (socket != null && !socket.isClosed()) {
                socket.close();
            }
        } catch (Exception ignored) {
        }
        socket = null;
        in = null;
        out = null;
    }

    public boolean isConnected() {
        return isConnected.get();
    }

    private void runConnectionLoop() {
        int retryDelayMs = 1000;

        while (isRunning.get()) {
            try {
                Log.i(TAG, "Connecting to " + serverIp + ":" + serverPort + "...");
                socket = new Socket();
                socket.connect(new InetSocketAddress(serverIp, serverPort), 5000);
                socket.setTcpNoDelay(true);
                socket.setKeepAlive(true);
                socket.setSoTimeout(15000); // 15 second timeout to allow heartbeat

                in = new DataInputStream(socket.getInputStream());
                out = new DataOutputStream(socket.getOutputStream());

                // Perform Authentication Handshake
                JSONObject authObj = new JSONObject();
                authObj.put("type", "AUTH");
                authObj.put("token", pairingCode);
                authObj.put("device_name", Build.MANUFACTURER + " " + Build.MODEL);
                authObj.put("sample_rate", 48000);
                authObj.put("channels", 2);

                sendJson(authObj);

                // Read Handshake Response
                JSONObject resp = readJson();
                if (resp == null || !"OK".equals(resp.optString("status"))) {
                    String msg = resp != null ? resp.optString("message") : "Authentication failed";
                    Log.e(TAG, "Handshake rejected: " + msg);
                    if (listener != null) {
                        mainHandler.post(() -> listener.onError(msg));
                    }
                    closeSocket();
                    Thread.sleep(2000);
                    continue;
                }

                int sessionId = resp.optInt("session_id", 1);
                int udpPort = resp.optInt("udp_port", 58001);
                int sampleRate = resp.optInt("sample_rate", 48000);
                int channels = resp.optInt("channels", 2);

                isConnected.set(true);
                retryDelayMs = 1000;

                Log.i(TAG, "Authenticated! Session ID=" + sessionId + ", UDP Port=" + udpPort);
                if (listener != null) {
                    mainHandler.post(() -> listener.onConnected(sessionId, udpPort, sampleRate, channels));
                }

                // Start ping thread for latency measurement and keeping connection alive
                startPingThread();

                // Read incoming TCP messages loop
                while (isRunning.get() && isConnected.get()) {
                    try {
                        JSONObject incoming = readJson();
                        if (incoming != null) {
                            handleIncomingMessage(incoming);
                        }
                    } catch (SocketTimeoutException ste) {
                        // Normal idle timeout; continue loop
                    }
                }

            } catch (Exception e) {
                Log.w(TAG, "TCP connection error: " + e.getMessage());
            } finally {
                isConnected.set(false);
                closeSocket();
                if (pingThread != null) {
                    pingThread.interrupt();
                    pingThread = null;
                }
                if (isRunning.get()) {
                    if (listener != null) {
                        mainHandler.post(() -> listener.onDisconnected("Connection lost. Reconnecting..."));
                    }
                    try {
                        Thread.sleep(retryDelayMs);
                        retryDelayMs = Math.min(retryDelayMs * 2, 6000);
                    } catch (InterruptedException ignored) {
                        break;
                    }
                }
            }
        }
    }

    private void startPingThread() {
        pingThread = new Thread(() -> {
            while (isRunning.get() && isConnected.get()) {
                try {
                    long now = System.currentTimeMillis();
                    JSONObject ping = new JSONObject();
                    ping.put("type", "PING");
                    ping.put("timestamp", now);
                    sendJson(ping);

                    Thread.sleep(2000);
                } catch (InterruptedException e) {
                    break;
                } catch (Exception e) {
                    Log.w(TAG, "Ping send error: " + e.getMessage());
                    break;
                }
            }
        }, "VBridge-PingThread");
        pingThread.start();
    }

    private void handleIncomingMessage(JSONObject msg) {
        String type = msg.optString("type");
        if ("PONG".equals(type)) {
            long clientTs = msg.optLong("client_ts", 0);
            if (clientTs > 0) {
                long rtt = System.currentTimeMillis() - clientTs;
                if (listener != null) {
                    mainHandler.post(() -> listener.onLatencyMeasured(rtt));
                }
            }
        }
    }

    public synchronized void sendJson(JSONObject obj) throws Exception {
        if (out == null) return;
        byte[] bytes = obj.toString().getBytes("UTF-8");
        out.writeInt(bytes.length);
        out.write(bytes);
        out.flush();
    }

    private JSONObject readJson() throws Exception {
        if (in == null) return null;
        int len = in.readInt();
        if (len <= 0 || len > 65536) return null;
        byte[] buf = new byte[len];
        in.readFully(buf);
        return new JSONObject(new String(buf, "UTF-8"));
    }
}
