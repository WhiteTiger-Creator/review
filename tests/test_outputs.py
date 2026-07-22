"""Independent verifier for the duration-aware sleep-stage HMM model."""

from __future__ import annotations

import csv
import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path


APP = Path("/app")
OUT = APP / "out"
STATES = ["quiet", "flow_limited", "apnea"]
FEATURES = ["airflow_flatness", "spo2_drop", "resp_pause", "body_motion"]
CAPS = [4, 3, 4]
COMPONENTS = [0, 1]
START_ALPHA = 0.5
DURATION_ALPHA = 0.5
DESTINATION_ALPHA = 0.25
VARIANCE_FLOOR = 0.0001
COVARIANCE_SHRINKAGE = 0.20
STUDENT_DEGREES_OF_FREEDOM = 5.0
MIXTURE_ALPHA = 0.25
TIE_EPSILON = 1e-12
ADAPTATION_ROUNDS = 3


@dataclass(frozen=True)
class Row:
    """One monitor sample from a trace CSV."""

    sequence_id: str
    t: int
    x: tuple[float, float, float, float]
    state: str | None = None


@dataclass(frozen=True)
class Decoded:
    """One expanded-state decode collapsed to clinical states."""

    path: list[int]
    posterior: list[list[float]]
    entropy: list[float]
    log_likelihood: float


@dataclass(frozen=True)
class ForwardBackward:
    """Forward and backward scores for one expanded-state sequence."""

    forward: list[list[float]]
    backward: list[list[float]]
    log_likelihood: float


EXPANDED = [
    (state, age)
    for state, cap in enumerate(CAPS)
    for age in range(1, cap + 1)
]


def run_command(args: list[str], cwd: Path = APP) -> None:
    """Run a task command and include useful output when it fails."""
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False)
    assert result.returncode == 0, (
        f"command failed: {' '.join(args)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def load_traces(directory: Path, require_state: bool) -> dict[str, list[Row]]:
    """Load traces using the documented file and sample ordering."""
    traces: dict[str, list[Row]] = {}
    files = sorted(directory.glob("*.csv"))
    assert files, f"no CSV files in {directory}"
    for path in files:
        with path.open(newline="") as handle:
            reader = csv.DictReader(handle)
            expected = ["sequence_id", "t", *FEATURES]
            if require_state:
                expected.append("state")
            assert reader.fieldnames == expected
            for item in reader:
                row = Row(
                    sequence_id=item["sequence_id"],
                    t=int(item["t"]),
                    x=tuple(float(item[name]) for name in FEATURES),  # type: ignore[arg-type]
                    state=item.get("state"),
                )
                traces.setdefault(row.sequence_id, []).append(row)
    for rows in traces.values():
        rows.sort(key=lambda row: row.t)
    return dict(sorted(traces.items()))


def state_index(state: str) -> int:
    """Return the documented clinical-state index."""
    return STATES.index(state)


def component_medians(traces: dict[str, list[Row]]) -> list[float]:
    """Derive the documented labeled spo2_drop median for every state."""
    values = [[] for _ in STATES]
    for rows in traces.values():
        for row in rows:
            assert row.state is not None
            values[state_index(row.state)].append(row.x[1])
    medians = []
    for state_values in values:
        assert state_values
        state_values.sort()
        middle = len(state_values) // 2
        medians.append(
            (state_values[middle - 1] + state_values[middle]) / 2.0
            if len(state_values) % 2 == 0
            else state_values[middle]
        )
    return medians


def component_index(row: Row, state: int, medians: list[float]) -> int:
    """Assign one labeled row to its documented baseline mixture component."""
    return 0 if row.x[1] <= medians[state] else 1


def collect_supervised_stats(traces: dict[str, list[Row]]) -> dict[str, object]:
    """Collect fixed labeled sufficient statistics from training traces."""
    start_counts = [0.0 for _ in STATES]
    medians = component_medians(traces)
    component_weight = [[0.0 for _ in COMPONENTS] for _ in STATES]
    sums = [[[0.0 for _ in FEATURES] for _ in COMPONENTS] for _ in STATES]
    cross_sums = [
        [[[0.0 for _ in FEATURES] for _ in FEATURES] for _ in COMPONENTS]
        for _ in STATES
    ]
    continue_counts = [[0.0 for _ in range(CAPS[state])] for state in range(len(STATES))]
    exit_counts = [[0.0 for _ in range(CAPS[state])] for state in range(len(STATES))]
    destination_counts = [[0.0 for _ in STATES] for _ in STATES]
    training_rows = 0

    for rows in traces.values():
        assert rows
        assert rows[0].state is not None
        start_counts[state_index(rows[0].state)] += 1.0
        previous_state = -1
        raw_age = 0
        for idx, row in enumerate(rows):
            assert row.state is not None
            state = state_index(row.state)
            raw_age = raw_age + 1 if state == previous_state else 1
            previous_state = state
            age = min(raw_age, CAPS[state])
            component = component_index(row, state, medians)
            component_weight[state][component] += 1.0
            training_rows += 1
            for feat_idx, value in enumerate(row.x):
                sums[state][component][feat_idx] += value
                for other_idx, other_value in enumerate(row.x):
                    cross_sums[state][component][feat_idx][other_idx] += value * other_value
            if idx + 1 < len(rows):
                assert rows[idx + 1].state is not None
                next_state = state_index(rows[idx + 1].state)
                if next_state == state:
                    continue_counts[state][age - 1] += 1.0
                else:
                    exit_counts[state][age - 1] += 1.0
                    destination_counts[state][next_state] += 1.0

    return {
        "training_sequences": len(traces),
        "training_rows": training_rows,
        "start_counts": start_counts,
        "component_weight": component_weight,
        "sums": sums,
        "cross_sums": cross_sums,
        "continue_counts": continue_counts,
        "exit_counts": exit_counts,
        "destination_counts": destination_counts,
    }


def empty_expected_stats() -> dict[str, object]:
    """Create empty expected calibration sufficient statistics."""
    return {
        "start_counts": [0.0 for _ in STATES],
        "component_weight": [[0.0 for _ in COMPONENTS] for _ in STATES],
        "sums": [[[0.0 for _ in FEATURES] for _ in COMPONENTS] for _ in STATES],
        "cross_sums": [
            [[[0.0 for _ in FEATURES] for _ in FEATURES] for _ in COMPONENTS]
            for _ in STATES
        ],
        "continue_counts": [[0.0 for _ in range(CAPS[state])] for state in range(len(STATES))],
        "exit_counts": [[0.0 for _ in range(CAPS[state])] for state in range(len(STATES))],
        "destination_counts": [[0.0 for _ in STATES] for _ in STATES],
    }


def reestimate_reference(
    labeled: dict[str, object], expected: dict[str, object], adaptation_sequences: int, adaptation_rows: int
) -> dict[str, object]:
    """Combine fixed labels and one expected calibration pass into a model."""
    start_counts = labeled["start_counts"]
    component_weight = labeled["component_weight"]
    sums = labeled["sums"]
    cross_sums = labeled["cross_sums"]
    continue_counts = labeled["continue_counts"]
    exit_counts = labeled["exit_counts"]
    destination_counts = labeled["destination_counts"]
    expected_start = expected["start_counts"]
    expected_weight = expected["component_weight"]
    expected_sums = expected["sums"]
    expected_cross_sums = expected["cross_sums"]
    expected_continue = expected["continue_counts"]
    expected_exit = expected["exit_counts"]
    expected_destination = expected["destination_counts"]
    assert isinstance(start_counts, list)
    assert isinstance(component_weight, list)
    assert isinstance(sums, list)
    assert isinstance(cross_sums, list)
    assert isinstance(continue_counts, list)
    assert isinstance(exit_counts, list)
    assert isinstance(destination_counts, list)
    assert isinstance(expected_start, list)
    assert isinstance(expected_weight, list)
    assert isinstance(expected_sums, list)
    assert isinstance(expected_cross_sums, list)
    assert isinstance(expected_continue, list)
    assert isinstance(expected_exit, list)
    assert isinstance(expected_destination, list)
    training_sequences = labeled["training_sequences"]
    training_rows = labeled["training_rows"]
    assert isinstance(training_sequences, int)
    assert isinstance(training_rows, int)
    start = [
        (start_counts[state] + expected_start[state] + START_ALPHA)
        / (training_sequences + adaptation_sequences + START_ALPHA * len(STATES))
        for state in range(len(STATES))
    ]
    duration_continue = []
    exit_destination = [[0.0 for _ in STATES] for _ in STATES]
    mixture_weight = [[0.0 for _ in COMPONENTS] for _ in STATES]
    mean = [[[0.0 for _ in FEATURES] for _ in COMPONENTS] for _ in STATES]
    covariance = [
        [[[0.0 for _ in FEATURES] for _ in FEATURES] for _ in COMPONENTS]
        for _ in STATES
    ]
    for state in range(len(STATES)):
        state_weight = sum(
            component_weight[state][component] + expected_weight[state][component]
            for component in COMPONENTS
        )
        assert state_weight > 0.0
        duration_continue.append(
            [
                (continue_counts[state][age] + expected_continue[state][age] + DURATION_ALPHA)
                /
                (
                    continue_counts[state][age]
                    + expected_continue[state][age]
                    + exit_counts[state][age]
                    + expected_exit[state][age]
                    + 2 * DURATION_ALPHA
                )
                for age in range(CAPS[state])
            ]
        )
        destination_total = sum(
            destination_counts[state][next_state] + expected_destination[state][next_state]
            for next_state in range(len(STATES))
            if next_state != state
        )
        for next_state in range(len(STATES)):
            if next_state != state:
                exit_destination[state][next_state] = (
                    destination_counts[state][next_state]
                    + expected_destination[state][next_state]
                    + DESTINATION_ALPHA
                ) / (destination_total + DESTINATION_ALPHA * (len(STATES) - 1))
        for component in COMPONENTS:
            combined_weight = (
                component_weight[state][component] + expected_weight[state][component]
            )
            assert combined_weight > 0.0
            mixture_weight[state][component] = (
                combined_weight + MIXTURE_ALPHA
            ) / (state_weight + MIXTURE_ALPHA * len(COMPONENTS))
            for feat_idx in range(len(FEATURES)):
                mean[state][component][feat_idx] = (
                    sums[state][component][feat_idx]
                    + expected_sums[state][component][feat_idx]
                ) / combined_weight
            for feat_idx in range(len(FEATURES)):
                for other_idx in range(len(FEATURES)):
                    second = (
                        cross_sums[state][component][feat_idx][other_idx]
                        + expected_cross_sums[state][component][feat_idx][other_idx]
                    ) / combined_weight
                    scatter = (
                        second
                        - mean[state][component][feat_idx]
                        * mean[state][component][other_idx]
                    )
                    covariance[state][component][feat_idx][other_idx] = (
                        scatter + VARIANCE_FLOOR
                        if feat_idx == other_idx
                        else (1.0 - COVARIANCE_SHRINKAGE) * scatter
                    )

    return {
        "training_sequences": training_sequences,
        "training_rows": training_rows,
        "adaptation_sequences": adaptation_sequences,
        "adaptation_rows": adaptation_rows,
        "start": start,
        "duration_continue": duration_continue,
        "exit_destination": exit_destination,
        "mixture_weight": mixture_weight,
        "mean": mean,
        "covariance": covariance,
    }


def train_reference(traces: dict[str, list[Row]]) -> dict[str, object]:
    """Fit the initial supervised model from labeled sufficient statistics."""
    return reestimate_reference(collect_supervised_stats(traces), empty_expected_stats(), 0, 0)


def component_log_probability(
    model: dict[str, object], state: int, component: int, row: Row
) -> float:
    """Compute one weighted shrinkage full-covariance Student-t component score."""
    mixture_weight = model["mixture_weight"]
    mean = model["mean"]
    covariance = model["covariance"]
    assert isinstance(mixture_weight, list)
    assert isinstance(mean, list)
    assert isinstance(covariance, list)
    lower = [[0.0 for _ in FEATURES] for _ in FEATURES]
    log_determinant = 0.0
    for row_idx in range(len(FEATURES)):
        for column_idx in range(row_idx + 1):
            value = covariance[state][component][row_idx][column_idx]
            value -= sum(lower[row_idx][inner] * lower[column_idx][inner] for inner in range(column_idx))
            if row_idx == column_idx:
                assert value > 0.0
                lower[row_idx][column_idx] = math.sqrt(value)
                log_determinant += 2.0 * math.log(lower[row_idx][column_idx])
            else:
                lower[row_idx][column_idx] = value / lower[column_idx][column_idx]
    solved = [0.0 for _ in FEATURES]
    for row_idx, value in enumerate(row.x):
        solved[row_idx] = (
            value
            - mean[state][component][row_idx]
            - sum(lower[row_idx][inner] * solved[inner] for inner in range(row_idx))
        ) / lower[row_idx][row_idx]
    quadratic = sum(value * value for value in solved)
    dimensions = len(FEATURES)
    return math.log(mixture_weight[state][component]) + (
        math.lgamma((STUDENT_DEGREES_OF_FREEDOM + dimensions) / 2.0)
        - math.lgamma(STUDENT_DEGREES_OF_FREEDOM / 2.0)
        - 0.5 * (dimensions * math.log(STUDENT_DEGREES_OF_FREEDOM * math.pi) + log_determinant)
        - ((STUDENT_DEGREES_OF_FREEDOM + dimensions) / 2.0)
        * math.log1p(quadratic / STUDENT_DEGREES_OF_FREEDOM)
    )


def emission_log_probability(model: dict[str, object], state: int, row: Row) -> float:
    """Marginalize the documented two-component Student-t state emission."""
    return logsumexp(
        [component_log_probability(model, state, component, row) for component in COMPONENTS]
    )


def edge_log_probability(
    model: dict[str, object], previous: tuple[int, int], following: tuple[int, int]
) -> float:
    """Return the documented expanded-state transition score."""
    duration_continue = model["duration_continue"]
    exit_destination = model["exit_destination"]
    assert isinstance(duration_continue, list)
    assert isinstance(exit_destination, list)
    state, age = previous
    next_state, next_age = following
    continue_probability = duration_continue[state][age - 1]
    if state == next_state:
        if next_age != min(age + 1, CAPS[state]):
            return -math.inf
        return math.log(continue_probability)
    if next_age != 1:
        return -math.inf
    return math.log(1.0 - continue_probability) + math.log(exit_destination[state][next_state])


def logsumexp(values: list[float]) -> float:
    """Calculate logsumexp while handling impossible transitions."""
    maximum = max(values, default=-math.inf)
    if not math.isfinite(maximum):
        return -math.inf
    return maximum + math.log(sum(math.exp(value - maximum) for value in values if math.isfinite(value)))


def forward_backward_reference(model: dict[str, object], rows: list[Row]) -> ForwardBackward:
    """Run the documented expanded-state forward-backward calculation."""
    start = model["start"]
    assert isinstance(start, list)
    forward = [[-math.inf for _ in EXPANDED] for _ in rows]
    for state in range(len(STATES)):
        index = EXPANDED.index((state, 1))
        forward[0][index] = math.log(start[state]) + emission_log_probability(model, state, rows[0])
    for row_idx in range(1, len(rows)):
        for next_idx, following in enumerate(EXPANDED):
            candidates = []
            for previous_idx, previous in enumerate(EXPANDED):
                edge = edge_log_probability(model, previous, following)
                if math.isfinite(edge) and math.isfinite(forward[row_idx - 1][previous_idx]):
                    candidates.append(forward[row_idx - 1][previous_idx] + edge)
            total = logsumexp(candidates)
            if math.isfinite(total):
                forward[row_idx][next_idx] = total + emission_log_probability(
                    model, following[0], rows[row_idx]
                )
    backward = [[0.0 for _ in EXPANDED] for _ in rows]
    for row_idx in range(len(rows) - 2, -1, -1):
        for previous_idx, previous in enumerate(EXPANDED):
            candidates = []
            for next_idx, following in enumerate(EXPANDED):
                edge = edge_log_probability(model, previous, following)
                if math.isfinite(edge):
                    candidates.append(
                        edge
                        + emission_log_probability(model, following[0], rows[row_idx + 1])
                        + backward[row_idx + 1][next_idx]
                    )
            backward[row_idx][previous_idx] = logsumexp(candidates)
    log_likelihood = logsumexp(forward[-1])
    assert math.isfinite(log_likelihood)
    return ForwardBackward(forward=forward, backward=backward, log_likelihood=log_likelihood)


def expected_calibration_stats(
    model: dict[str, object], traces: dict[str, list[Row]]
) -> tuple[dict[str, object], float]:
    """Calculate one documented E-step from unlabeled calibration traces."""
    expected = empty_expected_stats()
    start_counts = expected["start_counts"]
    component_weight = expected["component_weight"]
    sums = expected["sums"]
    cross_sums = expected["cross_sums"]
    continue_counts = expected["continue_counts"]
    exit_counts = expected["exit_counts"]
    destination_counts = expected["destination_counts"]
    assert isinstance(start_counts, list)
    assert isinstance(component_weight, list)
    assert isinstance(sums, list)
    assert isinstance(cross_sums, list)
    assert isinstance(continue_counts, list)
    assert isinstance(exit_counts, list)
    assert isinstance(destination_counts, list)
    total_log_likelihood = 0.0
    for rows in traces.values():
        calculation = forward_backward_reference(model, rows)
        total_log_likelihood += calculation.log_likelihood
        for row_idx, row in enumerate(rows):
            expanded_mass = [0.0 for _ in EXPANDED]
            state_mass = [0.0 for _ in STATES]
            for expanded_idx, (state, _) in enumerate(EXPANDED):
                log_mass = (
                    calculation.forward[row_idx][expanded_idx]
                    + calculation.backward[row_idx][expanded_idx]
                    - calculation.log_likelihood
                )
                if math.isfinite(log_mass):
                    expanded_mass[expanded_idx] = math.exp(log_mass)
                    state_mass[state] += expanded_mass[expanded_idx]
            total_mass = sum(state_mass)
            assert total_mass > 0.0
            for state in range(len(STATES)):
                gamma = state_mass[state] / total_mass
                state_emission = emission_log_probability(model, state, row)
                for component in COMPONENTS:
                    responsibility = math.exp(
                        component_log_probability(model, state, component, row) - state_emission
                    )
                    component_mass = gamma * responsibility
                    component_weight[state][component] += component_mass
                    for feat_idx, value in enumerate(row.x):
                        sums[state][component][feat_idx] += component_mass * value
                        for other_idx, other_value in enumerate(row.x):
                            cross_sums[state][component][feat_idx][other_idx] += (
                                component_mass * value * other_value
                            )
            if row_idx == 0:
                for expanded_idx, (state, age) in enumerate(EXPANDED):
                    if age == 1:
                        start_counts[state] += expanded_mass[expanded_idx] / total_mass
        for row_idx in range(len(rows) - 1):
            for previous_idx, previous in enumerate(EXPANDED):
                for next_idx, following in enumerate(EXPANDED):
                    edge = edge_log_probability(model, previous, following)
                    if not math.isfinite(edge):
                        continue
                    log_xi = (
                        calculation.forward[row_idx][previous_idx]
                        + edge
                        + emission_log_probability(model, following[0], rows[row_idx + 1])
                        + calculation.backward[row_idx + 1][next_idx]
                        - calculation.log_likelihood
                    )
                    if not math.isfinite(log_xi):
                        continue
                    xi = math.exp(log_xi)
                    state, age = previous
                    next_state, _ = following
                    if state == next_state:
                        continue_counts[state][age - 1] += xi
                    else:
                        exit_counts[state][age - 1] += xi
                        destination_counts[state][next_state] += xi
    return expected, total_log_likelihood


def adapted_reference(
    train: dict[str, list[Row]], adaptation: dict[str, list[Row]]
) -> dict[str, object]:
    """Run the three fixed anchored adaptation rounds independently."""
    labeled = collect_supervised_stats(train)
    adaptation_rows = sum(len(rows) for rows in adaptation.values())
    model = reestimate_reference(labeled, empty_expected_stats(), 0, 0)
    log_likelihoods = []
    for _ in range(ADAPTATION_ROUNDS):
        expected, log_likelihood = expected_calibration_stats(model, adaptation)
        log_likelihoods.append(log_likelihood)
        model = reestimate_reference(labeled, expected, len(adaptation), adaptation_rows)
    model["adaptation_iterations"] = ADAPTATION_ROUNDS
    model["adaptation_log_likelihood"] = log_likelihoods
    return model


def decode_reference(model: dict[str, object], rows: list[Row]) -> Decoded:
    """Run documented Viterbi and forward-backward calculations."""
    start = model["start"]
    assert isinstance(start, list)
    viterbi = [[-math.inf for _ in EXPANDED] for _ in rows]
    predecessor = [[0 for _ in EXPANDED] for _ in rows]
    for state in range(len(STATES)):
        index = EXPANDED.index((state, 1))
        viterbi[0][index] = math.log(start[state]) + emission_log_probability(model, state, rows[0])
    for row_idx in range(1, len(rows)):
        for next_idx, following in enumerate(EXPANDED):
            best = -math.inf
            best_previous = 0
            for previous_idx, previous in enumerate(EXPANDED):
                edge = edge_log_probability(model, previous, following)
                candidate = viterbi[row_idx - 1][previous_idx] + edge
                if math.isfinite(candidate) and candidate > best + TIE_EPSILON:
                    best = candidate
                    best_previous = previous_idx
            if math.isfinite(best):
                viterbi[row_idx][next_idx] = best + emission_log_probability(
                    model, following[0], rows[row_idx]
                )
                predecessor[row_idx][next_idx] = best_previous

    best = -math.inf
    final_idx = 0
    for idx, score in enumerate(viterbi[-1]):
        if score > best + TIE_EPSILON:
            best = score
            final_idx = idx
    assert math.isfinite(best)
    expanded_path = [0 for _ in rows]
    expanded_path[-1] = final_idx
    for row_idx in range(len(rows) - 1, 0, -1):
        expanded_path[row_idx - 1] = predecessor[row_idx][expanded_path[row_idx]]

    calculation = forward_backward_reference(model, rows)
    log_likelihood = calculation.log_likelihood
    posterior: list[list[float]] = []
    entropy: list[float] = []
    for row_idx in range(len(rows)):
        state_mass = [0.0 for _ in STATES]
        for expanded_idx, (state, _) in enumerate(EXPANDED):
            log_mass = (
                calculation.forward[row_idx][expanded_idx]
                + calculation.backward[row_idx][expanded_idx]
                - log_likelihood
            )
            if math.isfinite(log_mass):
                state_mass[state] += math.exp(log_mass)
        total_mass = sum(state_mass)
        assert total_mass > 0.0
        probabilities = [mass / total_mass for mass in state_mass]
        posterior.append(probabilities)
        entropy.append(-sum(value * math.log(value) for value in probabilities if value > 0.0))
    return Decoded(
        path=[EXPANDED[index][0] for index in expanded_path],
        posterior=posterior,
        entropy=entropy,
        log_likelihood=log_likelihood,
    )


def expected_predictions(
    model: dict[str, object], traces: dict[str, list[Row]]
) -> list[dict[str, str]]:
    """Build expected inference prediction rows."""
    result = []
    for sequence_id, rows in traces.items():
        decoded = decode_reference(model, rows)
        for row, state in zip(rows, decoded.path, strict=True):
            result.append(
                {"sequence_id": sequence_id, "t": str(row.t), "predicted_state": STATES[state]}
            )
    return result


def expected_posteriors(
    model: dict[str, object], traces: dict[str, list[Row]]
) -> list[tuple[str, int, list[float], float]]:
    """Build expected posterior rows without fixing a serialization style."""
    result = []
    for sequence_id, rows in traces.items():
        decoded = decode_reference(model, rows)
        for row, probabilities, entropy in zip(rows, decoded.posterior, decoded.entropy, strict=True):
            result.append((sequence_id, row.t, probabilities, entropy))
    return result


def expected_events(
    model: dict[str, object], traces: dict[str, list[Row]]
) -> list[dict[str, object]]:
    """Build expected duration-aware apnea-event summaries."""
    result = []
    apnea = state_index("apnea")
    for sequence_id, rows in traces.items():
        decoded = decode_reference(model, rows)
        idx = 0
        while idx < len(rows):
            if decoded.path[idx] != apnea:
                idx += 1
                continue
            start = idx
            spo2_sum = 0.0
            posterior_sum = 0.0
            max_pause = rows[idx].x[2]
            while idx < len(rows) and decoded.path[idx] == apnea:
                spo2_sum += rows[idx].x[1]
                posterior_sum += decoded.posterior[idx][apnea]
                max_pause = max(max_pause, rows[idx].x[2])
                idx += 1
            length = idx - start
            if length >= 2:
                mean_posterior = posterior_sum / length
                result.append(
                    {
                        "sequence_id": sequence_id,
                        "start_t": rows[start].t,
                        "end_t": rows[idx - 1].t,
                        "length": length,
                        "mean_spo2_drop": spo2_sum / length,
                        "max_resp_pause": max_pause,
                        "mean_apnea_posterior": mean_posterior,
                        "severity": "high"
                        if length >= 3 or max_pause >= 15.0 or mean_posterior >= 0.85
                        else "watch",
                        "preceding_state": "start"
                        if start == 0
                        else STATES[decoded.path[start - 1]],
                    }
                )
    return result


def expected_validation_metrics(
    model: dict[str, object], traces: dict[str, list[Row]]
) -> dict[str, object]:
    """Compute all documented validation metrics from independent decoding."""
    confusion = [[0 for _ in STATES] for _ in STATES]
    correct = 0
    total = 0
    nll = 0.0
    entropy_sum = 0.0
    for rows in traces.values():
        decoded = decode_reference(model, rows)
        nll -= decoded.log_likelihood
        for row, predicted, entropy in zip(rows, decoded.path, decoded.entropy, strict=True):
            assert row.state is not None
            actual = state_index(row.state)
            confusion[actual][predicted] += 1
            correct += int(actual == predicted)
            total += 1
            entropy_sum += entropy
    f1_values = []
    for state in range(len(STATES)):
        true_positive = confusion[state][state]
        predicted_total = sum(confusion[actual][state] for actual in range(len(STATES)))
        actual_total = sum(confusion[state])
        precision = true_positive / predicted_total if predicted_total else 0.0
        recall = true_positive / actual_total if actual_total else 0.0
        f1_values.append(
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
    return {
        "accuracy": correct / total,
        "macro_f1": sum(f1_values) / len(f1_values),
        "mean_negative_log_likelihood": nll / total,
        "mean_posterior_entropy": entropy_sum / total,
        "confusion": {
            STATES[actual]: {
                STATES[predicted]: confusion[actual][predicted]
                for predicted in range(len(STATES))
            }
            for actual in range(len(STATES))
        },
    }


def assert_close(actual: float, expected: float, tolerance: float = 1e-9) -> None:
    """Assert that a serialized numeric value meets the documented precision."""
    assert math.isfinite(actual)
    assert abs(actual - expected) <= tolerance, (actual, expected)


def read_csv_dicts(path: Path) -> list[dict[str, str]]:
    """Read one CSV output as dictionaries."""
    with path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def run_default_once() -> None:
    """Train and evaluate the model through the standard local entrypoint."""
    run_command(["/app/scripts/run-triage.sh"])


def assert_posteriors_match(
    path: Path, expected: list[tuple[str, int, list[float], float]]
) -> None:
    """Compare posterior rows including probabilities and entropy."""
    actual = read_csv_dicts(path)
    assert len(actual) == len(expected)
    for row, (sequence_id, t, probabilities, entropy) in zip(actual, expected, strict=True):
        assert row["sequence_id"] == sequence_id
        assert int(row["t"]) == t
        actual_probabilities = [float(row[f"{state}_posterior"]) for state in STATES]
        for actual_value, expected_value in zip(actual_probabilities, probabilities, strict=True):
            assert_close(actual_value, expected_value)
        assert_close(sum(actual_probabilities), 1.0)
        assert_close(float(row["entropy"]), entropy)


def assert_events_match(actual_path: Path, expected: list[dict[str, object]]) -> None:
    """Compare apnea-event summaries without relying on CSV formatting."""
    actual = read_csv_dicts(actual_path)
    assert len(actual) == len(expected)
    for row, exp in zip(actual, expected, strict=True):
        assert row["sequence_id"] == exp["sequence_id"]
        assert int(row["start_t"]) == exp["start_t"]
        assert int(row["end_t"]) == exp["end_t"]
        assert int(row["length"]) == exp["length"]
        assert_close(float(row["mean_spo2_drop"]), exp["mean_spo2_drop"])
        assert_close(float(row["max_resp_pause"]), exp["max_resp_pause"])
        assert_close(float(row["mean_apnea_posterior"]), exp["mean_apnea_posterior"])
        assert row["severity"] == exp["severity"]
        assert row["preceding_state"] == exp["preceding_state"]


def assert_model_matches(model: dict[str, object], reference: dict[str, object]) -> None:
    """Compare every fitted parameter and documented adaptation record."""
    assert model["training_sequences"] == reference["training_sequences"]
    assert model["training_rows"] == reference["training_rows"]
    assert model["adaptation_sequences"] == reference["adaptation_sequences"]
    assert model["adaptation_rows"] == reference["adaptation_rows"]
    assert model["adaptation_iterations"] == reference["adaptation_iterations"]
    assert_close(model["emission_degrees_of_freedom"], STUDENT_DEGREES_OF_FREEDOM)
    history = reference["adaptation_log_likelihood"]
    assert isinstance(history, list)
    assert len(model["adaptation_log_likelihood"]) == len(history)
    for actual, expected in zip(model["adaptation_log_likelihood"], history, strict=True):
        assert_close(actual, expected)
    start = reference["start"]
    duration_continue = reference["duration_continue"]
    exit_destination = reference["exit_destination"]
    mixture_weight = reference["mixture_weight"]
    mean = reference["mean"]
    covariance = reference["covariance"]
    assert isinstance(start, list)
    assert isinstance(duration_continue, list)
    assert isinstance(exit_destination, list)
    assert isinstance(mixture_weight, list)
    assert isinstance(mean, list)
    assert isinstance(covariance, list)
    for state_idx, state in enumerate(STATES):
        assert_close(model["start_probability"][state], start[state_idx])
        for age in range(1, CAPS[state_idx] + 1):
            assert_close(
                model["duration_continue_probability"][state][str(age)],
                duration_continue[state_idx][age - 1],
            )
        for next_idx, next_state in enumerate(STATES):
            if next_idx != state_idx:
                assert_close(
                    model["exit_destination_probability"][state][next_state],
                    exit_destination[state_idx][next_idx],
                )
        emission = model["emission"][state]
        assert set(emission) == {"mixture_weight", "components"}
        for component in COMPONENTS:
            key = str(component)
            assert_close(emission["mixture_weight"][key], mixture_weight[state_idx][component])
            component_emission = emission["components"][key]
            assert set(component_emission) == {"mean", "covariance"}
            for feature_idx, feature in enumerate(FEATURES):
                assert_close(
                    component_emission["mean"][feature], mean[state_idx][component][feature_idx]
                )
                for other_idx, other_feature in enumerate(FEATURES):
                    assert_close(
                        component_emission["covariance"][feature][other_feature],
                        covariance[state_idx][component][feature_idx][other_idx],
                    )


def default_reference() -> dict[str, object]:
    """Fit the documented default training and calibration batches."""
    return adapted_reference(
        load_traces(APP / "data/train", require_state=True),
        load_traces(APP / "data/adaptation", require_state=False),
    )


def test_trained_model_artifacts_have_documented_schemas() -> None:
    """Verify training produces every documented model and evaluation artifact."""
    run_default_once()
    required_outputs = {
        "model.json",
        "predictions.csv",
        "posterior.csv",
        "apnea_events.csv",
        "validation_metrics.json",
    }
    assert required_outputs.issubset({path.name for path in OUT.iterdir()})
    model = json.loads((OUT / "model.json").read_text())
    assert set(model) == {
        "states",
        "features",
        "training_sequences",
        "training_rows",
        "adaptation_sequences",
        "adaptation_rows",
        "adaptation_iterations",
        "emission_degrees_of_freedom",
        "adaptation_log_likelihood",
        "start_probability",
        "duration_cap",
        "duration_continue_probability",
        "exit_destination_probability",
        "emission",
    }
    assert model["states"] == STATES
    assert model["features"] == FEATURES
    assert model["duration_cap"] == dict(zip(STATES, CAPS, strict=True))
    for state_idx, state in enumerate(STATES):
        assert set(model["duration_continue_probability"][state]) == {
            str(age) for age in range(1, CAPS[state_idx] + 1)
        }
        assert set(model["exit_destination_probability"][state]) == set(STATES) - {state}
        emission = model["emission"][state]
        assert set(emission) == {"mixture_weight", "components"}
        assert set(emission["mixture_weight"]) == {str(component) for component in COMPONENTS}
        assert set(emission["components"]) == {str(component) for component in COMPONENTS}
        for component in COMPONENTS:
            component_emission = emission["components"][str(component)]
            assert set(component_emission) == {"mean", "covariance"}
            assert set(component_emission["mean"]) == set(FEATURES)
            assert set(component_emission["covariance"]) == set(FEATURES)
            for feature in FEATURES:
                assert set(component_emission["covariance"][feature]) == set(FEATURES)
    with (OUT / "predictions.csv").open(newline="") as handle:
        assert csv.DictReader(handle).fieldnames == ["sequence_id", "t", "predicted_state"]
    with (OUT / "posterior.csv").open(newline="") as handle:
        assert csv.DictReader(handle).fieldnames == [
            "sequence_id",
            "t",
            "quiet_posterior",
            "flow_limited_posterior",
            "apnea_posterior",
            "entropy",
        ]
    with (OUT / "apnea_events.csv").open(newline="") as handle:
        assert csv.DictReader(handle).fieldnames == [
            "sequence_id",
            "start_t",
            "end_t",
            "length",
            "mean_spo2_drop",
            "max_resp_pause",
            "mean_apnea_posterior",
            "severity",
            "preceding_state",
        ]


def test_model_parameters_match_documented_mixture_adaptation_rules() -> None:
    """Verify model.json contains the full-covariance mixture adaptation result."""
    run_default_once()
    reference = default_reference()
    model = json.loads((OUT / "model.json").read_text())
    assert_model_matches(model, reference)


def test_inference_predictions_posteriors_and_events_follow_model_contract() -> None:
    """Verify inference staging, posterior confidence, and event triage are coherent."""
    run_default_once()
    reference = default_reference()
    inference = load_traces(APP / "data/inference", require_state=False)
    assert read_csv_dicts(OUT / "predictions.csv") == expected_predictions(reference, inference)
    assert_posteriors_match(OUT / "posterior.csv", expected_posteriors(reference, inference))
    assert_events_match(OUT / "apnea_events.csv", expected_events(reference, inference))


def test_validation_metrics_match_duration_aware_reference_decoder() -> None:
    """Verify validation metrics use Viterbi and forward-backward results."""
    run_default_once()
    reference = default_reference()
    validation = load_traces(APP / "data/validation", require_state=True)
    expected = expected_validation_metrics(reference, validation)
    actual = json.loads((OUT / "validation_metrics.json").read_text())
    for key in [
        "accuracy",
        "macro_f1",
        "mean_negative_log_likelihood",
        "mean_posterior_entropy",
    ]:
        assert_close(actual[key], expected[key])
    assert actual["confusion"] == expected["confusion"]


def write_trace(path: Path, rows: list[Row], include_state: bool) -> None:
    """Write a temporary CSV trace fixture."""
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = ["sequence_id", "t", *FEATURES]
    if include_state:
        headers.append("state")
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for row in rows:
            values: list[object] = [row.sequence_id, row.t, *row.x]
            if include_state:
                assert row.state is not None
                values.append(row.state)
            writer.writerow(values)


def test_mixture_adaptation_reuses_contract_on_alternate_fixture(tmp_path: Path) -> None:
    """Verify calibration changes all model paths on an independent fixture."""
    run_default_once()
    fixture = tmp_path / "fixture"
    train_rows = [
        Row("tmp-1", 0, (0.10, 0.0, 0.4, 0.10), "quiet"),
        Row("tmp-1", 1, (0.16, 0.2, 0.8, 0.13), "quiet"),
        Row("tmp-1", 2, (0.20, 0.3, 1.0, 0.15), "quiet"),
        Row("tmp-1", 3, (0.46, 1.2, 3.2, 0.25), "flow_limited"),
        Row("tmp-1", 4, (0.50, 1.5, 3.9, 0.27), "flow_limited"),
        Row("tmp-1", 5, (0.84, 4.4, 12.0, 0.11), "apnea"),
        Row("tmp-1", 6, (0.89, 5.1, 15.6, 0.08), "apnea"),
        Row("tmp-1", 7, (0.92, 5.5, 16.3, 0.07), "apnea"),
        Row("tmp-1", 8, (0.55, 1.9, 4.6, 0.24), "flow_limited"),
        Row("tmp-1", 9, (0.17, 0.2, 0.8, 0.18), "quiet"),
        Row("tmp-2", 0, (0.14, 0.1, 0.6, 0.16), "quiet"),
        Row("tmp-2", 1, (0.42, 1.0, 2.8, 0.26), "flow_limited"),
        Row("tmp-2", 2, (0.48, 1.4, 3.5, 0.28), "flow_limited"),
        Row("tmp-2", 3, (0.54, 1.8, 4.4, 0.25), "flow_limited"),
        Row("tmp-2", 4, (0.79, 3.9, 10.8, 0.14), "apnea"),
        Row("tmp-2", 5, (0.85, 4.7, 13.0, 0.10), "apnea"),
        Row("tmp-2", 6, (0.58, 2.1, 5.0, 0.22), "flow_limited"),
        Row("tmp-2", 7, (0.18, 0.3, 1.1, 0.20), "quiet"),
    ]
    validation_rows = [
        Row("check", 0, (0.13, 0.1, 0.5, 0.14), "quiet"),
        Row("check", 1, (0.18, 0.3, 1.0, 0.19), "quiet"),
        Row("check", 2, (0.45, 1.1, 3.0, 0.25), "flow_limited"),
        Row("check", 3, (0.51, 1.6, 4.0, 0.26), "flow_limited"),
        Row("check", 4, (0.86, 4.8, 14.1, 0.10), "apnea"),
        Row("check", 5, (0.90, 5.2, 15.9, 0.08), "apnea"),
        Row("check", 6, (0.56, 2.0, 4.8, 0.22), "flow_limited"),
    ]
    inference_rows = [
        Row("fresh", 0, (0.15, 0.2, 0.7, 0.17)),
        Row("fresh", 1, (0.43, 1.0, 2.9, 0.25)),
        Row("fresh", 2, (0.49, 1.5, 3.8, 0.26)),
        Row("fresh", 3, (0.83, 4.2, 11.7, 0.12)),
        Row("fresh", 4, (0.89, 5.0, 15.4, 0.09)),
        Row("fresh", 5, (0.91, 5.4, 16.2, 0.07)),
        Row("fresh", 6, (0.55, 2.0, 4.9, 0.21)),
    ]
    adaptation_rows = [
        Row("cal-a", 0, (0.20, 0.4, 1.0, 0.18)),
        Row("cal-a", 1, (0.25, 0.6, 1.4, 0.17)),
        Row("cal-a", 2, (0.50, 1.8, 4.1, 0.27)),
        Row("cal-a", 3, (0.56, 2.2, 4.8, 0.24)),
        Row("cal-a", 4, (0.86, 5.1, 14.0, 0.11)),
        Row("cal-a", 5, (0.92, 5.9, 17.0, 0.07)),
        Row("cal-a", 6, (0.58, 2.4, 5.2, 0.22)),
        Row("cal-b", 0, (0.18, 0.3, 0.8, 0.19)),
        Row("cal-b", 1, (0.46, 1.5, 3.6, 0.26)),
        Row("cal-b", 2, (0.53, 2.0, 4.5, 0.25)),
        Row("cal-b", 3, (0.82, 4.6, 12.4, 0.12)),
        Row("cal-b", 4, (0.88, 5.4, 15.5, 0.09)),
        Row("cal-b", 5, (0.57, 2.3, 5.1, 0.23)),
    ]
    write_trace(fixture / "train" / "z.csv", train_rows[:10], include_state=True)
    write_trace(fixture / "train" / "a.csv", train_rows[10:], include_state=True)
    write_trace(fixture / "adapt" / "b.csv", adaptation_rows[:7], include_state=False)
    write_trace(fixture / "adapt" / "a.csv", adaptation_rows[7:], include_state=False)
    write_trace(fixture / "validation" / "check.csv", validation_rows, include_state=True)
    write_trace(fixture / "infer" / "fresh.csv", inference_rows, include_state=False)
    out_dir = fixture / "out"
    run_command(
        [
            "/app/bin/apnea_hmm",
            "--train",
            str(fixture / "train"),
            "--adapt",
            str(fixture / "adapt"),
            "--validation",
            str(fixture / "validation"),
            "--infer",
            str(fixture / "infer"),
            "--out-dir",
            str(out_dir),
        ]
    )
    train = load_traces(fixture / "train", require_state=True)
    adaptation = load_traces(fixture / "adapt", require_state=False)
    reference = adapted_reference(train, adaptation)
    model = json.loads((out_dir / "model.json").read_text())
    assert_model_matches(model, reference)
    inference = load_traces(fixture / "infer", require_state=False)
    assert read_csv_dicts(out_dir / "predictions.csv") == expected_predictions(reference, inference)
    assert_posteriors_match(out_dir / "posterior.csv", expected_posteriors(reference, inference))
    assert_events_match(out_dir / "apnea_events.csv", expected_events(reference, inference))
    expected_metrics = expected_validation_metrics(
        reference, load_traces(fixture / "validation", require_state=True)
    )
    metrics = json.loads((out_dir / "validation_metrics.json").read_text())
    for key in [
        "accuracy",
        "macro_f1",
        "mean_negative_log_likelihood",
        "mean_posterior_entropy",
    ]:
        assert_close(metrics[key], expected_metrics[key])
    assert metrics["confusion"] == expected_metrics["confusion"]


def test_rerun_replaces_documented_outputs() -> None:
    """Verify every documented output overwrites stale prior content."""
    OUT.mkdir(parents=True, exist_ok=True)
    stale_files = {
        "model.json": "{\"stale\": true}\n",
        "predictions.csv": "stale\n",
        "posterior.csv": "stale\n",
        "apnea_events.csv": "stale\n",
        "validation_metrics.json": "{\"stale\": true}\n",
    }
    for name, content in stale_files.items():
        (OUT / name).write_text(content)
    run_default_once()
    for name in stale_files:
        assert "stale" not in (OUT / name).read_text()
