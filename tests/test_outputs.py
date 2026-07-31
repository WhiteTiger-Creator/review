"""Behavioral verification for the Kotlin and Go furnace reconstruction pipeline."""

from __future__ import annotations

import binascii
import contextlib
import hashlib
import json
import math
import os
import shutil
import socket
import sqlite3
import struct
import subprocess
import time
from collections import deque
from collections.abc import Iterator
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

APP = Path("/app")
ANALYZER = APP / "bin" / "analyze-thermograms"
REBUILD = APP / "bin" / "rebuild-analyzer"
BASE_DB = APP / "data" / "thermograms.sqlite"
BASE_PROFILES = APP / "inspection-api" / "src" / "main" / "resources" / "calibrations.json"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(base_url: str, timeout: float = 20.0) -> None:
    import urllib.request

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(base_url + "/health", timeout=1.0) as response:
                if response.status == 200:
                    return
        except OSError:
            time.sleep(0.1)
    raise AssertionError("inspection API did not become healthy")


@contextlib.contextmanager
def _spring_api(database: Path, profiles: Path) -> Iterator[str]:
    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "SERVER_PORT": str(port),
            "THERMOGRAM_DB": str(database),
            "CALIBRATION_FILE": str(profiles),
        }
    )
    process = subprocess.Popen(
        [str(APP / "bin" / "start-inspection-api")],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
        text=True,
    )
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_for_health(base_url)
        yield base_url
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _decode_qir(blob: bytes, width: int, height: int) -> list[int]:
    assert blob[:4] == b"QIR2" and blob[4] == 2
    flags = blob[5]
    header_length, inner_width, inner_height = struct.unpack_from("<HHH", blob, 6)
    base, stream_length, expected_crc = struct.unpack_from("<iII", blob, 12)
    assert flags & 3 == 3 and flags & 0xF8 == 0
    assert (inner_width, inner_height) == (width, height)
    assert header_length >= 24 and header_length + stream_length == len(blob)
    stream = memoryview(blob)[header_length:]
    assert stream[-1] == 0xFF

    def decode_row(data: memoryview, row: int, indexed: bool) -> list[int]:
        cursor = 0
        predictor = base
        values: list[int] = []
        while len(values) < width:
            opcode = data[cursor]
            cursor += 1
            if opcode <= 0x3F:
                delta = (opcode >> 1) ^ -(opcode & 1)
                predictor += delta
                values.append(predictor)
            elif opcode <= 0x7F:
                count = (opcode & 0x3F) + 1
                assert len(values) + count <= width
                values.extend([predictor] * count)
            elif opcode == 0x80:
                (delta,) = struct.unpack_from("<h", data, cursor)
                cursor += 2
                predictor += delta
                values.append(predictor)
            elif opcode == 0x81:
                (predictor,) = struct.unpack_from("<i", data, cursor)
                cursor += 4
                values.append(predictor)
            elif opcode == 0x82:
                count = data[cursor]
                (delta,) = struct.unpack_from("<h", data, cursor + 1)
                cursor += 3
                assert count and len(values) + count <= width
                for _ in range(count):
                    predictor += delta
                    values.append(predictor)
            elif opcode == 0x83:
                count = data[cursor]
                cursor += 1
                assert count and len(values) + count <= width
                deltas = struct.unpack_from(f"<{count}h", data, cursor)
                cursor += 2 * count
                for delta in deltas:
                    predictor += delta
                    values.append(predictor)
            elif opcode == 0x84:
                count = data[cursor]
                delta, delta_step = struct.unpack_from("<hh", data, cursor + 1)
                cursor += 5
                assert count and len(values) + count <= width
                for _ in range(count):
                    predictor += delta
                    values.append(predictor)
                    delta += delta_step
            else:
                raise AssertionError(f"invalid opcode {opcode:#x}")
            assert -(1 << 31) <= predictor < (1 << 31)
        if indexed:
            assert data[cursor] == 0xFE and cursor + 1 == len(data)
        return values

    output: list[int] = []
    if flags & 4:
        assert header_length == 24 + 12 * height
        expected_offset = 0
        previous_crc = 0
        for row in range(height):
            offset, length, row_crc = struct.unpack_from("<III", blob, 24 + 12 * row)
            assert offset == expected_offset and length > 0
            assert offset + length <= stream_length - 1
            values = decode_row(stream[offset : offset + length], row, True)
            chained = struct.pack("<II", previous_crc, row) + b"".join(
                struct.pack("<i", value) for value in values
            )
            actual_crc = binascii.crc32(chained) & 0xFFFFFFFF
            assert actual_crc == row_crc
            previous_crc = actual_crc
            output.extend(values)
            expected_offset += length
        assert expected_offset == stream_length - 1
    else:
        assert all(value == 0 for value in blob[24:header_length])
        cursor = 0
        for row in range(height):
            # Unindexed rows share one stream, so decode the exact row prefix.
            row_start = cursor
            predictor = base
            values: list[int] = []
            while len(values) < width:
                opcode = stream[cursor]
                cursor += 1
                if opcode <= 0x3F:
                    delta = (opcode >> 1) ^ -(opcode & 1)
                    predictor += delta
                    values.append(predictor)
                elif opcode <= 0x7F:
                    count = (opcode & 0x3F) + 1
                    assert len(values) + count <= width
                    values.extend([predictor] * count)
                elif opcode == 0x80:
                    (delta,) = struct.unpack_from("<h", stream, cursor)
                    cursor += 2
                    predictor += delta
                    values.append(predictor)
                elif opcode == 0x81:
                    (predictor,) = struct.unpack_from("<i", stream, cursor)
                    cursor += 4
                    values.append(predictor)
                elif opcode == 0x82:
                    count = stream[cursor]
                    (delta,) = struct.unpack_from("<h", stream, cursor + 1)
                    cursor += 3
                    assert count and len(values) + count <= width
                    for _ in range(count):
                        predictor += delta
                        values.append(predictor)
                elif opcode == 0x83:
                    count = stream[cursor]
                    cursor += 1
                    assert count and len(values) + count <= width
                    deltas = struct.unpack_from(f"<{count}h", stream, cursor)
                    cursor += 2 * count
                    for delta in deltas:
                        predictor += delta
                        values.append(predictor)
                elif opcode == 0x84:
                    count = stream[cursor]
                    delta, delta_step = struct.unpack_from("<hh", stream, cursor + 1)
                    cursor += 5
                    assert count and len(values) + count <= width
                    for _ in range(count):
                        predictor += delta
                        values.append(predictor)
                        delta += delta_step
                else:
                    raise AssertionError(f"invalid opcode {opcode:#x} at {row_start}")
            output.extend(values)
        assert stream[cursor] == 0xFF and cursor + 1 == len(stream)

    decoded = b"".join(struct.pack("<i", value) for value in output)
    assert binascii.crc32(decoded) & 0xFFFFFFFF == expected_crc
    return output


def _zigzag(value: int) -> int:
    return (value << 1) ^ (value >> 31)


def _encode_qir(rows: list[list[int]], base: int) -> bytes:
    height = len(rows)
    width = len(rows[0])
    assert height and width and all(len(row) == width for row in rows)
    stream = bytearray()
    flattened: list[int] = []
    for row in rows:
        predictor = base
        index = 0
        while index < width:
            value = row[index]
            run = 0
            while index + run < width and row[index + run] == predictor and run < 64:
                run += 1
            if run >= 2:
                stream.append(0x40 | (run - 1))
                flattened.extend([predictor] * run)
                index += run
                continue
            if index + 2 < width:
                delta = value - predictor
                count = 1
                probe = value
                while (
                    index + count < width
                    and row[index + count] - probe == delta
                    and count < 255
                ):
                    probe = row[index + count]
                    count += 1
                if count >= 3 and not -32 <= delta <= 31:
                    stream.extend((0x82, count))
                    stream.extend(struct.pack("<h", delta))
                    for _ in range(count):
                        predictor += delta
                        flattened.append(predictor)
                    index += count
                    continue
            delta = value - predictor
            encoded = _zigzag(delta)
            if 0 <= encoded <= 0x3F:
                stream.append(encoded)
                predictor = value
            elif -32768 <= delta <= 32767:
                stream.append(0x80)
                stream.extend(struct.pack("<h", delta))
                predictor = value
            else:
                stream.append(0x81)
                stream.extend(struct.pack("<i", value))
                predictor = value
            flattened.append(value)
            index += 1
    stream.append(0xFF)
    decoded = b"".join(struct.pack("<i", value) for value in flattened)
    header = bytearray(b"QIR2")
    header.extend((2, 3))
    header.extend(
        struct.pack(
            "<HHHiII",
            24,
            width,
            height,
            base,
            len(stream),
            binascii.crc32(decoded) & 0xFFFFFFFF,
        )
    )
    return bytes(header + stream)


def _encode_qir_indexed(rows: list[list[int]], base: int) -> bytes:
    height = len(rows)
    width = len(rows[0])
    assert height and width and all(len(row) == width for row in rows)
    row_streams: list[bytes] = []
    descriptors: list[tuple[int, int, int]] = []
    flattened: list[int] = []
    offset = 0
    previous_crc = 0
    used_delta_block = False
    used_accelerated = False
    for row_index, row in enumerate(rows):
        encoded = bytearray()
        predictor = base
        index = 0
        while index < width:
            remaining = width - index
            if row_index == 0 and index == 0 and remaining >= 2:
                first_delta = row[0] - predictor
                second_delta = row[1] - row[0]
                step = second_delta - first_delta
                if all(-32768 <= value <= 32767 for value in (first_delta, step)):
                    encoded.extend((0x84, 2))
                    encoded.extend(struct.pack("<hh", first_delta, step))
                    delta = first_delta
                    for _ in range(2):
                        predictor += delta
                        flattened.append(predictor)
                        delta += step
                    index += 2
                    used_accelerated = True
                    continue
            if remaining >= 3:
                deltas = [row[index] - predictor]
                probe = row[index]
                for position in range(index + 1, width):
                    deltas.append(row[position] - probe)
                    probe = row[position]
                step = deltas[1] - deltas[0]
                count = 2
                while count < len(deltas) and deltas[count] - deltas[count - 1] == step and count < 255:
                    count += 1
                if count >= 3 and all(-32768 <= value <= 32767 for value in (deltas[0], step)):
                    encoded.extend((0x84, count))
                    encoded.extend(struct.pack("<hh", deltas[0], step))
                    delta = deltas[0]
                    for _ in range(count):
                        predictor += delta
                        flattened.append(predictor)
                        delta += step
                    index += count
                    used_accelerated = True
                    continue
            count = min(remaining, 6)
            deltas: list[int] = []
            probe = predictor
            while len(deltas) < count:
                delta = row[index + len(deltas)] - probe
                if not -32768 <= delta <= 32767:
                    break
                deltas.append(delta)
                probe += delta
            if deltas:
                encoded.extend((0x83, len(deltas)))
                encoded.extend(struct.pack(f"<{len(deltas)}h", *deltas))
                for delta in deltas:
                    predictor += delta
                    flattened.append(predictor)
                index += len(deltas)
                used_delta_block = True
                continue
            encoded.append(0x81)
            encoded.extend(struct.pack("<i", row[index]))
            predictor = row[index]
            flattened.append(predictor)
            index += 1
        encoded.append(0xFE)
        chained = struct.pack("<II", previous_crc, row_index) + b"".join(
            struct.pack("<i", value) for value in row
        )
        row_crc = binascii.crc32(chained) & 0xFFFFFFFF
        row_bytes = bytes(encoded)
        descriptors.append((offset, len(row_bytes), row_crc))
        row_streams.append(row_bytes)
        offset += len(row_bytes)
        previous_crc = row_crc
    assert used_delta_block and used_accelerated
    stream = b"".join(row_streams) + b"\xFF"
    header_length = 24 + 12 * height
    decoded = b"".join(struct.pack("<i", value) for value in flattened)
    header = bytearray(b"QIR2")
    header.extend((2, 7))
    header.extend(
        struct.pack(
            "<HHHiII",
            header_length,
            width,
            height,
            base,
            len(stream),
            binascii.crc32(decoded) & 0xFFFFFFFF,
        )
    )
    for descriptor in descriptors:
        header.extend(struct.pack("<III", *descriptor))
    return bytes(header + stream)


def _rewrite_frames_as_indexed(database: Path) -> None:
    connection = sqlite3.connect(database)
    rows = connection.execute(
        "SELECT frame_id,width,height,qir_blob FROM frames ORDER BY frame_id"
    ).fetchall()
    for frame_id, width, height, blob in rows:
        values = _decode_qir(blob, width, height)
        base = struct.unpack_from("<i", blob, 12)[0]
        matrix = [values[offset : offset + width] for offset in range(0, len(values), width)]
        connection.execute(
            "UPDATE frames SET qir_blob=? WHERE frame_id=?",
            (_encode_qir_indexed(matrix, base), frame_id),
        )
    connection.commit()
    connection.close()

def _temperature(raw: float, calibration: dict[str, Any]) -> float:
    sensor = (
        calibration["offsetC"]
        + calibration["gain"] * raw
        + calibration["quadratic"] * raw * raw
    )
    difference = sensor - calibration["ambientC"]
    return (
        calibration["ambientC"]
        + difference / calibration["emissivity"]
        + calibration["ambientCoupling"] * difference
    )


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _repair(
    raw: list[int],
    width: int,
    height: int,
    bad_pixels: list[int],
) -> list[float]:
    assert len(set(bad_pixels)) == len(bad_pixels)
    assert all(0 <= index < len(raw) for index in bad_pixels)
    bad = set(bad_pixels)
    repaired = [float(value) for value in raw]
    for index in bad_pixels:
        x = index % width
        y = index // width
        neighbours: list[int] = []
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = x + dx
                ny = y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    candidate = ny * width + nx
                    if candidate not in bad:
                        neighbours.append(raw[candidate])
        assert len(neighbours) >= 3
        repaired[index] = _median([float(value) for value in neighbours])
    return repaired


def _solve3(matrix: list[list[float]], rhs: list[float]) -> list[float]:
    augmented = [row[:] + [rhs[index]] for index, row in enumerate(matrix)]
    scale = max(abs(value) for row in matrix for value in row)
    assert math.isfinite(scale) and scale > 0.0
    for column in range(3):
        pivot_row = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        assert abs(augmented[pivot_row][column]) > 1e-12 * scale
        augmented[column], augmented[pivot_row] = augmented[pivot_row], augmented[column]
        pivot = augmented[column][column]
        for col in range(column, 4):
            augmented[column][col] /= pivot
        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            for col in range(column, 4):
                augmented[row][col] -= factor * augmented[column][col]
    return [augmented[index][3] for index in range(3)]


def _inverse3(matrix: list[list[float]]) -> list[list[float]]:
    inverse = [[0.0] * 3 for _ in range(3)]
    for column in range(3):
        rhs = [0.0] * 3
        rhs[column] = 1.0
        solution = _solve3([row[:] for row in matrix], rhs)
        for row in range(3):
            inverse[row][column] = solution[row]
    return inverse


def _matmul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    return [
        [sum(left[i][k] * right[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]


def _transpose(matrix: list[list[float]]) -> list[list[float]]:
    return [[matrix[j][i] for j in range(3)] for i in range(3)]


def _fit_references(
    rows: list[tuple[str, int, float, float]],
    preliminary: list[float],
    bad_pixels: list[int],
) -> tuple[float, float, float, float, float, list[list[float]]]:
    grouped: dict[str, list[tuple[int, float, float]]] = {}
    for reference_id, pixel_index, expected_c, sigma_c in rows:
        grouped.setdefault(reference_id, []).append((pixel_index, expected_c, sigma_c))
    assert len(grouped) >= 5
    pairs: list[tuple[float, float, float]] = []
    for samples in grouped.values():
        indices = [row[0] for row in samples]
        targets = [row[1] for row in samples]
        sigmas = [row[2] for row in samples]
        assert len(samples) >= 2 and len(set(indices)) == len(indices)
        assert all(0 <= index < len(preliminary) for index in indices)
        assert not set(indices) & set(bad_pixels)
        assert len(set(targets)) == 1 and len(set(sigmas)) == 1
        assert math.isfinite(targets[0]) and math.isfinite(sigmas[0]) and sigmas[0] > 0.0
        pairs.append((_median([preliminary[index] for index in indices]), targets[0], sigmas[0]))

    base_weights = [1.0 / (sigma * sigma) for _, _, sigma in pairs]
    total_weight = sum(base_weights)
    center = sum(pair[0] * base_weights[index] for index, pair in enumerate(pairs)) / total_weight
    span = max(abs(x - center) for x, _, _ in pairs)
    assert math.isfinite(span) and span > 0.0
    robust = [1.0] * len(pairs)
    normalized = [0.0] * 3
    final_matrix = [[0.0] * 3 for _ in range(3)]
    final_weights = [0.0] * len(pairs)
    for iteration in range(8):
        matrix = [[0.0] * 3 for _ in range(3)]
        rhs = [0.0] * 3
        for index, (x, y, _) in enumerate(pairs):
            z = (x - center) / span
            basis = [z * z, z, 1.0]
            weight = base_weights[index] * robust[index]
            final_weights[index] = weight
            for i in range(3):
                rhs[i] += weight * basis[i] * y
                for j in range(3):
                    matrix[i][j] += weight * basis[i] * basis[j]
        normalized = _solve3(matrix, rhs)
        final_matrix = matrix
        if iteration < 7:
            for index, (x, y, sigma) in enumerate(pairs):
                z = (x - center) / span
                prediction = normalized[0] * z * z + normalized[1] * z + normalized[2]
                standardized = abs(prediction - y) / sigma
                robust[index] = 1.0 if standardized <= 1.5 else 1.5 / standardized
                assert math.isfinite(robust[index]) and robust[index] > 0.0

    a, b, d = normalized
    quadratic = a / (span * span)
    linear = b / span - 2.0 * a * center / (span * span)
    offset = d - b * center / span + a * center * center / (span * span)
    low = min(x for x, _, _ in pairs)
    high = max(x for x, _, _ in pairs)
    assert 2.0 * quadratic * low + linear > 0.0
    assert 2.0 * quadratic * high + linear > 0.0
    residuals = [quadratic * x * x + linear * x + offset - y for x, y, _ in pairs]
    weighted_sse = sum(final_weights[i] * residuals[i] ** 2 for i in range(len(pairs)))
    weighted_rmse = math.sqrt(weighted_sse / sum(final_weights))
    reduced_chi_square = weighted_sse / (len(pairs) - 3)
    assert math.isfinite(reduced_chi_square) and reduced_chi_square > 0.0
    covariance_normalized = [
        [value * reduced_chi_square for value in row]
        for row in _inverse3(final_matrix)
    ]
    transform = [
        [1.0 / (span * span), 0.0, 0.0],
        [-2.0 * center / (span * span), 1.0 / span, 0.0],
        [center * center / (span * span), -center / span, 1.0],
    ]
    covariance = _matmul(_matmul(transform, covariance_normalized), _transpose(transform))
    assert all(
        math.isfinite(value)
        for value in (quadratic, linear, offset, weighted_rmse)
        for _ in (0,)
    )
    assert all(math.isfinite(value) for row in covariance for value in row)
    return quadratic, linear, offset, weighted_rmse, reduced_chi_square, covariance


def _propagated_uncertainty(
    value: float,
    covariance: list[list[float]],
    detector_noise_c: float,
) -> float:
    gradient = [value * value, value, 1.0]
    fit_variance = sum(
        gradient[i] * covariance[i][j] * gradient[j]
        for i in range(3)
        for j in range(3)
    )
    assert math.isfinite(fit_variance) and fit_variance >= -1e-9
    sigma = math.sqrt(max(0.0, fit_variance) + detector_noise_c * detector_noise_c)
    assert math.isfinite(sigma) and sigma > 0.0
    return sigma


def _orient(
    values: list[float],
    width: int,
    height: int,
    geometry: dict[str, Any],
) -> tuple[int, int, list[float]]:
    rotation = geometry["rotation"]
    assert rotation in (0, 90, 180, 270)
    output_width = height if rotation in (90, 270) else width
    output_height = width if rotation in (90, 270) else height
    output = [math.nan] * (output_width * output_height)
    for y in range(height):
        for x in range(width):
            mirrored_x = width - 1 - x if geometry["mirrorX"] else x
            if rotation == 0:
                output_x, output_y = mirrored_x, y
            elif rotation == 90:
                output_x, output_y = height - 1 - y, mirrored_x
            elif rotation == 180:
                output_x, output_y = width - 1 - mirrored_x, height - 1 - y
            else:
                output_x, output_y = y, width - 1 - mirrored_x
            output[output_y * output_width + output_x] = values[y * width + x]
    assert all(math.isfinite(value) for value in output)
    return output_width, output_height, output


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    position = 0.95 * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    return ordered[low] + (position - low) * (ordered[high] - ordered[low])


def _project(x: float, y: float, homography: list[float]) -> tuple[float, float]:
    assert len(homography) == 9 and all(math.isfinite(value) for value in homography)
    denominator = homography[6] * x + homography[7] * y + homography[8]
    assert math.isfinite(denominator) and abs(denominator) > 1e-12
    px = (homography[0] * x + homography[1] * y + homography[2]) / denominator
    py = (homography[3] * x + homography[4] * y + homography[5]) / denominator
    assert math.isfinite(px) and math.isfinite(py)
    return px, py


def _physical_grid(
    width: int,
    height: int,
    homography: list[float],
) -> tuple[list[tuple[float, float]], list[float]]:
    centres: list[tuple[float, float]] = []
    areas: list[float] = []
    for y in range(height):
        for x in range(width):
            centres.append(_project(float(x), float(y), homography))
            corners = [
                _project(x - 0.5, y - 0.5, homography),
                _project(x + 0.5, y - 0.5, homography),
                _project(x + 0.5, y + 0.5, homography),
                _project(x - 0.5, y + 0.5, homography),
            ]
            twice_area = sum(
                corners[index][0] * corners[(index + 1) % 4][1]
                - corners[(index + 1) % 4][0] * corners[index][1]
                for index in range(4)
            )
            area = abs(twice_area) / 2.0
            assert math.isfinite(area) and area > 0.0
            areas.append(area)
    return centres, areas


def _spatial_sigma(
    indices: list[int],
    contributions: list[float],
    centres: list[tuple[float, float]],
    geometry: dict[str, Any],
) -> float:
    major_length = geometry["correlationMajorMm"]
    minor_length = geometry["correlationMinorMm"]
    angle_degrees = geometry["correlationAngleDeg"]
    assert math.isfinite(major_length) and major_length > 0.0
    assert math.isfinite(minor_length) and minor_length > 0.0
    assert math.isfinite(angle_degrees)
    angle = math.radians(angle_degrees)
    cosine = math.cos(angle)
    sine = math.sin(angle)
    variance = 0.0
    for position, left in enumerate(indices):
        left_contribution = contributions[left]
        assert math.isfinite(left_contribution)
        variance += left_contribution * left_contribution
        for right in indices[position + 1 :]:
            dx = centres[right][0] - centres[left][0]
            dy = centres[right][1] - centres[left][1]
            major = cosine * dx + sine * dy
            minor = -sine * dx + cosine * dy
            scaled_squared = (major / major_length) ** 2 + (minor / minor_length) ** 2
            correlation = math.exp(-0.5 * scaled_squared)
            assert math.isfinite(correlation) and 0.0 < correlation <= 1.0
            variance += 2.0 * left_contribution * contributions[right] * correlation
    assert math.isfinite(variance) and variance > 0.0
    sigma = math.sqrt(variance)
    assert math.isfinite(sigma) and sigma > 0.0
    return sigma



def _invert_matrix(matrix: list[list[float]]) -> list[list[float]]:
    size = len(matrix)
    assert size > 0 and all(len(row) == size for row in matrix)
    augmented = [
        list(row) + [1.0 if column == index else 0.0 for column in range(size)]
        for index, row in enumerate(matrix)
    ]
    matrix_scale = max(abs(value) for row in matrix for value in row)
    assert math.isfinite(matrix_scale) and matrix_scale > 0.0
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        assert abs(augmented[pivot][column]) > 1e-12 * matrix_scale
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                augmented[row][index] - factor * augmented[column][index]
                for index in range(2 * size)
            ]
    inverse = [row[size:] for row in augmented]
    assert all(math.isfinite(value) for row in inverse for value in row)
    return inverse


def _temporal_covariance(
    rows: list[dict[str, Any]],
    sigma_key: str,
) -> list[list[float]]:
    scale = rows[0]["temporalCorrelationSeconds"]
    assert math.isfinite(scale) and scale > 0.0
    assert all(row["temporalCorrelationSeconds"] == scale for row in rows)
    covariance: list[list[float]] = []
    for left in rows:
        left_sigma = left[sigma_key]
        assert math.isfinite(left_sigma) and left_sigma > 0.0
        current: list[float] = []
        for right in rows:
            right_sigma = right[sigma_key]
            assert math.isfinite(right_sigma) and right_sigma > 0.0
            elapsed = abs((right["instant"] - left["instant"]).total_seconds())
            correlation = math.exp(-elapsed / scale)
            assert math.isfinite(correlation) and 0.0 < correlation <= 1.0
            current.append(left_sigma * right_sigma * correlation)
        covariance.append(current)
    return covariance


def _gls_arrhenius_acceleration(rows: list[dict[str, Any]]) -> dict[str, Any]:
    covariance = _temporal_covariance(rows, "arrheniusSigma")
    sigmas = [row["arrheniusSigma"] for row in rows]
    correlation = [
        [covariance[i][j] / (sigmas[i] * sigmas[j]) for j in range(len(rows))]
        for i in range(len(rows))
    ]
    inverse_correlation = _invert_matrix(correlation)
    inverse = [
        [inverse_correlation[i][j] / (sigmas[i] * sigmas[j]) for j in range(len(rows))]
        for i in range(len(rows))
    ]
    origin = rows[0]["instant"]
    times = [(row["instant"] - origin).total_seconds() / 60.0 for row in rows]
    assert all(right > left for left, right in pairwise(times))
    values = [row["arrheniusRate"] for row in rows]
    n00 = n01 = n11 = rhs0 = rhs1 = 0.0
    for i in range(len(rows)):
        for j in range(len(rows)):
            weight = inverse[i][j]
            n00 += weight
            n01 += weight * times[j]
            n11 += times[i] * weight * times[j]
            rhs0 += weight * values[j]
            rhs1 += times[i] * weight * values[j]
    determinant = n00 * n11 - n01 * n01
    matrix_scale = max(abs(n00), abs(n01), abs(n11))
    assert matrix_scale > 0.0 and determinant > 1e-12 * matrix_scale * matrix_scale
    slope = (-n01 * rhs0 + n00 * rhs1) / determinant
    slope_variance = n00 / determinant
    assert math.isfinite(slope_variance) and slope_variance > 0.0
    sigma = math.sqrt(slope_variance)
    lower95 = slope - 1.96 * sigma
    assert all(math.isfinite(value) for value in (slope, sigma, lower95))
    return {
        "cameraId": rows[0]["cameraId"],
        "fromFrameId": rows[0]["frameId"],
        "toFrameId": rows[-1]["frameId"],
        "observationCount": len(rows),
        "acceleration": slope,
        "sigma": sigma,
        "lower95": lower95,
    }

def _hot_region(
    values: list[float],
    uncertainties: list[float],
    lower_confidence: list[float],
    areas: list[float],
    centres: list[tuple[float, float]],
    width: int,
    height: int,
    hot_sigma: float,
    min_area: int,
    geometry: dict[str, Any],
) -> tuple[float, dict[str, Any] | None, float | None, float | None, float | None]:
    center = _median(lower_confidence)
    mad = _median([abs(value - center) for value in lower_confidence])
    threshold = center + hot_sigma * 1.4826 * mad
    hot = [value > threshold for value in lower_confidence]
    seen = [False] * len(values)
    components: list[dict[str, Any]] = []
    for start in range(len(values)):
        if not hot[start] or seen[start]:
            continue
        queue: deque[int] = deque([start])
        seen[start] = True
        indices: list[int] = []
        while queue:
            current = queue.popleft()
            indices.append(current)
            x = current % width
            y = current // width
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx = x + dx
                    ny = y + dy
                    if 0 <= nx < width and 0 <= ny < height:
                        nxt = ny * width + nx
                        if hot[nxt] and not seen[nxt]:
                            seen[nxt] = True
                            queue.append(nxt)
        if len(indices) < min_area:
            continue
        area_mm2 = sum(areas[index] for index in indices)
        integrated = sum((values[index] - threshold) * areas[index] for index in indices)
        load_contributions = [0.0] * len(values)
        for index in indices:
            load_contributions[index] = uncertainties[index] * areas[index]
        load_sigma = _spatial_sigma(indices, load_contributions, centres, geometry)
        lower95 = integrated - 1.96 * load_sigma
        if not math.isfinite(lower95) or lower95 <= 0.0:
            continue
        peak_index = min(
            indices,
            key=lambda index: (-lower_confidence[index], -values[index], index),
        )
        components.append(
            {
                "indices": indices,
                "area": area_mm2,
                "integrated": integrated,
                "loadSigma": load_sigma,
                "integratedForAudit": integrated or 0.0,
                "loadSigmaForAudit": load_sigma or 0.0,
                "lower95": lower95,
                "peakIndex": peak_index,
                "minX": min(index % width for index in indices),
                "minY": min(index // width for index in indices),
                "maxX": max(index % width for index in indices),
                "maxY": max(index // width for index in indices),
            }
        )
    if not components:
        return threshold, None, None, None, None
    chosen = min(
        components,
        key=lambda row: (
            -row["lower95"],
            -row["integrated"],
            -row["area"],
            -len(row["indices"]),
            row["minY"],
            row["minX"],
            row["peakIndex"],
        ),
    )
    weights = [
        (lower_confidence[index] - threshold) * areas[index]
        for index in chosen["indices"]
    ]
    total_weight = sum(weights)
    assert math.isfinite(total_weight) and total_weight > 0.0
    centroid_x = sum(
        centres[index][0] * weights[position]
        for position, index in enumerate(chosen["indices"])
    ) / total_weight
    centroid_y = sum(
        centres[index][1] * weights[position]
        for position, index in enumerate(chosen["indices"])
    ) / total_weight
    peak_index = chosen["peakIndex"]
    return (
        threshold,
        {
            "areaPixels": len(chosen["indices"]),
            "areaMm2": _round(chosen["area"]),
            "peak": {
                "x": peak_index % width,
                "y": peak_index // width,
                "temperatureC": _round(values[peak_index]),
                "uncertaintyC": _round(uncertainties[peak_index]),
            },
            "centroidMm": {"x": _round(centroid_x), "y": _round(centroid_y)},
            "integratedExcessCmm2": _round(chosen["integrated"]),
            "loadSigmaCmm2": _round(chosen["loadSigma"]),
            "lower95IntegratedExcessCmm2": _round(chosen["lower95"]),
            "bounds": {
                "minX": chosen["minX"],
                "minY": chosen["minY"],
                "maxX": chosen["maxX"],
                "maxY": chosen["maxY"],
            },
        },
        chosen["integrated"],
        chosen["loadSigma"],
        chosen["lower95"],
    )


def _round(value: float) -> float:
    rounded = float(
        Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
    )
    return 0.0 if rounded == 0.0 else rounded


def _profile_maps(
    profiles: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    document = json.loads(profiles.read_text())
    calibrations = {row["cameraId"]: row for row in document["calibrations"]}
    geometries = {row["cameraId"]: row for row in document["geometries"]}
    return calibrations, geometries



def _evidence_digest(rows: list[dict[str, Any]]) -> str:
    payload = bytearray(b"TGA1")
    payload.extend(struct.pack("<I", len(rows)))
    for row in rows:
        for key in ("frameId", "cameraId", "capturedAt"):
            encoded = row[key].encode("utf-8")
            assert encoded and len(encoded) <= 65535
            payload.extend(struct.pack("<H", len(encoded)))
            payload.extend(encoded)
        epoch_millis = int(row["instant"].timestamp() * 1000)
        payload.extend(struct.pack("<q", epoch_millis))
        for key in (
            "temporalCorrelationSeconds",
            "arrheniusRate",
            "arrheniusSigma",
            "integratedForAudit",
            "loadSigmaForAudit",
        ):
            scaled = int(
                Decimal(str(row[key]))
                .quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
                * 1_000
            )
            payload.extend(struct.pack("<q", scaled))
    return hashlib.sha256(payload).hexdigest()


def _episode_profile_rows(database: Path) -> dict[str, dict[str, Any]]:
    connection = sqlite3.connect(database)
    rows = connection.execute(
        "SELECT camera_id,min_frames,max_gap_seconds,cross_metric_correlation,"
        "load_sigma_floor_cmm2,min_glr FROM episode_profiles ORDER BY camera_id"
    ).fetchall()
    connection.close()
    profiles: dict[str, dict[str, Any]] = {}
    for camera_id, min_frames, max_gap, cross, load_floor, min_glr in rows:
        assert camera_id not in profiles
        assert min_frames >= 2
        assert math.isfinite(max_gap) and max_gap > 0.0
        assert math.isfinite(cross) and -0.95 < cross < 0.95
        assert math.isfinite(load_floor) and load_floor > 0.0
        assert math.isfinite(min_glr) and min_glr >= 0.0
        profiles[camera_id] = {
            "minFrames": min_frames,
            "maxGapSeconds": max_gap,
            "cross": cross,
            "loadFloor": load_floor,
            "minGlr": min_glr,
        }
    return profiles


def _selection9(value: float) -> Decimal:
    return Decimal(str(value)).quantize(
        Decimal("0.000000001"), rounding=ROUND_HALF_UP
    )


def _dominant_bivariate_episode(
    rows: list[dict[str, Any]],
    database: Path,
) -> dict[str, Any] | None:
    profiles = _episode_profile_rows(database)
    candidates: list[dict[str, Any]] = []
    for camera_id in sorted({row["cameraId"] for row in rows}):
        profile = profiles[camera_id]
        camera_rows = sorted(
            [row for row in rows if row["cameraId"] == camera_id],
            key=lambda row: (row["instant"], row["frameId"]),
        )
        assert all(
            later["instant"] > earlier["instant"]
            for earlier, later in pairwise(camera_rows)
        )
        tau = camera_rows[0]["temporalCorrelationSeconds"]
        assert math.isfinite(tau) and tau > 0.0
        assert all(row["temporalCorrelationSeconds"] == tau for row in camera_rows)
        count = len(camera_rows)
        if count <= profile["minFrames"]:
            continue
        size = 2 * count
        correlation = [[0.0] * size for _ in range(size)]
        scales = [0.0] * size
        values = [0.0] * size
        origin = camera_rows[0]["instant"]
        times = [
            (row["instant"] - origin).total_seconds() / 60.0
            for row in camera_rows
        ]
        for i, left in enumerate(camera_rows):
            values[2 * i] = left["arrheniusRate"]
            values[2 * i + 1] = left["integratedForAudit"]
            scales[2 * i] = left["arrheniusSigma"]
            scales[2 * i + 1] = max(
                left["loadSigmaForAudit"], profile["loadFloor"]
            )
            for j, right in enumerate(camera_rows):
                rho = math.exp(
                    -abs((right["instant"] - left["instant"]).total_seconds()) / tau
                )
                correlation[2 * i][2 * j] = rho
                correlation[2 * i + 1][2 * j + 1] = rho
                correlation[2 * i][2 * j + 1] = profile["cross"] * rho
                correlation[2 * j + 1][2 * i] = profile["cross"] * rho
        inverse_correlation = _invert_matrix(correlation)
        for start in range(count):
            for end in range(
                start + profile["minFrames"] - 1,
                count,
            ):
                observation_count = end - start + 1
                if observation_count >= count:
                    continue
                if any(
                    (
                        camera_rows[index]["instant"]
                        - camera_rows[index - 1]["instant"]
                    ).total_seconds()
                    > profile["maxGapSeconds"]
                    for index in range(start + 1, end + 1)
                ):
                    continue
                design = [[0.0] * 6 for _ in range(size)]
                for index, time_value in enumerate(times):
                    inside = start <= index <= end
                    design[2 * index][0] = 1.0
                    design[2 * index][1] = time_value
                    design[2 * index + 1][2] = 1.0
                    design[2 * index + 1][3] = time_value
                    if inside:
                        design[2 * index][4] = 1.0
                        design[2 * index + 1][5] = 1.0
                normalized_values = [
                    values[index] / scales[index] for index in range(size)
                ]
                normalized_design = [
                    [
                        design[index][column] / scales[index]
                        for column in range(6)
                    ]
                    for index in range(size)
                ]
                column_scales = [
                    max(abs(normalized_design[index][column]) for index in range(size))
                    for column in range(6)
                ]
                assert all(
                    math.isfinite(value) and value > 0.0
                    for value in column_scales
                )
                for index in range(size):
                    for column in range(6):
                        normalized_design[index][column] /= column_scales[column]
                normal = [[0.0] * 6 for _ in range(6)]
                rhs = [0.0] * 6
                for a in range(6):
                    for b in range(6):
                        normal[a][b] = sum(
                            normalized_design[i][a]
                            * inverse_correlation[i][j]
                            * normalized_design[j][b]
                            for i in range(size)
                            for j in range(size)
                        )
                    rhs[a] = sum(
                        normalized_design[i][a]
                        * inverse_correlation[i][j]
                        * normalized_values[j]
                        for i in range(size)
                        for j in range(size)
                    )
                try:
                    gamma_covariance = _invert_matrix(normal)
                except AssertionError:
                    continue
                gamma = [
                    sum(gamma_covariance[i][j] * rhs[j] for j in range(6))
                    for i in range(6)
                ]
                beta = [
                    gamma[index] / column_scales[index]
                    for index in range(6)
                ]
                coefficient_covariance = [
                    [
                        gamma_covariance[i][j]
                        / (column_scales[i] * column_scales[j])
                        for j in range(6)
                    ]
                    for i in range(6)
                ]
                rate_shift = beta[4]
                load_shift = beta[5]
                rate_variance = coefficient_covariance[4][4]
                load_variance = coefficient_covariance[5][5]
                assert rate_variance > 0.0 and load_variance > 0.0
                rate_sigma = math.sqrt(rate_variance)
                load_sigma = math.sqrt(load_variance)
                rate_lower = rate_shift - 1.96 * rate_sigma
                load_lower = load_shift - 1.96 * load_sigma
                shift_covariance = [
                    [coefficient_covariance[4][4], coefficient_covariance[4][5]],
                    [coefficient_covariance[5][4], coefficient_covariance[5][5]],
                ]
                inverse_shift = _invert_matrix(shift_covariance)
                glr = (
                    rate_shift
                    * (
                        inverse_shift[0][0] * rate_shift
                        + inverse_shift[0][1] * load_shift
                    )
                    + load_shift
                    * (
                        inverse_shift[1][0] * rate_shift
                        + inverse_shift[1][1] * load_shift
                    )
                )
                assert all(
                    math.isfinite(value)
                    for value in (
                        rate_shift,
                        load_shift,
                        rate_sigma,
                        load_sigma,
                        rate_lower,
                        load_lower,
                        glr,
                    )
                )
                if (
                    rate_lower > 0.0
                    and load_lower > 0.0
                    and glr >= profile["minGlr"]
                ):
                    candidates.append(
                        {
                            "cameraId": camera_id,
                            "fromFrameId": camera_rows[start]["frameId"],
                            "toFrameId": camera_rows[end]["frameId"],
                            "observationCount": observation_count,
                            "rateShift": rate_shift,
                            "rateSigma": rate_sigma,
                            "rateLower": rate_lower,
                            "loadShift": load_shift,
                            "loadSigma": load_sigma,
                            "loadLower": load_lower,
                            "glr": glr,
                        }
                    )
    if not candidates:
        return None
    winner = min(
        candidates,
        key=lambda row: (
            -_selection9(row["glr"]),
            -_selection9(row["rateLower"]),
            -_selection9(row["loadLower"]),
            row["cameraId"],
            row["fromFrameId"],
            row["toFrameId"],
        ),
    )
    return {
        "cameraId": winner["cameraId"],
        "fromFrameId": winner["fromFrameId"],
        "toFrameId": winner["toFrameId"],
        "observationCount": winner["observationCount"],
        "arrheniusShiftMm2PerSecond": _round(winner["rateShift"]),
        "arrheniusShiftSigmaMm2PerSecond": _round(winner["rateSigma"]),
        "arrheniusLower95Mm2PerSecond": _round(winner["rateLower"]),
        "loadShiftCmm2": _round(winner["loadShift"]),
        "loadShiftSigmaCmm2": _round(winner["loadSigma"]),
        "loadLower95Cmm2": _round(winner["loadLower"]),
        "generalizedLikelihoodRatio": _round(winner["glr"]),
    }


def _expected(database: Path, profiles: Path) -> dict[str, Any]:
    calibrations, geometries = _profile_maps(profiles)
    connection = sqlite3.connect(database)
    frames = connection.execute(
        "SELECT frame_id,camera_id,captured_at,width,height,qir_blob "
        "FROM frames ORDER BY captured_at,frame_id"
    ).fetchall()
    checkpoint_rows = connection.execute(
        "SELECT frame_id,pixel_index,raw_count FROM frame_checkpoints "
        "ORDER BY frame_id,pixel_index"
    ).fetchall()
    reference_rows = connection.execute(
        "SELECT frame_id,reference_id,pixel_index,expected_c,sigma_c FROM reference_samples "
        "ORDER BY frame_id,reference_id,pixel_index"
    ).fetchall()
    connection.close()
    checkpoints: dict[str, dict[int, int]] = {}
    references: dict[str, list[tuple[str, int, float, float]]] = {}
    for frame_id, pixel_index, raw_count in checkpoint_rows:
        checkpoints.setdefault(frame_id, {})[pixel_index] = raw_count
    for frame_id, reference_id, pixel_index, expected_c, sigma_c in reference_rows:
        references.setdefault(frame_id, []).append((reference_id, pixel_index, expected_c, sigma_c))

    reports: list[dict[str, Any]] = []
    internal: list[dict[str, Any]] = []
    for frame_id, camera_id, captured_at, sensor_width, sensor_height, blob in frames:
        raw = _decode_qir(blob, sensor_width, sensor_height)
        for index, expected_count in checkpoints.get(frame_id, {}).items():
            assert 0 <= index < len(raw) and raw[index] == expected_count
        calibration = calibrations[camera_id]
        geometry = geometries[camera_id]
        assert all(
            math.isfinite(geometry[key]) and geometry[key] > 0.0
            for key in (
                "arrheniusA",
                "activationEnergyJMol",
                "detectorNoiseC",
                "confidenceK",
                "correlationMajorMm",
                "correlationMinorMm",
                "temporalCorrelationSeconds",
            )
        )
        assert math.isfinite(geometry["correlationAngleDeg"])
        repaired = _repair(raw, sensor_width, sensor_height, geometry["badPixels"])
        preliminary = [_temperature(value, calibration) for value in repaired]
        quadratic, linear, offset, weighted_rmse, reduced_chi_square, covariance = _fit_references(
            references.get(frame_id, []), preliminary, geometry["badPixels"]
        )
        corrected = [quadratic * value * value + linear * value + offset for value in preliminary]
        uncertainty = [
            _propagated_uncertainty(value, covariance, geometry["detectorNoiseC"])
            for value in preliminary
        ]
        width, height, temperatures = _orient(corrected, sensor_width, sensor_height, geometry)
        _, _, uncertainties = _orient(uncertainty, sensor_width, sensor_height, geometry)
        lower_confidence = [
            temperatures[index] - geometry["confidenceK"] * uncertainties[index]
            for index in range(len(temperatures))
        ]
        centres, areas = _physical_grid(width, height, geometry["homography"])
        mean = sum(temperatures) / len(temperatures)
        variance = sum((value - mean) ** 2 for value in temperatures) / len(temperatures)
        maximum = max(temperatures)
        hotspot_index = temperatures.index(maximum)
        threshold, region, integrated, load_sigma, lower95 = _hot_region(
            temperatures,
            uncertainties,
            lower_confidence,
            areas,
            centres,
            width,
            height,
            geometry["hotSigma"],
            geometry["minHotArea"],
            geometry,
        )
        arrhenius_rate = 0.0
        arrhenius_contributions = [0.0] * len(temperatures)
        gas_constant = 8.31446261815324
        for index, temperature in enumerate(temperatures):
            kelvin = temperature + 273.15
            rate = geometry["arrheniusA"] * math.exp(
                -geometry["activationEnergyJMol"] / (gas_constant * kelvin)
            )
            derivative = rate * geometry["activationEnergyJMol"] / (gas_constant * kelvin * kelvin)
            arrhenius_rate += rate * areas[index]
            arrhenius_contributions[index] = derivative * uncertainties[index] * areas[index]
        arrhenius_sigma = _spatial_sigma(
            list(range(len(temperatures))),
            arrhenius_contributions,
            centres,
            geometry,
        )
        assert all(math.isfinite(value) and value > 0.0 for value in (arrhenius_rate, arrhenius_sigma))
        reports.append(
            {
                "frameId": frame_id,
                "cameraId": camera_id,
                "calibrationRevision": calibration["revision"],
                "geometryRevision": geometry["revision"],
                "capturedAt": captured_at,
                "sensorWidth": sensor_width,
                "sensorHeight": sensor_height,
                "width": width,
                "height": height,
                "repairedPixels": len(geometry["badPixels"]),
                "referenceQuadratic": _round(quadratic),
                "referenceLinear": _round(linear),
                "referenceOffsetC": _round(offset),
                "referenceWeightedRmseC": _round(weighted_rmse),
                "referenceReducedChiSquare": _round(reduced_chi_square),
                "projectedAreaMm2": _round(sum(areas)),
                "arrheniusRateMm2PerSecond": _round(arrhenius_rate),
                "arrheniusRateSigmaMm2PerSecond": _round(arrhenius_sigma),
                "meanUncertaintyC": _round(sum(uncertainties) / len(uncertainties)),
                "maxUncertaintyC": _round(max(uncertainties)),
                "minC": _round(min(temperatures)),
                "maxC": _round(maximum),
                "meanC": _round(mean),
                "stddevC": _round(math.sqrt(variance)),
                "p95C": _round(_p95(temperatures)),
                "thresholdC": _round(threshold),
                "hotspot": {
                    "x": hotspot_index % width,
                    "y": hotspot_index // width,
                    "temperatureC": _round(maximum),
                    "uncertaintyC": _round(uncertainties[hotspot_index]),
                },
                "hotRegion": region,
            }
        )
        internal.append(
            {
                "frameId": frame_id,
                "cameraId": camera_id,
                "capturedAt": captured_at,
                "instant": datetime.fromisoformat(captured_at.replace("Z", "+00:00")),
                "mean": mean,
                "maximum": maximum,
                "integrated": integrated,
                "loadSigma": load_sigma,
                "integratedForAudit": integrated or 0.0,
                "loadSigmaForAudit": load_sigma or 0.0,
                "lower95": lower95,
                "arrheniusRate": arrhenius_rate,
                "arrheniusSigma": arrhenius_sigma,
                "temporalCorrelationSeconds": geometry["temporalCorrelationSeconds"],
            }
        )

    hottest = min(internal, key=lambda row: (-row["maximum"], row["frameId"]))
    regions = [row for row in internal if row["lower95"] is not None]
    region_winner = min(
        regions,
        key=lambda row: (-row["lower95"], -row["integrated"], row["frameId"]),
    ) if regions else None
    rises: list[dict[str, Any]] = []
    accelerations: list[dict[str, Any]] = []
    doses: list[dict[str, Any]] = []
    for camera_id in sorted({row["cameraId"] for row in internal}):
        rows = sorted(
            [row for row in internal if row["cameraId"] == camera_id],
            key=lambda row: (row["instant"], row["frameId"]),
        )
        temporal_scale = rows[0]["temporalCorrelationSeconds"]
        assert math.isfinite(temporal_scale) and temporal_scale > 0.0
        assert all(row["temporalCorrelationSeconds"] == temporal_scale for row in rows)
        coefficients = [0.0] * len(rows)
        cumulative = 0.0
        for index, (earlier, later) in enumerate(pairwise(rows)):
            elapsed_seconds = (later["instant"] - earlier["instant"]).total_seconds()
            assert elapsed_seconds > 0.0
            elapsed_minutes = elapsed_seconds / 60.0
            earlier_load = earlier["integrated"] or 0.0
            later_load = later["integrated"] or 0.0
            earlier_sigma = earlier["loadSigma"] or 0.0
            later_sigma = later["loadSigma"] or 0.0
            temporal_rho = math.exp(-elapsed_seconds / temporal_scale)
            difference_variance = (
                earlier_sigma**2
                + later_sigma**2
                - 2.0 * earlier_sigma * later_sigma * temporal_rho
            )
            assert math.isfinite(difference_variance) and difference_variance >= -1e-9
            rate = (later_load - earlier_load) / elapsed_minutes
            rate_sigma = math.sqrt(max(0.0, difference_variance)) / elapsed_minutes
            lower_rate = rate - 1.96 * rate_sigma
            if lower_rate > 0.0:
                rises.append(
                    {
                        "cameraId": camera_id,
                        "fromFrameId": earlier["frameId"],
                        "toFrameId": later["frameId"],
                        "rate": rate,
                        "sigma": rate_sigma,
                        "lower95": lower_rate,
                    }
                )
            cumulative += 0.5 * (earlier["arrheniusRate"] + later["arrheniusRate"]) * elapsed_seconds
            coefficients[index] += 0.5 * elapsed_seconds
            coefficients[index + 1] += 0.5 * elapsed_seconds
        if len(rows) >= 2:
            acceleration = _gls_arrhenius_acceleration(rows)
            if acceleration["lower95"] > 0.0:
                accelerations.append(acceleration)
            temporal_covariance = _temporal_covariance(rows, "arrheniusSigma")
            dose_variance = sum(
                coefficients[i] * temporal_covariance[i][j] * coefficients[j]
                for i in range(len(rows))
                for j in range(len(rows))
            )
            assert math.isfinite(dose_variance) and dose_variance > 0.0
            dose_sigma = math.sqrt(dose_variance)
            doses.append(
                {
                    "cameraId": camera_id,
                    "dose": cumulative,
                    "sigma": dose_sigma,
                    "lower95": cumulative - 1.96 * dose_sigma,
                }
            )
    fastest = min(
        rises,
        key=lambda row: (
            -row["lower95"],
            -row["rate"],
            row["cameraId"],
            row["fromFrameId"],
            row["toFrameId"],
        ),
    ) if rises else None
    steepest = min(
        accelerations,
        key=lambda row: (
            -row["lower95"],
            -row["acceleration"],
            row["cameraId"],
            row["fromFrameId"],
            row["toFrameId"],
        ),
    ) if accelerations else None
    largest_dose = min(
        doses,
        key=lambda row: (-row["lower95"], -row["dose"], row["cameraId"]),
    ) if doses else None
    return {
        "frames": reports,
        "summary": {
            "frameCount": len(reports),
            "hottestFrameId": hottest["frameId"],
            "globalMaxC": _round(hottest["maximum"]),
            "meanFrameMeanC": _round(sum(row["mean"] for row in internal) / len(internal)),
            "largestConservativeRegionFrameId": region_winner["frameId"] if region_winner else None,
            "largestLower95IntegratedExcessCmm2": _round(region_winner["lower95"]) if region_winner else None,
            "fastestSignificantThermalLoadRise": (
                {
                    "cameraId": fastest["cameraId"],
                    "fromFrameId": fastest["fromFrameId"],
                    "toFrameId": fastest["toFrameId"],
                    "rateCmm2PerMinute": _round(fastest["rate"]),
                    "sigmaCmm2PerMinute": _round(fastest["sigma"]),
                    "lower95Cmm2PerMinute": _round(fastest["lower95"]),
                }
                if fastest else None
            ),
            "steepestSignificantArrheniusAcceleration": (
                {
                    "cameraId": steepest["cameraId"],
                    "fromFrameId": steepest["fromFrameId"],
                    "toFrameId": steepest["toFrameId"],
                    "observationCount": steepest["observationCount"],
                    "accelerationMm2PerSecondPerMinute": _round(steepest["acceleration"]),
                    "sigmaMm2PerSecondPerMinute": _round(steepest["sigma"]),
                    "lower95Mm2PerSecondPerMinute": _round(steepest["lower95"]),
                }
                if steepest else None
            ),
            "largestConservativeArrheniusDose": (
                {
                    "cameraId": largest_dose["cameraId"],
                    "doseMm2": _round(largest_dose["dose"]),
                    "sigmaMm2": _round(largest_dose["sigma"]),
                    "lower95Mm2": _round(largest_dose["lower95"]),
                }
                if largest_dose else None
            ),
            "evidenceSha256": _evidence_digest(internal),
            "dominantBivariateThermalEpisode": _dominant_bivariate_episode(
                internal, database
            ),
        },
    }


def _seed_references(
    connection: sqlite3.Connection,
    frame_id: str,
    raw: list[int],
    width: int,
    height: int,
    calibration: dict[str, Any],
    geometry: dict[str, Any],
    quadratic: float,
    linear: float,
    offset: float,
) -> None:
    repaired = _repair(raw, width, height, geometry["badPixels"])
    preliminary = [_temperature(value, calibration) for value in repaired]
    usable = sorted(
        (index for index in range(len(raw)) if index not in geometry["badPixels"]),
        key=lambda index: preliminary[index],
    )
    anchors = (0, len(usable) // 4, len(usable) // 2, 3 * len(usable) // 4, len(usable) - 2)
    groups = [
        [usable[min(anchor, len(usable) - 2)], usable[min(anchor, len(usable) - 2) + 1]]
        for anchor in anchors
    ]
    noises = (-0.02, 0.015, -0.01, 0.018, -0.012)
    sigmas = (0.20, 0.32, 0.48, 0.70, 0.95)
    for number, (indices, noise, sigma) in enumerate(
        zip(groups, noises, sigmas, strict=True),
        start=1,
    ):
        measured = _median([preliminary[index] for index in indices])
        expected = quadratic * measured * measured + linear * measured + offset + noise
        for index in indices:
            connection.execute(
                "INSERT INTO reference_samples("
                "frame_id,reference_id,pixel_index,expected_c,sigma_c"
                ") VALUES (?,?,?,?,?)",
                (frame_id, f"ref-{number}", index, expected, sigma),
            )

def _heldout_profiles(destination: Path) -> dict[str, Any]:
    document = json.loads(BASE_PROFILES.read_text())
    for index, row in enumerate(document["calibrations"]):
        row["revision"] = f"heldout-cal-{index}"
        row["gain"] *= 1.06
        row["offsetC"] -= 3.75
        row["quadratic"] *= 0.86
        row["ambientCoupling"] += 0.008
        row["emissivity"] -= 0.025
    geometry_by_camera = {row["cameraId"]: row for row in document["geometries"]}
    geometry_by_camera["north-cam"].update(
        {
            "revision": "heldout-geom-n",
            "rotation": 270,
            "mirrorX": True,
            "badPixels": [9, 10],
            "hotSigma": 1.25,
            "minHotArea": 2,
            "homography": [8.8, 0.7, 130.0, -0.35, 9.4, 65.0, 0.0008, -0.0005, 1.0],
            "arrheniusA": 175.0,
            "activationEnergyJMol": 62500.0,
            "detectorNoiseC": 0.58,
            "confidenceK": 2.15,
            "correlationMajorMm": 31.0,
            "correlationMinorMm": 4.5,
            "correlationAngleDeg": 118.0,
            "temporalCorrelationSeconds": 210.0,
        }
    )
    geometry_by_camera["south-cam"].update(
        {
            "revision": "heldout-geom-s",
            "rotation": 90,
            "mirrorX": False,
            "badPixels": [7, 8],
            "hotSigma": 1.4,
            "minHotArea": 1,
            "homography": [13.1, -0.2, 45.0, 0.4, 10.7, 72.0, -0.0006, 0.0004, 1.0],
            "arrheniusA": 5000.0,
            "activationEnergyJMol": 35000.0,
            "detectorNoiseC": 0.44,
            "confidenceK": 1.72,
            "correlationMajorMm": 9.0,
            "correlationMinorMm": 2.8,
            "correlationAngleDeg": -12.0,
            "temporalCorrelationSeconds": 72.0,
        }
    )
    destination.write_text(json.dumps(document))
    return document

def _replace_with_heldout_frames(database: Path, profile_document: dict[str, Any]) -> None:
    fixtures = [
        ("north-early", "north-cam", "2026-05-01T10:00:00Z", 5000, [[5000, 5000, 5000, 5001, 5002, 5003, 5100, 90000], [5050, 5100, 5150, 5200, 5250, 5300, 5350, 5400], [5030, 5029, 5028, 5028, 5028, 5040, 5035, 5030]]),
        ("south-early", "south-cam", "2026-05-01T10:01:00Z", 6100, [[6105, 6110, 6115, 6120, 6125, 6130], [6100, 6100, 6100, 6150, 6200, 6250], [6400, 6420, 6440, 6460, 6480, 6500], [6200, 6210, 6999, 6999, 6210, 6200]]),
        ("north-middle", "north-cam", "2026-05-01T10:02:15Z", 5150, [[5150, 5150, 5160, 5170, 5180, 5190, 5200, 5210], [5200, 5250, 5300, 5350, 5400, 5450, 5500, 5550], [5250, 5300, 5350, 7000, 7100, 7200, 5400, 5350]]),
        ("north-late", "north-cam", "2026-05-01T10:04:30Z", 5200, [[5200, 5200, 5200, 5210, 5220, 5230, 5240, 5250], [5250, 5300, 5350, 5400, 5450, 5500, 5550, 5600], [5300, 5350, 5400, 7800, 7850, 7900, 5450, 5400]]),
        ("south-late", "south-cam", "2026-05-01T10:06:00Z", 6200, [[6200, 6210, 6220, 6230, 6240, 6250], [6250, 6300, 6350, 6400, 6450, 6500], [6500, 6550, 6600, 6650, 6700, 6750], [6300, 6350, 7200, 7250, 6400, 6350]]),
    ]
    calibrations = {row["cameraId"]: row for row in profile_document["calibrations"]}
    geometries = {row["cameraId"]: row for row in profile_document["geometries"]}
    connection = sqlite3.connect(database)
    connection.execute("DELETE FROM frame_checkpoints")
    connection.execute("DELETE FROM reference_samples")
    connection.execute("DELETE FROM frames")
    for number, (frame_id, camera_id, captured_at, base, rows) in enumerate(fixtures):
        blob = _encode_qir(rows, base)
        flattened = [value for row in rows for value in row]
        connection.execute(
            "INSERT INTO frames(frame_id,camera_id,captured_at,width,height,qir_blob) VALUES (?,?,?,?,?,?)",
            (frame_id, camera_id, captured_at, len(rows[0]), len(rows), blob),
        )
        for index in (0, len(flattened) // 2, len(flattened) - 1):
            connection.execute(
                "INSERT INTO frame_checkpoints(frame_id,pixel_index,raw_count) VALUES (?,?,?)",
                (frame_id, index, flattened[index]),
            )
        _seed_references(
            connection,
            frame_id,
            flattened,
            len(rows[0]),
            len(rows),
            calibrations[camera_id],
            geometries[camera_id],
            quadratic=0.00008 + number * 0.000015,
            linear=0.95 + number * 0.012,
            offset=3.6 - number * 0.7,
        )
    connection.commit()
    connection.close()


def _replace_with_temporal_gls_frames(
    database: Path,
    profile_document: dict[str, Any],
) -> None:
    fixtures = [
        (
            "gls-north-1",
            "2026-06-01T10:00:00Z",
            5000,
            [
                [5000, 5010, 5020, 5030, 5040, 5050],
                [5060, 5070, 5080, 5090, 5100, 5110],
                [5120, 5130, 5140, 5300, 5350, 5400],
                [5150, 5160, 5170, 5180, 5190, 5200],
            ],
        ),
        (
            "gls-north-2",
            "2026-06-01T10:01:30Z",
            5050,
            [
                [5050, 5060, 5070, 5080, 5090, 5100],
                [5110, 5120, 5130, 5140, 5150, 5160],
                [5170, 5180, 5190, 6000, 6100, 6200],
                [5200, 5210, 5220, 5230, 5240, 5250],
            ],
        ),
        (
            "gls-north-3",
            "2026-06-01T10:05:00Z",
            5100,
            [
                [5100, 5110, 5120, 5130, 5140, 5150],
                [5160, 5170, 5180, 5190, 5200, 5210],
                [5220, 5230, 5240, 6900, 7100, 7300],
                [5250, 5260, 5270, 5280, 5290, 5300],
            ],
        ),
    ]
    calibrations = {row["cameraId"]: row for row in profile_document["calibrations"]}
    geometries = {row["cameraId"]: row for row in profile_document["geometries"]}
    calibration = calibrations["north-cam"]
    geometry = geometries["north-cam"]
    connection = sqlite3.connect(database)
    connection.execute("DELETE FROM frame_checkpoints")
    connection.execute("DELETE FROM reference_samples")
    connection.execute("DELETE FROM frames")
    for number, (frame_id, captured_at, base, rows) in enumerate(fixtures):
        blob = _encode_qir(rows, base)
        flattened = [value for row in rows for value in row]
        connection.execute(
            "INSERT INTO frames(frame_id,camera_id,captured_at,width,height,qir_blob) "
            "VALUES (?,?,?,?,?,?)",
            (frame_id, "north-cam", captured_at, len(rows[0]), len(rows), blob),
        )
        for index in (0, len(flattened) // 2, len(flattened) - 1):
            connection.execute(
                "INSERT INTO frame_checkpoints(frame_id,pixel_index,raw_count) VALUES (?,?,?)",
                (frame_id, index, flattened[index]),
            )
        _seed_references(
            connection,
            frame_id,
            flattened,
            len(rows[0]),
            len(rows),
            calibration,
            geometry,
            quadratic=0.00007 + number * 0.00001,
            linear=0.97 + number * 0.008,
            offset=2.8 - number * 0.3,
        )
    connection.commit()
    connection.close()


def _replace_with_episode_frames(
    database: Path,
    profile_document: dict[str, Any],
) -> None:
    fixtures = [
        (
            "episode-north-1",
            "2026-07-01T10:00:00Z",
            5000,
            [
                [5000, 5010, 5020, 5030, 5040, 5050],
                [5060, 5070, 5080, 5090, 5100, 5110],
                [5120, 5130, 5140, 5250, 5300, 5350],
                [5150, 5160, 5170, 5180, 5190, 5200],
            ],
        ),
        (
            "episode-north-2",
            "2026-07-01T10:01:10Z",
            5050,
            [
                [5050, 5060, 5070, 5080, 5090, 5100],
                [5110, 5120, 5130, 5140, 5150, 5160],
                [5170, 5180, 5190, 5450, 5520, 5590],
                [5200, 5210, 5220, 5230, 5240, 5250],
            ],
        ),
        (
            "episode-north-3",
            "2026-07-01T10:02:55Z",
            5100,
            [
                [5100, 5110, 5120, 5130, 5140, 5150],
                [5160, 5170, 5180, 5190, 5200, 5210],
                [5220, 5230, 5240, 5700, 5800, 5900],
                [5250, 5260, 5270, 5280, 5290, 5300],
            ],
        ),
        (
            "episode-north-4",
            "2026-07-01T10:05:20Z",
            6200,
            [
                [6200, 6210, 6220, 6230, 6240, 6250],
                [6260, 6270, 6280, 6290, 6300, 6310],
                [6320, 6330, 6340, 7600, 7800, 8000],
                [6350, 6360, 6370, 6380, 6390, 6400],
            ],
        ),
        (
            "episode-north-5",
            "2026-07-01T10:09:00Z",
            5200,
            [
                [5200, 5210, 5220, 5230, 5240, 5250],
                [5260, 5270, 5280, 5290, 5300, 5310],
                [5320, 5330, 5340, 5750, 5850, 5950],
                [5350, 5360, 5370, 5380, 5390, 5400],
            ],
        ),
    ]
    calibration = next(
        row for row in profile_document["calibrations"]
        if row["cameraId"] == "north-cam"
    )
    geometry = next(
        row for row in profile_document["geometries"]
        if row["cameraId"] == "north-cam"
    )
    connection = sqlite3.connect(database)
    connection.execute("DELETE FROM frame_checkpoints")
    connection.execute("DELETE FROM reference_samples")
    connection.execute("DELETE FROM frames")
    connection.execute(
        "UPDATE episode_profiles SET min_frames=2,max_gap_seconds=600,"
        "cross_metric_correlation=0.28,load_sigma_floor_cmm2=9,min_glr=0.1 "
        "WHERE camera_id='north-cam'"
    )
    for number, (frame_id, captured_at, base, rows) in enumerate(fixtures):
        blob = _encode_qir_indexed(rows, base) if number % 2 else _encode_qir(rows, base)
        flattened = [value for row in rows for value in row]
        connection.execute(
            "INSERT INTO frames(frame_id,camera_id,captured_at,width,height,qir_blob) "
            "VALUES (?,?,?,?,?,?)",
            (frame_id, "north-cam", captured_at, len(rows[0]), len(rows), blob),
        )
        for index in (0, len(flattened) // 2, len(flattened) - 1):
            connection.execute(
                "INSERT INTO frame_checkpoints(frame_id,pixel_index,raw_count) VALUES (?,?,?)",
                (frame_id, index, flattened[index]),
            )
        _seed_references(
            connection,
            frame_id,
            flattened,
            len(rows[0]),
            len(rows),
            calibration,
            geometry,
            quadratic=0.000075,
            linear=0.975,
            offset=2.5,
        )
    connection.commit()
    connection.close()


def _run(database: Path, api: str, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(ANALYZER), "--db", str(database), "--api", api, "--output", str(output)],
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )


@pytest.fixture(scope="session", autouse=True)
def _compile_analyzer() -> None:
    """Compile the submitted Kotlin source before behavioral tests run."""
    subprocess.run([str(REBUILD)], timeout=90, check=True)


def test_visible_archive_matches_robust_uncertainty_contract(tmp_path: Path) -> None:
    """Verify the complete archive against the robust uncertainty contract.

    Compare the full JSON object with the independent Python scientific oracle.
    """
    output = tmp_path / "report.json"
    before = BASE_DB.read_bytes()
    with _spring_api(BASE_DB, BASE_PROFILES) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == _expected(BASE_DB, BASE_PROFILES)
    assert BASE_DB.read_bytes() == before


def test_heldout_frames_change_irls_covariance_and_confidence_trends(tmp_path: Path) -> None:
    """Verify held-out frames change IRLS, covariance, and confidence trends.

    Recompute the expected JSON after database and runtime-profile mutations.
    """
    database = tmp_path / "heldout.sqlite"
    shutil.copy2(BASE_DB, database)
    profiles = tmp_path / "profiles.json"
    profile_document = _heldout_profiles(profiles)
    _replace_with_heldout_frames(database, profile_document)
    output = tmp_path / "heldout.json"
    with _spring_api(database, profiles) as api:
        result = _run(database, api, output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == _expected(database, profiles)


def test_runtime_reference_targets_change_quadratic_fit_and_physics(tmp_path: Path) -> None:
    """Verify reference targets change the fit and downstream physics.

    Confirm affected numerical fields match an independent expectation.
    """
    database = tmp_path / "references.sqlite"
    shutil.copy2(BASE_DB, database)
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE reference_samples SET expected_c = expected_c * 1.035 + 1.7 "
        "WHERE frame_id IN ('kiln-a-001','kiln-c-204')"
    )
    connection.commit()
    connection.close()
    output = tmp_path / "references.json"
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == _expected(database, BASE_PROFILES)


def test_inconsistent_reference_target_fails_without_replacing_output(tmp_path: Path) -> None:
    """Reject inconsistent targets within one blackbody reference.

    Confirm a nonzero exit and preservation of the previous output.
    """
    database = tmp_path / "inconsistent.sqlite"
    shutil.copy2(BASE_DB, database)
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE reference_samples SET expected_c = expected_c + 0.5 "
        "WHERE rowid = (SELECT rowid FROM reference_samples LIMIT 1)"
    )
    connection.commit()
    connection.close()
    output = tmp_path / "sentinel.json"
    output.write_text("keep-reference")
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-reference"


def test_degenerate_reference_fit_fails_atomically(tmp_path: Path) -> None:
    """Reject a degenerate robust quadratic fit.

    Confirm the analyzer fails without publishing a partial replacement.
    """
    database = tmp_path / "degenerate.sqlite"
    shutil.copy2(BASE_DB, database)
    connection = sqlite3.connect(database)
    frame_id = connection.execute("SELECT frame_id FROM frames ORDER BY frame_id LIMIT 1").fetchone()[0]
    connection.execute("DELETE FROM reference_samples WHERE frame_id=?", (frame_id,))
    for reference_id, expected in (("a", 100.0), ("b", 110.0), ("c", 120.0), ("d", 130.0)):
        for pixel_index in (0, 1):
            connection.execute(
                "INSERT INTO reference_samples("
                "frame_id,reference_id,pixel_index,expected_c,sigma_c"
                ") VALUES (?,?,?,?,?)",
                (frame_id, reference_id, pixel_index, expected, 0.4),
            )
    connection.commit()
    connection.close()
    output = tmp_path / "sentinel.json"
    output.write_text("keep-degenerate")
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-degenerate"


def test_checkpoint_disagreement_fails_without_replacing_output(tmp_path: Path) -> None:
    """Reject a PLC checkpoint that disagrees with decoded detector data.

    Confirm a nonzero exit and preservation of the existing report.
    """
    database = tmp_path / "checkpoint.sqlite"
    shutil.copy2(BASE_DB, database)
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE frame_checkpoints SET raw_count=raw_count+1 "
        "WHERE rowid=(SELECT rowid FROM frame_checkpoints LIMIT 1)"
    )
    connection.commit()
    connection.close()
    output = tmp_path / "sentinel.json"
    output.write_text("keep-checkpoint")
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-checkpoint"


def test_invalid_hot_region_profile_fails_without_replacing_output(tmp_path: Path) -> None:
    """Reject invalid hot-region runtime parameters.

    Confirm profile validation occurs before atomic output replacement.
    """
    document = json.loads(BASE_PROFILES.read_text())
    document["geometries"][0]["hotSigma"] = 0.0
    profiles = tmp_path / "invalid-hot.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "sentinel.json"
    output.write_text("keep-hot")
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-hot"


def test_corrupt_payload_checksum_fails_without_partial_publish(tmp_path: Path) -> None:
    """Reject a QIR2 payload whose decoded counts fail CRC validation.

    Confirm no partial JSON is published.
    """
    database = tmp_path / "corrupt.sqlite"
    shutil.copy2(BASE_DB, database)
    connection = sqlite3.connect(database)
    frame_id, blob = connection.execute(
        "SELECT frame_id,qir_blob FROM frames ORDER BY frame_id LIMIT 1"
    ).fetchone()
    damaged = bytearray(blob)
    damaged[20] ^= 0x01
    connection.execute("UPDATE frames SET qir_blob=? WHERE frame_id=?", (bytes(damaged), frame_id))
    connection.commit()
    connection.close()
    output = tmp_path / "sentinel.json"
    output.write_text("keep-crc")
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-crc"

def test_reference_uncertainty_changes_weighted_solution(tmp_path: Path) -> None:
    """Verify reference uncertainty changes the weighted robust solution.

    Compare the entire report with the independently recomputed expectation.
    """
    database = tmp_path / "uncertainty.sqlite"
    shutil.copy2(BASE_DB, database)
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE reference_samples SET sigma_c = "
        "CASE reference_id WHEN 'cold' THEN 1.4 WHEN 'warm' THEN 0.15 "
        "WHEN 'mid' THEN 0.8 ELSE 0.25 END "
        "WHERE frame_id IN ('kiln-a-001','kiln-c-204')"
    )
    connection.commit()
    connection.close()
    output = tmp_path / "uncertainty.json"
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == _expected(database, BASE_PROFILES)




def test_reference_outlier_is_robustly_downweighted(tmp_path: Path) -> None:
    """Verify a valid reference outlier is downweighted by Huber IRLS.

    Check the robust-fit, covariance, and downstream report values.
    """
    database = tmp_path / "robust-outlier.sqlite"
    shutil.copy2(BASE_DB, database)
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE reference_samples SET expected_c = expected_c + 7.5, sigma_c = 0.35 "
        "WHERE frame_id = 'kiln-c-204' AND reference_id = 'ref-3'"
    )
    connection.commit()
    connection.close()
    output = tmp_path / "robust-outlier.json"
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == _expected(database, BASE_PROFILES)

def test_inconsistent_reference_uncertainty_fails_atomically(tmp_path: Path) -> None:
    """Reject inconsistent sigma values within one blackbody reference.

    Confirm failure is atomic and the prior output remains unchanged.
    """
    database = tmp_path / "bad-sigma.sqlite"
    shutil.copy2(BASE_DB, database)
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE reference_samples SET sigma_c = sigma_c * 2 "
        "WHERE rowid = (SELECT rowid FROM reference_samples LIMIT 1)"
    )
    connection.commit()
    connection.close()
    output = tmp_path / "sentinel.json"
    output.write_text("keep-sigma")
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-sigma"


def test_singular_projective_mapping_fails_without_replacing_output(tmp_path: Path) -> None:
    """Reject a singular projective mapping.

    Confirm invalid mapped geometry cannot replace an existing report.
    """
    document = json.loads(BASE_PROFILES.read_text())
    document["geometries"][0]["homography"] = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    profiles = tmp_path / "singular-homography.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "sentinel.json"
    output.write_text("keep-homography")
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-homography"


def test_runtime_homography_changes_area_weighted_loads(tmp_path: Path) -> None:
    """Verify runtime homography changes projected areas and weighted loads.

    Compare full JSON against the independent projective-geometry oracle.
    """
    document = json.loads(BASE_PROFILES.read_text())
    document["geometries"][0]["homography"] = [
        15.0, 0.9, 140.0,
        -0.6, 7.8, 30.0,
        0.0012, -0.0009, 1.0,
    ]
    profiles = tmp_path / "warped.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "warped-report.json"
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == _expected(BASE_DB, profiles)




def test_runtime_noise_and_confidence_change_conservative_regions(tmp_path: Path) -> None:
    """Verify noise and confidence factors change conservative results.

    Recompute all uncertainty-qualified outputs independently.
    """
    document = json.loads(BASE_PROFILES.read_text())
    document["geometries"][0]["detectorNoiseC"] *= 2.4
    document["geometries"][0]["confidenceK"] = 2.75
    profiles = tmp_path / "uncertainty-profile.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "uncertainty-report.json"
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == _expected(BASE_DB, profiles)


def test_runtime_anisotropic_correlation_changes_uncertainty_outputs(tmp_path: Path) -> None:
    """Verify anisotropic projected-space correlation changes propagated uncertainty.

    Compare the full report with the independent pairwise-covariance oracle.
    """
    document = json.loads(BASE_PROFILES.read_text())
    document["geometries"][0]["correlationMajorMm"] = 42.0
    document["geometries"][0]["correlationMinorMm"] = 3.2
    document["geometries"][0]["correlationAngleDeg"] = 73.0
    profiles = tmp_path / "anisotropic-correlation.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "anisotropic-report.json"
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == _expected(BASE_DB, profiles)


def test_correlation_angle_uses_projected_furnace_axes(tmp_path: Path) -> None:
    """Verify the covariance kernel rotates in projected millimetre coordinates.

    Compare the exact JSON after changing only the anisotropy angle.
    """
    document = json.loads(BASE_PROFILES.read_text())
    geometry = document["geometries"][1]
    geometry["correlationMajorMm"] = 36.0
    geometry["correlationMinorMm"] = 2.5
    geometry["correlationAngleDeg"] += 90.0
    profiles = tmp_path / "rotated-correlation.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "rotated-correlation-report.json"
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == _expected(BASE_DB, profiles)


def test_invalid_spatial_correlation_fails_atomically(tmp_path: Path) -> None:
    """Reject a nonphysical spatial-correlation length.

    Confirm validation fails without replacing the existing report.
    """
    document = json.loads(BASE_PROFILES.read_text())
    document["geometries"][0]["correlationMinorMm"] = 0.0
    profiles = tmp_path / "invalid-correlation.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "sentinel.json"
    output.write_text("keep-correlation")
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-correlation"



def test_irregular_three_frame_gls_uses_full_temporal_covariance(tmp_path: Path) -> None:
    """Verify dense GLS over all irregularly timed camera frames.

    Compare the full report with the independent temporal-covariance oracle and
    reject an endpoint-slope shortcut through the three-observation result.
    """
    database = tmp_path / "temporal-gls.sqlite"
    shutil.copy2(BASE_DB, database)
    document = json.loads(BASE_PROFILES.read_text())
    geometry = next(row for row in document["geometries"] if row["cameraId"] == "north-cam")
    geometry["arrheniusA"] = 5000.0
    geometry["activationEnergyJMol"] = 35000.0
    geometry["temporalCorrelationSeconds"] = 180.0
    profiles = tmp_path / "temporal-gls.json"
    profiles.write_text(json.dumps(document))
    _replace_with_temporal_gls_frames(database, document)
    expected = _expected(database, profiles)
    output = tmp_path / "temporal-gls-output.json"
    with _spring_api(database, profiles) as api:
        result = _run(database, api, output)
    assert result.returncode == 0, result.stderr
    actual = json.loads(output.read_text())
    assert actual == expected
    acceleration = actual["summary"]["steepestSignificantArrheniusAcceleration"]
    assert acceleration["observationCount"] == 3
    rates = [frame["arrheniusRateMm2PerSecond"] for frame in actual["frames"]]
    endpoint_slope = (rates[-1] - rates[0]) / 5.0
    assert abs(acceleration["accelerationMm2PerSecondPerMinute"] - endpoint_slope) > 0.01


def test_runtime_temporal_correlation_changes_gls_and_dose(tmp_path: Path) -> None:
    """Verify runtime temporal length changes both cross-frame uncertainties.

    Compare two full reports against the oracle and require changed GLS and dose
    sigma values without changing the underlying SQLite archive.
    """
    database = tmp_path / "temporal-change.sqlite"
    shutil.copy2(BASE_DB, database)
    document = json.loads(BASE_PROFILES.read_text())
    geometry = next(row for row in document["geometries"] if row["cameraId"] == "north-cam")
    geometry["arrheniusA"] = 5000.0
    geometry["activationEnergyJMol"] = 35000.0
    geometry["temporalCorrelationSeconds"] = 180.0
    _replace_with_temporal_gls_frames(database, document)

    slow_profiles = tmp_path / "temporal-slow.json"
    slow_profiles.write_text(json.dumps(document))
    slow_expected = _expected(database, slow_profiles)
    slow_output = tmp_path / "temporal-slow-output.json"
    with _spring_api(database, slow_profiles) as api:
        slow_result = _run(database, api, slow_output)
    assert slow_result.returncode == 0, slow_result.stderr
    slow_actual = json.loads(slow_output.read_text())
    assert slow_actual == slow_expected

    geometry["temporalCorrelationSeconds"] = 12.0
    fast_profiles = tmp_path / "temporal-fast.json"
    fast_profiles.write_text(json.dumps(document))
    fast_expected = _expected(database, fast_profiles)
    fast_output = tmp_path / "temporal-fast-output.json"
    with _spring_api(database, fast_profiles) as api:
        fast_result = _run(database, api, fast_output)
    assert fast_result.returncode == 0, fast_result.stderr
    fast_actual = json.loads(fast_output.read_text())
    assert fast_actual == fast_expected

    slow_acceleration = slow_actual["summary"]["steepestSignificantArrheniusAcceleration"]
    fast_acceleration = fast_actual["summary"]["steepestSignificantArrheniusAcceleration"]
    assert slow_acceleration["sigmaMm2PerSecondPerMinute"] != fast_acceleration["sigmaMm2PerSecondPerMinute"]
    assert slow_actual["summary"]["largestConservativeArrheniusDose"]["sigmaMm2"] != fast_actual["summary"]["largestConservativeArrheniusDose"]["sigmaMm2"]


def test_invalid_temporal_correlation_fails_atomically(tmp_path: Path) -> None:
    """Reject a nonphysical cross-frame correlation length.

    Confirm temporal-profile validation fails before replacing an existing report.
    """
    document = json.loads(BASE_PROFILES.read_text())
    document["geometries"][0]["temporalCorrelationSeconds"] = 0.0
    profiles = tmp_path / "invalid-temporal.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "sentinel.json"
    output.write_text("keep-temporal")
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-temporal"

def test_invalid_uncertainty_profile_fails_without_replacing_output(tmp_path: Path) -> None:
    """Reject a nonphysical detector-noise profile.

    Confirm uncertainty validation fails before publication.
    """
    document = json.loads(BASE_PROFILES.read_text())
    document["geometries"][0]["detectorNoiseC"] = 0.0
    profiles = tmp_path / "invalid-uncertainty.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "sentinel.json"
    output.write_text("keep-uncertainty")
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-uncertainty"



def test_invalid_confidence_factor_fails_atomically(tmp_path: Path) -> None:
    """Reject an invalid confidence factor.

    Confirm a nonzero exit without altering the previous output.
    """
    document = json.loads(BASE_PROFILES.read_text())
    document["geometries"][0]["confidenceK"] = 0.0
    profiles = tmp_path / "invalid-confidence.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "sentinel.json"
    output.write_text("keep-confidence")
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-confidence"

def test_invalid_arrhenius_profile_fails_without_replacing_output(tmp_path: Path) -> None:
    """Reject nonphysical Arrhenius coefficients.

    Confirm kinetics validation is atomic and preserves the prior report.
    """
    document = json.loads(BASE_PROFILES.read_text())
    document["geometries"][0]["activationEnergyJMol"] = 0.0
    profiles = tmp_path / "invalid-kinetics.json"
    profiles.write_text(json.dumps(document))
    output = tmp_path / "sentinel.json"
    output.write_text("keep-kinetics")
    with _spring_api(BASE_DB, profiles) as api:
        result = _run(BASE_DB, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-kinetics"




def test_indexed_qir_directory_and_extended_opcodes_match_full_report(tmp_path: Path) -> None:
    """Verify indexed rows, chained CRCs, delta blocks, and accelerated ramps.

    Re-encode every frame without changing counts and compare the full JSON with
    the independent oracle after decoding the indexed representation.
    """
    database = tmp_path / "indexed.sqlite"
    shutil.copy2(BASE_DB, database)
    _rewrite_frames_as_indexed(database)
    output = tmp_path / "indexed-report.json"
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text()) == _expected(database, BASE_PROFILES)


def test_indexed_qir_chained_row_crc_fails_atomically(tmp_path: Path) -> None:
    """Reject an indexed packet whose chained row checksum is incorrect.

    Corrupt only a row descriptor CRC and preserve the previous output file.
    """
    database = tmp_path / "indexed-crc.sqlite"
    shutil.copy2(BASE_DB, database)
    _rewrite_frames_as_indexed(database)
    connection = sqlite3.connect(database)
    frame_id, blob = connection.execute(
        "SELECT frame_id,qir_blob FROM frames ORDER BY frame_id LIMIT 1"
    ).fetchone()
    damaged = bytearray(blob)
    row_crc_offset = 24 + 8
    current = struct.unpack_from("<I", damaged, row_crc_offset)[0]
    struct.pack_into("<I", damaged, row_crc_offset, current ^ 0x01020304)
    connection.execute("UPDATE frames SET qir_blob=? WHERE frame_id=?", (bytes(damaged), frame_id))
    connection.commit()
    connection.close()
    output = tmp_path / "sentinel.json"
    output.write_text("keep-indexed-crc")
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-indexed-crc"


def test_indexed_qir_overlapping_directory_fails_atomically(tmp_path: Path) -> None:
    """Reject overlapping indexed-row stream descriptors.

    Change the second row offset while leaving packet data and global CRC intact.
    """
    database = tmp_path / "indexed-overlap.sqlite"
    shutil.copy2(BASE_DB, database)
    _rewrite_frames_as_indexed(database)
    connection = sqlite3.connect(database)
    frame_id, blob = connection.execute(
        "SELECT frame_id,qir_blob FROM frames WHERE height>1 ORDER BY frame_id LIMIT 1"
    ).fetchone()
    damaged = bytearray(blob)
    struct.pack_into("<I", damaged, 24 + 12, 0)
    connection.execute("UPDATE frames SET qir_blob=? WHERE frame_id=?", (bytes(damaged), frame_id))
    connection.commit()
    connection.close()
    output = tmp_path / "sentinel.json"
    output.write_text("keep-indexed-directory")
    with _spring_api(database, BASE_PROFILES) as api:
        result = _run(database, api, output)
    assert result.returncode != 0
    assert output.read_text() == "keep-indexed-directory"


def test_go_auditor_detects_bivariate_irregular_episode(tmp_path: Path) -> None:
    """Build five irregular frames and compare the complete Go GLS episode against the independent oracle."""
    database = tmp_path / "episode.sqlite"
    profiles = tmp_path / "profiles.json"
    shutil.copy2(BASE_DB, database)
    document = json.loads(BASE_PROFILES.read_text())
    profiles.write_text(json.dumps(document))
    _replace_with_episode_frames(database, document)
    output = tmp_path / "report.json"
    with _spring_api(database, profiles) as api:
        result = _run(database, api, output)
    assert result.returncode == 0, result.stderr
    actual = json.loads(output.read_text())
    expected = _expected(database, profiles)
    assert actual == expected
    episode = actual["summary"]["dominantBivariateThermalEpisode"]
    assert episode is not None
    assert episode["observationCount"] >= 2
    assert episode["generalizedLikelihoodRatio"] > 0.0


def test_episode_cross_metric_correlation_changes_gls_selection(tmp_path: Path) -> None:
    """Mutate only the SQL cross-channel correlation and compare both final reports with independent GLS calculations."""
    database = tmp_path / "episode.sqlite"
    profiles = tmp_path / "profiles.json"
    shutil.copy2(BASE_DB, database)
    document = json.loads(BASE_PROFILES.read_text())
    profiles.write_text(json.dumps(document))
    _replace_with_episode_frames(database, document)
    first_output = tmp_path / "first.json"
    with _spring_api(database, profiles) as api:
        first_result = _run(database, api, first_output)
    assert first_result.returncode == 0, first_result.stderr
    first = json.loads(first_output.read_text())
    first_expected = _expected(database, profiles)
    assert first == first_expected
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE episode_profiles SET cross_metric_correlation=-0.42 "
        "WHERE camera_id='north-cam'"
    )
    connection.commit()
    connection.close()
    second_output = tmp_path / "second.json"
    with _spring_api(database, profiles) as api:
        second_result = _run(database, api, second_output)
    assert second_result.returncode == 0, second_result.stderr
    second = json.loads(second_output.read_text())
    assert second == _expected(database, profiles)
    assert (
        first["summary"]["dominantBivariateThermalEpisode"]
        != second["summary"]["dominantBivariateThermalEpisode"]
    )
    assert first["summary"]["evidenceSha256"] == second["summary"]["evidenceSha256"]


def test_invalid_episode_profile_fails_without_replacing_output(tmp_path: Path) -> None:
    """Set a nonphysical SQL correlation and verify the Go finalizer fails before atomic publication."""
    database = tmp_path / "invalid-profile.sqlite"
    profiles = tmp_path / "profiles.json"
    shutil.copy2(BASE_DB, database)
    shutil.copy2(BASE_PROFILES, profiles)
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE episode_profiles SET cross_metric_correlation=1.0 "
        "WHERE camera_id='north-cam'"
    )
    connection.commit()
    connection.close()
    output = tmp_path / "report.json"
    output.write_text("preserve-this-report")
    with _spring_api(database, profiles) as api:
        result = _run(database, api, output)
    assert result.returncode != 0
    assert output.read_text() == "preserve-this-report"


def test_evidence_digest_changes_with_full_precision_handoff(tmp_path: Path) -> None:
    """Change runtime reference evidence and verify the final report hides `_audit` while its canonical digest changes."""
    database = tmp_path / "digest.sqlite"
    profiles = tmp_path / "profiles.json"
    shutil.copy2(BASE_DB, database)
    shutil.copy2(BASE_PROFILES, profiles)
    first_output = tmp_path / "first.json"
    with _spring_api(database, profiles) as api:
        first_result = _run(database, api, first_output)
    assert first_result.returncode == 0, first_result.stderr
    first = json.loads(first_output.read_text())
    connection = sqlite3.connect(database)
    connection.execute(
        "UPDATE reference_samples SET expected_c=expected_c+0.37 "
        "WHERE frame_id=(SELECT frame_id FROM frames ORDER BY captured_at,frame_id LIMIT 1)"
    )
    connection.commit()
    connection.close()
    second_output = tmp_path / "second.json"
    with _spring_api(database, profiles) as api:
        second_result = _run(database, api, second_output)
    assert second_result.returncode == 0, second_result.stderr
    second = json.loads(second_output.read_text())
    assert set(first) == {"frames", "summary"}
    assert set(second) == {"frames", "summary"}
    assert first["summary"]["evidenceSha256"] != second["summary"]["evidenceSha256"]
    assert second == _expected(database, profiles)
