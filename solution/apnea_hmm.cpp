#include <algorithm>
#include <array>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

constexpr int kStateCount = 3;
constexpr int kFeatureCount = 4;
constexpr int kComponentCount = 2;
constexpr int kAdaptationRounds = 3;
constexpr double kStartAlpha = 0.5;
constexpr double kDurationAlpha = 0.5;
constexpr double kDestinationAlpha = 0.25;
constexpr double kVarianceFloor = 0.0001;
constexpr double kCovarianceShrinkage = 0.20;
constexpr double kStudentDegreesOfFreedom = 5.0;
constexpr double kMixtureAlpha = 0.25;
constexpr double kTieEpsilon = 1e-12;
constexpr double kNegativeInfinity = -std::numeric_limits<double>::infinity();
constexpr double kPi = 3.141592653589793238462643383279502884;

const std::array<std::string, kStateCount> kStates = {
    "quiet", "flow_limited", "apnea"};
const std::array<std::string, kFeatureCount> kFeatures = {
    "airflow_flatness", "spo2_drop", "resp_pause", "body_motion"};
const std::array<int, kStateCount> kDurationCaps = {4, 3, 4};

struct Row {
    std::string sequence_id;
    int t = 0;
    std::array<double, kFeatureCount> features{};
    std::string state;
};

using TraceMap = std::map<std::string, std::vector<Row>>;
using FeatureVector = std::array<double, kFeatureCount>;
using CovarianceMatrix = std::array<FeatureVector, kFeatureCount>;
using ComponentWeights = std::array<double, kComponentCount>;
using ComponentMeans = std::array<FeatureVector, kComponentCount>;
using ComponentCovariances = std::array<CovarianceMatrix, kComponentCount>;

struct Model {
    int training_sequences = 0;
    int training_rows = 0;
    int adaptation_sequences = 0;
    int adaptation_rows = 0;
    int adaptation_iterations = 0;
    std::vector<double> adaptation_log_likelihood;
    std::array<double, kStateCount> start_probability{};
    std::array<std::vector<double>, kStateCount> duration_continue_probability;
    std::array<std::array<double, kStateCount>, kStateCount>
        exit_destination_probability{};
    std::array<ComponentWeights, kStateCount> mixture_weight{};
    std::array<ComponentMeans, kStateCount> mean{};
    std::array<ComponentCovariances, kStateCount> covariance{};
};

struct SupervisedStats {
    int sequences = 0;
    int rows = 0;
    std::array<double, kStateCount> start_counts{};
    std::array<ComponentWeights, kStateCount> component_weight{};
    std::array<ComponentMeans, kStateCount> sums{};
    std::array<ComponentCovariances, kStateCount> cross_sums{};
    std::array<std::vector<double>, kStateCount> continue_counts;
    std::array<std::vector<double>, kStateCount> exit_counts;
    std::array<std::array<double, kStateCount>, kStateCount> destination_counts{};
};

struct ExpectedStats {
    std::array<double, kStateCount> start_counts{};
    std::array<ComponentWeights, kStateCount> component_weight{};
    std::array<ComponentMeans, kStateCount> sums{};
    std::array<ComponentCovariances, kStateCount> cross_sums{};
    std::array<std::vector<double>, kStateCount> continue_counts;
    std::array<std::vector<double>, kStateCount> exit_counts;
    std::array<std::array<double, kStateCount>, kStateCount> destination_counts{};
    double log_likelihood = 0.0;
};

struct ExpandedState {
    int state = 0;
    int age = 1;
};

struct ForwardBackward {
    std::vector<std::vector<double>> forward;
    std::vector<std::vector<double>> backward;
    double log_likelihood = 0.0;
};

struct DecodedSequence {
    std::vector<int> viterbi_states;
    std::vector<std::array<double, kStateCount>> posterior;
    std::vector<double> entropy;
    double log_likelihood = 0.0;
};

struct Arguments {
    fs::path train_dir;
    fs::path adaptation_dir;
    fs::path validation_dir;
    fs::path inference_dir;
    fs::path out_dir;
};

int state_index(const std::string& state) {
    for (int index = 0; index < kStateCount; ++index) {
        if (kStates[index] == state) {
            return index;
        }
    }
    throw std::runtime_error("unknown state: " + state);
}

std::string strip_cr(std::string value) {
    if (!value.empty() && value.back() == '\r') {
        value.pop_back();
    }
    return value;
}

std::vector<std::string> split_csv(const std::string& line) {
    std::vector<std::string> cells;
    std::string cell;
    for (char character : line) {
        if (character == ',') {
            cells.push_back(strip_cr(cell));
            cell.clear();
        } else {
            cell.push_back(character);
        }
    }
    cells.push_back(strip_cr(cell));
    return cells;
}

TraceMap load_traces(const fs::path& directory, bool require_state) {
    std::vector<fs::path> files;
    for (const fs::directory_entry& entry : fs::directory_iterator(directory)) {
        if (entry.is_regular_file() && entry.path().extension() == ".csv") {
            files.push_back(entry.path());
        }
    }
    std::sort(files.begin(), files.end());
    if (files.empty()) {
        throw std::runtime_error("no CSV files in " + directory.string());
    }

    const std::vector<std::string> expected_header = require_state
        ? std::vector<std::string>{"sequence_id", "t", "airflow_flatness",
                                   "spo2_drop", "resp_pause", "body_motion", "state"}
        : std::vector<std::string>{"sequence_id", "t", "airflow_flatness",
                                   "spo2_drop", "resp_pause", "body_motion"};
    TraceMap traces;
    for (const fs::path& path : files) {
        std::ifstream input(path);
        if (!input) {
            throw std::runtime_error("cannot read " + path.string());
        }
        std::string line;
        if (!std::getline(input, line) || split_csv(line) != expected_header) {
            throw std::runtime_error("unexpected CSV header in " + path.string());
        }
        while (std::getline(input, line)) {
            if (line.empty()) {
                continue;
            }
            const std::vector<std::string> cells = split_csv(line);
            if (cells.size() != expected_header.size()) {
                throw std::runtime_error("unexpected CSV row in " + path.string());
            }
            Row row;
            row.sequence_id = cells[0];
            row.t = std::stoi(cells[1]);
            for (int feature = 0; feature < kFeatureCount; ++feature) {
                row.features[feature] = std::stod(cells[feature + 2]);
            }
            if (require_state) {
                row.state = cells[6];
                (void)state_index(row.state);
            }
            traces[row.sequence_id].push_back(row);
        }
    }
    for (auto& [sequence_id, rows] : traces) {
        (void)sequence_id;
        std::sort(rows.begin(), rows.end(), [](const Row& left, const Row& right) {
            return left.t < right.t;
        });
    }
    return traces;
}

void initialize_duration_counts(std::array<std::vector<double>, kStateCount>* counts) {
    for (int state = 0; state < kStateCount; ++state) {
        (*counts)[state].assign(kDurationCaps[state], 0.0);
    }
}

std::array<double, kStateCount> component_medians(const TraceMap& traces) {
    std::array<std::vector<double>, kStateCount> values;
    for (const auto& [sequence_id, rows] : traces) {
        (void)sequence_id;
        for (const Row& row : rows) {
            values[state_index(row.state)].push_back(row.features[1]);
        }
    }
    std::array<double, kStateCount> medians{};
    for (int state = 0; state < kStateCount; ++state) {
        std::vector<double>& state_values = values[state];
        if (state_values.empty()) {
            throw std::runtime_error("missing labeled rows for " + kStates[state]);
        }
        std::sort(state_values.begin(), state_values.end());
        const std::size_t middle = state_values.size() / 2;
        medians[state] = state_values.size() % 2 == 0
            ? (state_values[middle - 1] + state_values[middle]) / 2.0
            : state_values[middle];
    }
    return medians;
}

int component_index(const Row& row, int state,
                    const std::array<double, kStateCount>& medians) {
    return row.features[1] <= medians[state] ? 0 : 1;
}

SupervisedStats collect_supervised_stats(const TraceMap& traces) {
    SupervisedStats stats;
    stats.sequences = static_cast<int>(traces.size());
    initialize_duration_counts(&stats.continue_counts);
    initialize_duration_counts(&stats.exit_counts);
    const std::array<double, kStateCount> medians = component_medians(traces);
    for (const auto& [sequence_id, rows] : traces) {
        (void)sequence_id;
        if (rows.empty()) {
            throw std::runtime_error("empty training sequence");
        }
        stats.start_counts[state_index(rows.front().state)] += 1.0;
        int previous_state = -1;
        int raw_age = 0;
        for (std::size_t index = 0; index < rows.size(); ++index) {
            const Row& row = rows[index];
            const int state = state_index(row.state);
            raw_age = state == previous_state ? raw_age + 1 : 1;
            previous_state = state;
            const int age = std::min(raw_age, kDurationCaps[state]);
            const int component = component_index(row, state, medians);
            stats.component_weight[state][component] += 1.0;
            stats.rows += 1;
            for (int feature = 0; feature < kFeatureCount; ++feature) {
                stats.sums[state][component][feature] += row.features[feature];
                for (int other_feature = 0; other_feature < kFeatureCount; ++other_feature) {
                    stats.cross_sums[state][component][feature][other_feature] +=
                        row.features[feature] * row.features[other_feature];
                }
            }
            if (index + 1 < rows.size()) {
                const int next_state = state_index(rows[index + 1].state);
                if (next_state == state) {
                    stats.continue_counts[state][age - 1] += 1.0;
                } else {
                    stats.exit_counts[state][age - 1] += 1.0;
                    stats.destination_counts[state][next_state] += 1.0;
                }
            }
        }
    }
    return stats;
}

ExpectedStats empty_expected_stats() {
    ExpectedStats stats;
    initialize_duration_counts(&stats.continue_counts);
    initialize_duration_counts(&stats.exit_counts);
    return stats;
}

Model reestimate_model(
    const SupervisedStats& labeled,
    const ExpectedStats& expected,
    int adaptation_sequences,
    int adaptation_rows) {
    Model model;
    model.training_sequences = labeled.sequences;
    model.training_rows = labeled.rows;
    model.adaptation_sequences = adaptation_sequences;
    model.adaptation_rows = adaptation_rows;
    const double start_total = static_cast<double>(labeled.sequences + adaptation_sequences) +
        kStartAlpha * static_cast<double>(kStateCount);
    for (int state = 0; state < kStateCount; ++state) {
        double state_weight = 0.0;
        for (int component = 0; component < kComponentCount; ++component) {
            state_weight += labeled.component_weight[state][component] +
                expected.component_weight[state][component];
        }
        if (!(state_weight > 0.0)) {
            throw std::runtime_error("model has no weight for " + kStates[state]);
        }
        model.start_probability[state] =
            (labeled.start_counts[state] + expected.start_counts[state] + kStartAlpha) /
            start_total;
        model.duration_continue_probability[state].resize(kDurationCaps[state]);
        for (int age = 0; age < kDurationCaps[state]; ++age) {
            const double continue_count = labeled.continue_counts[state][age] +
                expected.continue_counts[state][age];
            const double exit_count = labeled.exit_counts[state][age] +
                expected.exit_counts[state][age];
            model.duration_continue_probability[state][age] =
                (continue_count + kDurationAlpha) /
                (continue_count + exit_count + 2.0 * kDurationAlpha);
        }
        double destination_total = 0.0;
        for (int next_state = 0; next_state < kStateCount; ++next_state) {
            if (next_state != state) {
                destination_total += labeled.destination_counts[state][next_state] +
                    expected.destination_counts[state][next_state];
            }
        }
        const double destination_denominator = destination_total +
            kDestinationAlpha * static_cast<double>(kStateCount - 1);
        for (int next_state = 0; next_state < kStateCount; ++next_state) {
            if (next_state != state) {
                model.exit_destination_probability[state][next_state] =
                    (labeled.destination_counts[state][next_state] +
                     expected.destination_counts[state][next_state] + kDestinationAlpha) /
                    destination_denominator;
            }
        }
        for (int component = 0; component < kComponentCount; ++component) {
            const double component_weight = labeled.component_weight[state][component] +
                expected.component_weight[state][component];
            if (!(component_weight > 0.0)) {
                throw std::runtime_error("model has no component weight for " + kStates[state]);
            }
            model.mixture_weight[state][component] =
                (component_weight + kMixtureAlpha) /
                (state_weight + kMixtureAlpha * static_cast<double>(kComponentCount));
            for (int feature = 0; feature < kFeatureCount; ++feature) {
                model.mean[state][component][feature] =
                    (labeled.sums[state][component][feature] +
                     expected.sums[state][component][feature]) / component_weight;
            }
            for (int feature = 0; feature < kFeatureCount; ++feature) {
                for (int other_feature = 0; other_feature < kFeatureCount; ++other_feature) {
                    const double second_moment =
                        (labeled.cross_sums[state][component][feature][other_feature] +
                         expected.cross_sums[state][component][feature][other_feature]) /
                        component_weight;
                    const double scatter = second_moment -
                        model.mean[state][component][feature] *
                        model.mean[state][component][other_feature];
                    model.covariance[state][component][feature][other_feature] =
                        feature == other_feature
                        ? scatter + kVarianceFloor
                        : (1.0 - kCovarianceShrinkage) * scatter;
                }
            }
        }
    }
    return model;
}

const std::vector<ExpandedState>& expanded_states() {
    static const std::vector<ExpandedState> states = [] {
        std::vector<ExpandedState> result;
        for (int state = 0; state < kStateCount; ++state) {
            for (int age = 1; age <= kDurationCaps[state]; ++age) {
                result.push_back({state, age});
            }
        }
        return result;
    }();
    return states;
}

int expanded_index(int wanted_state, int wanted_age) {
    const std::vector<ExpandedState>& states = expanded_states();
    for (std::size_t index = 0; index < states.size(); ++index) {
        if (states[index].state == wanted_state && states[index].age == wanted_age) {
            return static_cast<int>(index);
        }
    }
    throw std::runtime_error("invalid expanded state");
}

double component_log_probability(
    const Model& model, int state, int component, const Row& row) {
    std::array<std::array<double, kFeatureCount>, kFeatureCount> lower{};
    double log_determinant = 0.0;
    for (int row_index = 0; row_index < kFeatureCount; ++row_index) {
        for (int column_index = 0; column_index <= row_index; ++column_index) {
            double value = model.covariance[state][component][row_index][column_index];
            for (int inner = 0; inner < column_index; ++inner) {
                value -= lower[row_index][inner] * lower[column_index][inner];
            }
            if (row_index == column_index) {
                if (!(value > 0.0)) {
                    throw std::runtime_error("emission covariance is not positive definite");
                }
                lower[row_index][column_index] = std::sqrt(value);
                log_determinant += 2.0 * std::log(lower[row_index][column_index]);
            } else {
                lower[row_index][column_index] = value / lower[column_index][column_index];
            }
        }
    }
    std::array<double, kFeatureCount> solved{};
    double quadratic = 0.0;
    for (int row_index = 0; row_index < kFeatureCount; ++row_index) {
        double value = row.features[row_index] - model.mean[state][component][row_index];
        for (int inner = 0; inner < row_index; ++inner) {
            value -= lower[row_index][inner] * solved[inner];
        }
        solved[row_index] = value / lower[row_index][row_index];
        quadratic += solved[row_index] * solved[row_index];
    }
    const double dimensions = static_cast<double>(kFeatureCount);
    return std::log(model.mixture_weight[state][component]) +
        std::lgamma((kStudentDegreesOfFreedom + dimensions) / 2.0) -
        std::lgamma(kStudentDegreesOfFreedom / 2.0) -
        0.5 * (dimensions * std::log(kStudentDegreesOfFreedom * kPi) + log_determinant) -
        ((kStudentDegreesOfFreedom + dimensions) / 2.0) *
            std::log1p(quadratic / kStudentDegreesOfFreedom);
}

double emission_log_probability(const Model& model, int state, const Row& row) {
    const double first = component_log_probability(model, state, 0, row);
    const double second = component_log_probability(model, state, 1, row);
    const double maximum = std::max(first, second);
    return maximum + std::log(std::exp(first - maximum) + std::exp(second - maximum));
}

double transition_log_probability(
    const Model& model, const ExpandedState& from, const ExpandedState& to) {
    const double continue_probability =
        model.duration_continue_probability[from.state][from.age - 1];
    if (to.state == from.state) {
        const int expected_age = std::min(from.age + 1, kDurationCaps[from.state]);
        if (to.age != expected_age) {
            return kNegativeInfinity;
        }
        return std::log(continue_probability);
    }
    if (to.age != 1) {
        return kNegativeInfinity;
    }
    return std::log(1.0 - continue_probability) +
        std::log(model.exit_destination_probability[from.state][to.state]);
}

double logsumexp(const std::vector<double>& values) {
    double maximum = kNegativeInfinity;
    for (double value : values) {
        maximum = std::max(maximum, value);
    }
    if (!std::isfinite(maximum)) {
        return kNegativeInfinity;
    }
    double sum = 0.0;
    for (double value : values) {
        if (std::isfinite(value)) {
            sum += std::exp(value - maximum);
        }
    }
    return maximum + std::log(sum);
}

ForwardBackward forward_backward(const Model& model, const std::vector<Row>& rows) {
    if (rows.empty()) {
        throw std::runtime_error("cannot process an empty sequence");
    }
    const std::vector<ExpandedState>& expanded = expanded_states();
    const int expanded_count = static_cast<int>(expanded.size());
    const int length = static_cast<int>(rows.size());
    ForwardBackward result;
    result.forward.assign(length, std::vector<double>(expanded_count, kNegativeInfinity));
    for (int state = 0; state < kStateCount; ++state) {
        const int index = expanded_index(state, 1);
        result.forward[0][index] = std::log(model.start_probability[state]) +
            emission_log_probability(model, state, rows[0]);
    }
    for (int row_index = 1; row_index < length; ++row_index) {
        for (int next = 0; next < expanded_count; ++next) {
            std::vector<double> candidates;
            candidates.reserve(expanded_count);
            for (int previous = 0; previous < expanded_count; ++previous) {
                const double edge =
                    transition_log_probability(model, expanded[previous], expanded[next]);
                if (std::isfinite(edge) && std::isfinite(result.forward[row_index - 1][previous])) {
                    candidates.push_back(result.forward[row_index - 1][previous] + edge);
                }
            }
            const double total = logsumexp(candidates);
            if (std::isfinite(total)) {
                result.forward[row_index][next] = total +
                    emission_log_probability(model, expanded[next].state, rows[row_index]);
            }
        }
    }
    result.backward.assign(length, std::vector<double>(expanded_count, 0.0));
    for (int row_index = length - 2; row_index >= 0; --row_index) {
        for (int previous = 0; previous < expanded_count; ++previous) {
            std::vector<double> candidates;
            candidates.reserve(expanded_count);
            for (int next = 0; next < expanded_count; ++next) {
                const double edge =
                    transition_log_probability(model, expanded[previous], expanded[next]);
                if (std::isfinite(edge)) {
                    candidates.push_back(edge +
                        emission_log_probability(model, expanded[next].state, rows[row_index + 1]) +
                        result.backward[row_index + 1][next]);
                }
            }
            result.backward[row_index][previous] = logsumexp(candidates);
        }
    }
    result.log_likelihood = logsumexp(result.forward[length - 1]);
    if (!std::isfinite(result.log_likelihood)) {
        throw std::runtime_error("forward-backward found no valid path");
    }
    return result;
}

ExpectedStats expectation_step(const Model& model, const TraceMap& traces) {
    ExpectedStats stats = empty_expected_stats();
    const std::vector<ExpandedState>& expanded = expanded_states();
    const int expanded_count = static_cast<int>(expanded.size());
    for (const auto& [sequence_id, rows] : traces) {
        (void)sequence_id;
        const ForwardBackward calculation = forward_backward(model, rows);
        stats.log_likelihood += calculation.log_likelihood;
        for (std::size_t row_index = 0; row_index < rows.size(); ++row_index) {
            std::vector<double> expanded_mass(expanded_count, 0.0);
            std::array<double, kStateCount> state_mass{};
            double total_mass = 0.0;
            for (int index = 0; index < expanded_count; ++index) {
                const double log_mass = calculation.forward[row_index][index] +
                    calculation.backward[row_index][index] - calculation.log_likelihood;
                if (std::isfinite(log_mass)) {
                    expanded_mass[index] = std::exp(log_mass);
                    state_mass[expanded[index].state] += expanded_mass[index];
                }
            }
            for (double mass : state_mass) {
                total_mass += mass;
            }
            if (!(total_mass > 0.0)) {
                throw std::runtime_error("adaptation posterior has no mass");
            }
            for (int state = 0; state < kStateCount; ++state) {
                const double gamma = state_mass[state] / total_mass;
                const double state_emission =
                    emission_log_probability(model, state, rows[row_index]);
                for (int component = 0; component < kComponentCount; ++component) {
                    const double responsibility = std::exp(
                        component_log_probability(model, state, component, rows[row_index]) -
                        state_emission);
                    const double component_mass = gamma * responsibility;
                    stats.component_weight[state][component] += component_mass;
                    for (int feature = 0; feature < kFeatureCount; ++feature) {
                        stats.sums[state][component][feature] +=
                            component_mass * rows[row_index].features[feature];
                        for (int other_feature = 0; other_feature < kFeatureCount;
                             ++other_feature) {
                            stats.cross_sums[state][component][feature][other_feature] +=
                                component_mass * rows[row_index].features[feature] *
                                rows[row_index].features[other_feature];
                        }
                    }
                }
            }
            if (row_index == 0) {
                for (int index = 0; index < expanded_count; ++index) {
                    if (expanded[index].age == 1) {
                        stats.start_counts[expanded[index].state] +=
                            expanded_mass[index] / total_mass;
                    }
                }
            }
        }
        for (std::size_t row_index = 0; row_index + 1 < rows.size(); ++row_index) {
            for (int previous = 0; previous < expanded_count; ++previous) {
                for (int next = 0; next < expanded_count; ++next) {
                    const double edge = transition_log_probability(
                        model, expanded[previous], expanded[next]);
                    if (!std::isfinite(edge)) {
                        continue;
                    }
                    const double log_xi = calculation.forward[row_index][previous] + edge +
                        emission_log_probability(model, expanded[next].state, rows[row_index + 1]) +
                        calculation.backward[row_index + 1][next] - calculation.log_likelihood;
                    if (!std::isfinite(log_xi)) {
                        continue;
                    }
                    const double xi = std::exp(log_xi);
                    const ExpandedState& from = expanded[previous];
                    const ExpandedState& to = expanded[next];
                    if (from.state == to.state) {
                        stats.continue_counts[from.state][from.age - 1] += xi;
                    } else {
                        stats.exit_counts[from.state][from.age - 1] += xi;
                        stats.destination_counts[from.state][to.state] += xi;
                    }
                }
            }
        }
    }
    return stats;
}

Model train_and_adapt(const TraceMap& train, const TraceMap& adaptation) {
    const SupervisedStats labeled = collect_supervised_stats(train);
    int adaptation_rows = 0;
    for (const auto& [sequence_id, rows] : adaptation) {
        (void)sequence_id;
        adaptation_rows += static_cast<int>(rows.size());
    }
    const int adaptation_sequences = static_cast<int>(adaptation.size());
    Model model = reestimate_model(labeled, empty_expected_stats(), 0, 0);
    std::vector<double> likelihood_history;
    likelihood_history.reserve(kAdaptationRounds);
    for (int round = 0; round < kAdaptationRounds; ++round) {
        const ExpectedStats expected = expectation_step(model, adaptation);
        likelihood_history.push_back(expected.log_likelihood);
        model = reestimate_model(labeled, expected, adaptation_sequences, adaptation_rows);
    }
    model.adaptation_iterations = kAdaptationRounds;
    model.adaptation_log_likelihood = likelihood_history;
    return model;
}

DecodedSequence decode_sequence(const Model& model, const std::vector<Row>& rows) {
    if (rows.empty()) {
        throw std::runtime_error("cannot decode an empty sequence");
    }
    const std::vector<ExpandedState>& expanded = expanded_states();
    const int expanded_count = static_cast<int>(expanded.size());
    const int length = static_cast<int>(rows.size());
    std::vector<std::vector<double>> viterbi(
        length, std::vector<double>(expanded_count, kNegativeInfinity));
    std::vector<std::vector<int>> predecessor(length, std::vector<int>(expanded_count, 0));
    for (int state = 0; state < kStateCount; ++state) {
        const int index = expanded_index(state, 1);
        viterbi[0][index] = std::log(model.start_probability[state]) +
            emission_log_probability(model, state, rows[0]);
    }
    for (int row_index = 1; row_index < length; ++row_index) {
        for (int next = 0; next < expanded_count; ++next) {
            double best = kNegativeInfinity;
            int best_previous = 0;
            for (int previous = 0; previous < expanded_count; ++previous) {
                const double edge =
                    transition_log_probability(model, expanded[previous], expanded[next]);
                if (!std::isfinite(edge) || !std::isfinite(viterbi[row_index - 1][previous])) {
                    continue;
                }
                const double candidate = viterbi[row_index - 1][previous] + edge;
                if (candidate > best + kTieEpsilon) {
                    best = candidate;
                    best_previous = previous;
                }
            }
            if (std::isfinite(best)) {
                viterbi[row_index][next] = best +
                    emission_log_probability(model, expanded[next].state, rows[row_index]);
                predecessor[row_index][next] = best_previous;
            }
        }
    }
    double best_final = kNegativeInfinity;
    int final_expanded_state = 0;
    for (int index = 0; index < expanded_count; ++index) {
        if (viterbi[length - 1][index] > best_final + kTieEpsilon) {
            best_final = viterbi[length - 1][index];
            final_expanded_state = index;
        }
    }
    if (!std::isfinite(best_final)) {
        throw std::runtime_error("decoder found no valid path");
    }
    std::vector<int> expanded_path(length, 0);
    expanded_path[length - 1] = final_expanded_state;
    for (int row_index = length - 1; row_index > 0; --row_index) {
        expanded_path[row_index - 1] = predecessor[row_index][expanded_path[row_index]];
    }
    const ForwardBackward calculation = forward_backward(model, rows);
    DecodedSequence decoded;
    decoded.log_likelihood = calculation.log_likelihood;
    decoded.viterbi_states.reserve(length);
    for (int index : expanded_path) {
        decoded.viterbi_states.push_back(expanded[index].state);
    }
    decoded.posterior.resize(length);
    decoded.entropy.resize(length, 0.0);
    for (int row_index = 0; row_index < length; ++row_index) {
        std::array<double, kStateCount> state_mass{};
        for (int index = 0; index < expanded_count; ++index) {
            const double log_mass = calculation.forward[row_index][index] +
                calculation.backward[row_index][index] - decoded.log_likelihood;
            if (std::isfinite(log_mass)) {
                state_mass[expanded[index].state] += std::exp(log_mass);
            }
        }
        double total_mass = 0.0;
        for (double mass : state_mass) {
            total_mass += mass;
        }
        if (!(total_mass > 0.0)) {
            throw std::runtime_error("posterior has no mass");
        }
        for (int state = 0; state < kStateCount; ++state) {
            decoded.posterior[row_index][state] = state_mass[state] / total_mass;
            if (decoded.posterior[row_index][state] > 0.0) {
                decoded.entropy[row_index] -= decoded.posterior[row_index][state] *
                    std::log(decoded.posterior[row_index][state]);
            }
        }
    }
    return decoded;
}

void write_model_json(const Model& model, const fs::path& out_dir) {
    std::ofstream output(out_dir / "model.json");
    if (!output) {
        throw std::runtime_error("cannot write model.json");
    }
    output << std::setprecision(17);
    output << "{\n  \"states\": [\"quiet\", \"flow_limited\", \"apnea\"],\n";
    output << "  \"features\": [\"airflow_flatness\", \"spo2_drop\", \"resp_pause\", \"body_motion\"],\n";
    output << "  \"training_sequences\": " << model.training_sequences << ",\n";
    output << "  \"training_rows\": " << model.training_rows << ",\n";
    output << "  \"adaptation_sequences\": " << model.adaptation_sequences << ",\n";
    output << "  \"adaptation_rows\": " << model.adaptation_rows << ",\n";
    output << "  \"adaptation_iterations\": " << model.adaptation_iterations << ",\n";
    output << "  \"emission_degrees_of_freedom\": " << kStudentDegreesOfFreedom << ",\n";
    output << "  \"adaptation_log_likelihood\": [";
    for (std::size_t index = 0; index < model.adaptation_log_likelihood.size(); ++index) {
        if (index != 0) {
            output << ", ";
        }
        output << model.adaptation_log_likelihood[index];
    }
    output << "],\n  \"start_probability\": {";
    for (int state = 0; state < kStateCount; ++state) {
        if (state != 0) {
            output << ", ";
        }
        output << "\"" << kStates[state] << "\": " << model.start_probability[state];
    }
    output << "},\n  \"duration_cap\": {";
    for (int state = 0; state < kStateCount; ++state) {
        if (state != 0) {
            output << ", ";
        }
        output << "\"" << kStates[state] << "\": " << kDurationCaps[state];
    }
    output << "},\n  \"duration_continue_probability\": {\n";
    for (int state = 0; state < kStateCount; ++state) {
        output << "    \"" << kStates[state] << "\": {";
        for (int age = 0; age < kDurationCaps[state]; ++age) {
            if (age != 0) {
                output << ", ";
            }
            output << "\"" << age + 1 << "\": "
                   << model.duration_continue_probability[state][age];
        }
        output << "}" << (state == kStateCount - 1 ? "\n" : ",\n");
    }
    output << "  },\n  \"exit_destination_probability\": {\n";
    for (int state = 0; state < kStateCount; ++state) {
        output << "    \"" << kStates[state] << "\": {";
        bool first = true;
        for (int next_state = 0; next_state < kStateCount; ++next_state) {
            if (next_state == state) {
                continue;
            }
            if (!first) {
                output << ", ";
            }
            first = false;
            output << "\"" << kStates[next_state] << "\": "
                   << model.exit_destination_probability[state][next_state];
        }
        output << "}" << (state == kStateCount - 1 ? "\n" : ",\n");
    }
    output << "  },\n  \"emission\": {\n";
    for (int state = 0; state < kStateCount; ++state) {
        output << "    \"" << kStates[state] << "\": {\"mixture_weight\": {";
        for (int component = 0; component < kComponentCount; ++component) {
            if (component != 0) {
                output << ", ";
            }
            output << "\"" << component << "\": "
                   << model.mixture_weight[state][component];
        }
        output << "}, \"components\": {";
        for (int component = 0; component < kComponentCount; ++component) {
            if (component != 0) {
                output << ", ";
            }
            output << "\"" << component << "\": {\"mean\": {";
            for (int feature = 0; feature < kFeatureCount; ++feature) {
                if (feature != 0) {
                    output << ", ";
                }
                output << "\"" << kFeatures[feature] << "\": "
                       << model.mean[state][component][feature];
            }
            output << "}, \"covariance\": {";
            for (int feature = 0; feature < kFeatureCount; ++feature) {
                if (feature != 0) {
                    output << ", ";
                }
                output << "\"" << kFeatures[feature] << "\": {";
                for (int other_feature = 0; other_feature < kFeatureCount; ++other_feature) {
                    if (other_feature != 0) {
                        output << ", ";
                    }
                    output << "\"" << kFeatures[other_feature] << "\": "
                           << model.covariance[state][component][feature][other_feature];
                }
                output << "}";
            }
            output << "}}";
        }
        output << "}}" << (state == kStateCount - 1 ? "\n" : ",\n");
    }
    output << "  }\n}\n";
}

void write_validation_metrics(const Model& model, const TraceMap& traces, const fs::path& out_dir) {
    std::array<std::array<int, kStateCount>, kStateCount> confusion{};
    int correct = 0;
    int total_rows = 0;
    double negative_log_likelihood = 0.0;
    double entropy_sum = 0.0;
    for (const auto& [sequence_id, rows] : traces) {
        (void)sequence_id;
        const DecodedSequence decoded = decode_sequence(model, rows);
        negative_log_likelihood -= decoded.log_likelihood;
        for (std::size_t index = 0; index < rows.size(); ++index) {
            const int actual = state_index(rows[index].state);
            const int predicted = decoded.viterbi_states[index];
            confusion[actual][predicted] += 1;
            correct += actual == predicted ? 1 : 0;
            total_rows += 1;
            entropy_sum += decoded.entropy[index];
        }
    }
    std::array<double, kStateCount> f1{};
    for (int state = 0; state < kStateCount; ++state) {
        const int true_positive = confusion[state][state];
        int predicted_total = 0;
        int actual_total = 0;
        for (int other = 0; other < kStateCount; ++other) {
            predicted_total += confusion[other][state];
            actual_total += confusion[state][other];
        }
        const double precision = predicted_total == 0
            ? 0.0 : static_cast<double>(true_positive) / predicted_total;
        const double recall = actual_total == 0
            ? 0.0 : static_cast<double>(true_positive) / actual_total;
        f1[state] = precision + recall == 0.0
            ? 0.0 : 2.0 * precision * recall / (precision + recall);
    }
    const double macro_f1 = (f1[0] + f1[1] + f1[2]) / kStateCount;
    std::ofstream output(out_dir / "validation_metrics.json");
    if (!output) {
        throw std::runtime_error("cannot write validation_metrics.json");
    }
    output << std::setprecision(17);
    output << "{\n  \"accuracy\": " << static_cast<double>(correct) / total_rows << ",\n";
    output << "  \"macro_f1\": " << macro_f1 << ",\n";
    output << "  \"mean_negative_log_likelihood\": "
           << negative_log_likelihood / total_rows << ",\n";
    output << "  \"mean_posterior_entropy\": " << entropy_sum / total_rows << ",\n";
    output << "  \"confusion\": {\n";
    for (int actual = 0; actual < kStateCount; ++actual) {
        output << "    \"" << kStates[actual] << "\": {";
        for (int predicted = 0; predicted < kStateCount; ++predicted) {
            if (predicted != 0) {
                output << ", ";
            }
            output << "\"" << kStates[predicted] << "\": "
                   << confusion[actual][predicted];
        }
        output << "}" << (actual == kStateCount - 1 ? "\n" : ",\n");
    }
    output << "  }\n}\n";
}

void write_inference_outputs(const Model& model, const TraceMap& traces, const fs::path& out_dir) {
    std::ofstream predictions(out_dir / "predictions.csv");
    std::ofstream posterior(out_dir / "posterior.csv");
    std::ofstream events(out_dir / "apnea_events.csv");
    if (!predictions || !posterior || !events) {
        throw std::runtime_error("cannot open inference output files");
    }
    predictions << "sequence_id,t,predicted_state\n";
    posterior << std::setprecision(17)
              << "sequence_id,t,quiet_posterior,flow_limited_posterior,apnea_posterior,entropy\n";
    events << std::setprecision(17)
           << "sequence_id,start_t,end_t,length,mean_spo2_drop,max_resp_pause,mean_apnea_posterior,severity,preceding_state\n";
    const int apnea = state_index("apnea");
    for (const auto& [sequence_id, rows] : traces) {
        const DecodedSequence decoded = decode_sequence(model, rows);
        for (std::size_t index = 0; index < rows.size(); ++index) {
            predictions << sequence_id << ',' << rows[index].t << ','
                        << kStates[decoded.viterbi_states[index]] << '\n';
            posterior << sequence_id << ',' << rows[index].t;
            for (int state = 0; state < kStateCount; ++state) {
                posterior << ',' << decoded.posterior[index][state];
            }
            posterior << ',' << decoded.entropy[index] << '\n';
        }
        std::size_t index = 0;
        while (index < rows.size()) {
            if (decoded.viterbi_states[index] != apnea) {
                index += 1;
                continue;
            }
            const std::size_t start = index;
            double spo2_sum = 0.0;
            double posterior_sum = 0.0;
            double max_pause = rows[index].features[2];
            while (index < rows.size() && decoded.viterbi_states[index] == apnea) {
                spo2_sum += rows[index].features[1];
                posterior_sum += decoded.posterior[index][apnea];
                max_pause = std::max(max_pause, rows[index].features[2]);
                index += 1;
            }
            const std::size_t length = index - start;
            if (length < 2) {
                continue;
            }
            const double mean_apnea_posterior = posterior_sum / length;
            const bool high = length >= 3 || max_pause >= 15.0 ||
                mean_apnea_posterior >= 0.85;
            events << sequence_id << ',' << rows[start].t << ',' << rows[index - 1].t
                   << ',' << length << ',' << spo2_sum / length << ',' << max_pause << ','
                   << mean_apnea_posterior << ',' << (high ? "high" : "watch") << ','
                   << (start == 0 ? "start" : kStates[decoded.viterbi_states[start - 1]])
                   << '\n';
        }
    }
}

Arguments parse_arguments(int argc, char* argv[]) {
    if (argc != 11) {
        throw std::runtime_error(
            "expected --train --adapt --validation --infer --out-dir arguments");
    }
    Arguments arguments;
    for (int index = 1; index < argc; index += 2) {
        const std::string flag = argv[index];
        const fs::path value = argv[index + 1];
        if (flag == "--train") {
            arguments.train_dir = value;
        } else if (flag == "--adapt") {
            arguments.adaptation_dir = value;
        } else if (flag == "--validation") {
            arguments.validation_dir = value;
        } else if (flag == "--infer") {
            arguments.inference_dir = value;
        } else if (flag == "--out-dir") {
            arguments.out_dir = value;
        } else {
            throw std::runtime_error("unknown argument: " + flag);
        }
    }
    if (arguments.train_dir.empty() || arguments.adaptation_dir.empty() ||
        arguments.validation_dir.empty() || arguments.inference_dir.empty() ||
        arguments.out_dir.empty()) {
        throw std::runtime_error("all five directory arguments are required");
    }
    return arguments;
}

}  // namespace

int main(int argc, char* argv[]) {
    try {
        const Arguments arguments = parse_arguments(argc, argv);
        const TraceMap train = load_traces(arguments.train_dir, true);
        const TraceMap adaptation = load_traces(arguments.adaptation_dir, false);
        const TraceMap validation = load_traces(arguments.validation_dir, true);
        const TraceMap inference = load_traces(arguments.inference_dir, false);
        const Model model = train_and_adapt(train, adaptation);
        fs::create_directories(arguments.out_dir);
        write_model_json(model, arguments.out_dir);
        write_validation_metrics(model, validation, arguments.out_dir);
        write_inference_outputs(model, inference, arguments.out_dir);
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << '\n';
        return 1;
    }
    return 0;
}
