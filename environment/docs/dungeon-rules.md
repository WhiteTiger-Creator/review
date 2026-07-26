# Dungeon rules

These are the playable puzzle-dungeon rules for Opaline's adventurer pathing on compact boards.

Boards are stored row-major. A live route state is the occupied cell, every collected key tag, and every collapsed crumble coordinate.

Keys are collected on entry and never consumed. Doors require their matching key before entry. Crumble tiles stay walkable until a successful departure; afterward that coordinate is permanently blocked. An illegal move attempt does not collapse the current tile.

Portals use tags `a`–`d` independent of keys and doors. Each used portal tag appears on exactly two cells. Stepping onto one portal cell completes the move on its partner. Transfer does not chain.

Walls, collapsed coordinates, locked doors, and out-of-bounds neighbors are illegal destinations.
