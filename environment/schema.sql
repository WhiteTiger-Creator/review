PRAGMA journal_mode = DELETE;
PRAGMA foreign_keys = ON;

CREATE TABLE layers (
    plot TEXT NOT NULL,
    depth REAL NOT NULL,
    temp REAL NOT NULL,
    moisture REAL NOT NULL,
    clay REAL NOT NULL,
    input REAL NOT NULL,
    f_input REAL NOT NULL,
    PRIMARY KEY (plot, depth)
);

CREATE TABLE forcing (
    plot TEXT PRIMARY KEY,
    moisture_scale REAL NOT NULL,
    oxygen_scale REAL NOT NULL
);

CREATE TABLE observations (
    plot TEXT NOT NULL,
    depth REAL NOT NULL,
    carbon REAL NOT NULL,
    respiration REAL NOT NULL,
    f14c REAL NOT NULL,
    sigma_c REAL NOT NULL,
    sigma_r REAL NOT NULL,
    sigma_f REAL NOT NULL,
    fold INTEGER NOT NULL,
    PRIMARY KEY (plot, depth)
);

CREATE TABLE bounds (
    parameter TEXT PRIMARY KEY,
    lower REAL NOT NULL,
    upper REAL NOT NULL
);

CREATE TABLE penalty_grid (
    weight REAL PRIMARY KEY
);

INSERT INTO bounds VALUES ('k0', 0.015, 0.09);
INSERT INTO bounds VALUES ('cue', 0.25, 0.70);
INSERT INTO bounds VALUES ('v', 0.001, 0.04);
INSERT INTO bounds VALUES ('input_scale', 0.60, 1.40);

INSERT INTO penalty_grid VALUES (16.0);
INSERT INTO penalty_grid VALUES (64.0);
INSERT INTO penalty_grid VALUES (250.0);
INSERT INTO penalty_grid VALUES (1000.0);
INSERT INTO penalty_grid VALUES (4000.0);
