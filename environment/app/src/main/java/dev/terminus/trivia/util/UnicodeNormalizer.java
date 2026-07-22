package dev.terminus.trivia.util;

import java.text.Normalizer;

public final class UnicodeNormalizer {
    private UnicodeNormalizer() {}

    public static String nfc(String input) {
        if (input == null) {
            return "";
        }
        return Normalizer.normalize(input, Normalizer.Form.NFC);
    }
}
