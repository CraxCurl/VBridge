package com.vbridge.audiobridge;

import android.util.Log;

import java.net.DatagramPacket;
import java.net.DatagramSocket;
import java.net.InetAddress;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.util.concurrent.atomic.AtomicBoolean;

public class AudioStreamer {
    private static final String TAG = "VBridge.AudioStreamer";

    private static final byte[] MAGIC = new byte[]{'V', 'B', 'R', 'G'};
    private static final int HEADER_SIZE = 16;
    private static final byte PACKET_TYPE_AUDIO_PCM = 1;

    private String targetIp;
    private int targetPort;
    private int sessionId;

    private DatagramSocket socket;
    private InetAddress targetAddress;
    private int sequenceNumber = 0;

    private final AtomicBoolean isStreaming = new AtomicBoolean(false);

    public AudioStreamer(String targetIp, int targetPort, int sessionId) {
        this.targetIp = targetIp;
        this.targetPort = targetPort;
        this.sessionId = sessionId;
    }

    public synchronized void start() throws Exception {
        if (isStreaming.get()) return;

        targetAddress = InetAddress.getByName(targetIp);
        socket = new DatagramSocket();
        socket.setSendBufferSize(512 * 1024);
        sequenceNumber = 0;
        isStreaming.set(true);

        Log.i(TAG, "AudioStreamer started -> " + targetIp + ":" + targetPort);
    }

    public synchronized void sendPcmFrame(byte[] pcmData, int offset, int length) {
        if (!isStreaming.get() || socket == null || socket.isClosed()) return;

        try {
            int packetSize = HEADER_SIZE + length;
            byte[] packetBuffer = new byte[packetSize];
            ByteBuffer bb = ByteBuffer.wrap(packetBuffer);
            bb.order(ByteOrder.BIG_ENDIAN);

            // 1. Magic (4 bytes)
            bb.put(MAGIC);
            // 2. Version (1 byte)
            bb.put((byte) 1);
            // 3. Packet Type (1 byte: PCM = 1)
            bb.put(PACKET_TYPE_AUDIO_PCM);
            // 4. Session ID (2 bytes)
            bb.putShort((short) (sessionId & 0xFFFF));
            // 5. Sequence Number (4 bytes)
            bb.putInt(sequenceNumber++);
            // 6. Timestamp (4 bytes ms)
            int ts = (int) (System.currentTimeMillis() & 0xFFFFFFFF);
            bb.putInt(ts);

            // 7. Payload
            bb.put(pcmData, offset, length);

            DatagramPacket packet = new DatagramPacket(packetBuffer, packetSize, targetAddress, targetPort);
            socket.send(packet);

        } catch (Exception e) {
            Log.w(TAG, "Error sending audio packet: " + e.getMessage());
        }
    }

    public synchronized void stop() {
        isStreaming.set(false);
        if (socket != null && !socket.isClosed()) {
            try {
                socket.close();
            } catch (Exception ignored) {
            }
        }
        socket = null;
        Log.i(TAG, "AudioStreamer stopped.");
    }

    public boolean isStreaming() {
        return isStreaming.get();
    }
}
