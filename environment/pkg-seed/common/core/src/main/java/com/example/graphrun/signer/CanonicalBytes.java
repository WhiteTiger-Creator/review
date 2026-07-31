package com.example.graphrun.signer;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.util.List;

public final class CanonicalBytes {

    private CanonicalBytes() {
    }

    public static byte[] frame(String domain, List<String> fields) {
        int size = 4 + domain.getBytes(StandardCharsets.UTF_8).length;
        for (String field : fields) {
            size += 4 + field.getBytes(StandardCharsets.UTF_8).length;
        }
        ByteBuffer buffer = ByteBuffer.allocate(size);
        writeString(buffer, domain);
        for (String field : fields) {
            writeString(buffer, field);
        }
        return buffer.array();
    }

    public static byte[] frameLoose(String domain, String... fields) {
        StringBuilder joined = new StringBuilder(domain);
        for (String field : fields) {
            joined.append('|').append(field);
        }
        return joined.toString().getBytes(StandardCharsets.UTF_8);
    }

    private static void writeString(ByteBuffer buffer, String value) {
        byte[] bytes = value.getBytes(StandardCharsets.UTF_8);
        buffer.putInt(bytes.length);
        buffer.put(bytes);
    }
}
