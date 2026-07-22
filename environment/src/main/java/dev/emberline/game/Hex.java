package dev.emberline.game;

/**
 * Axial hex coordinate (q, r). Distance is
 * {@code (abs(dq) + abs(dr) + abs(dq + dr)) / 2}.
 */
public record Hex(int q, int r) {}
