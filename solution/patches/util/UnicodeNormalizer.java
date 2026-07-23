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

    public static String normalizeAnswer(String input) {
        if (input == null) {
            return "";
        }
        String text = Normalizer.normalize(input, Normalizer.Form.NFC);
        text = foldCase(text);
        StringBuilder stripped = new StringBuilder();
        for (int offset = 0; offset < text.length(); ) {
            int codePoint = text.codePointAt(offset);
            if (Character.isLetterOrDigit(codePoint) || Character.isWhitespace(codePoint)) {
                stripped.appendCodePoint(codePoint);
            }
            offset += Character.charCount(codePoint);
        }
        return stripped.toString().trim().replaceAll("\\s+", " ");
    }

    private static String foldCase(String input) {
        StringBuilder folded = new StringBuilder(input.length());
        for (int offset = 0; offset < input.length(); ) {
            int codePoint = input.codePointAt(offset);
            int lower = Character.toLowerCase(codePoint);
            folded.appendCodePoint(lower);
            offset += Character.charCount(codePoint);
        }
        return Normalizer.normalize(folded.toString(), Normalizer.Form.NFC);
    }
}
