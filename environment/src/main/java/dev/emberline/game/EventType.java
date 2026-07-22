package dev.emberline.game;

/** Canonical turn-resolution event kinds. */
public enum EventType {
    MOVE,
    MOVE_BLOCKED,
    ATTACK_HIT,
    ATTACK_MISS,
    DAMAGE,
    DEFEATED,
    SCORE
}
