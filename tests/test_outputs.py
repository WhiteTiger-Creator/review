import hashlib
import math
import re
import shutil
import sqlite3
import subprocess
from collections import Counter
from pathlib import Path

import pandas as pd


APP = Path("/app")
BASE_DB = APP / "database" / "spam_lab.sqlite"
MIGRATION = APP / "migrations" / "train_naive_bayes.php"
LABELS = ("ham", "spam")
TABLES = (
    "model_metadata",
    "token_vocabulary",
    "class_token_stats",
    "validation_scores",
)


def db_copy(tmp_path):
    target = tmp_path / "spam_lab.sqlite"
    shutil.copy2(BASE_DB, target)
    return target


def run_migration(db_path):
    result = subprocess.run(
        ["php", str(MIGRATION), str(db_path)],
        cwd=APP,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    assert result.returncode == 0, result.stdout
    return result.stdout


def tokenize(text):
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) >= 2]


def fixed12(value):
    rounded = round(value, 12)
    if rounded == 0:
        rounded = 0.0
    return f"{rounded:.12f}"


def load_training_rows(conn):
    return conn.execute(
        """
        SELECT m.id, m.message_text, l.label, l.split
        FROM messages AS m
        JOIN labels AS l ON l.message_id = m.id
        ORDER BY m.id
        """
    ).fetchall()


def expected_tables(db_path):
    conn = sqlite3.connect(db_path)
    rows = load_training_rows(conn)
    train = [row for row in rows if row[3] == "train"]
    validation = [row for row in rows if row[3] == "validation"]

    by_class = {label: [] for label in LABELS}
    for _message_id, text, label, _split in train:
        by_class[label].append(tokenize(text))

    vocabulary = sorted({token for docs in by_class.values() for doc in docs for token in doc})
    token_ids = {token: index + 1 for index, token in enumerate(vocabulary)}
    vocab_size = len(vocabulary)

    class_doc_counts = {label: len(by_class[label]) for label in LABELS}
    total_train = sum(class_doc_counts.values())
    class_token_counts = {label: Counter() for label in LABELS}
    class_total_tokens = {}
    document_counts = Counter()
    total_counts = Counter()

    for label in LABELS:
        for doc_tokens in by_class[label]:
            class_token_counts[label].update(doc_tokens)
            document_counts.update(set(doc_tokens))
            total_counts.update(doc_tokens)
        class_total_tokens[label] = sum(class_token_counts[label].values())

    metadata = {
        "algorithm": "multinomial_naive_bayes",
        "alpha": "1.000000000000",
        "class_order": "ham,spam",
        "tokenizer": "ascii_alnum_min2_lower",
        "train_message_count": str(total_train),
        "validation_message_count": str(len(validation)),
        "vocabulary_size": str(vocab_size),
    }
    for label in LABELS:
        metadata[f"log_prior.{label}"] = fixed12(math.log(class_doc_counts[label] / total_train))

    token_vocabulary = [
        {
            "token_id": token_ids[token],
            "token": token,
            "document_count": document_counts[token],
            "total_count": total_counts[token],
        }
        for token in vocabulary
    ]

    raw_likelihoods = {}
    class_token_stats = []
    for label in LABELS:
        denominator = class_total_tokens[label] + vocab_size
        for token in vocabulary:
            count = class_token_counts[label][token]
            raw_likelihood = math.log((count + 1.0) / denominator)
            raw_likelihoods[(label, token)] = raw_likelihood
            class_token_stats.append(
                {
                    "label": label,
                    "token_id": token_ids[token],
                    "token_count": count,
                    "log_likelihood": fixed12(raw_likelihood),
                }
            )

    priors = {label: math.log(class_doc_counts[label] / total_train) for label in LABELS}
    validation_scores = []
    for message_id, text, label, _split in validation:
        present_tokens = [token for token in tokenize(text) if token in token_ids]
        scores = {}
        for class_label in LABELS:
            score = priors[class_label]
            for token in present_tokens:
                score += raw_likelihoods[(class_label, token)]
            scores[class_label] = score
        predicted = "spam" if scores["spam"] > scores["ham"] else "ham"
        validation_scores.append(
            {
                "message_id": message_id,
                "true_label": label,
                "predicted_label": predicted,
                "log_prob_ham": fixed12(scores["ham"]),
                "log_prob_spam": fixed12(scores["spam"]),
                "margin": fixed12(scores["spam"] - scores["ham"]),
                "correct": 1 if predicted == label else 0,
            }
        )

    conn.close()
    return {
        "model_metadata": [{"meta_key": key, "meta_value": value} for key, value in sorted(metadata.items())],
        "token_vocabulary": token_vocabulary,
        "class_token_stats": class_token_stats,
        "validation_scores": sorted(validation_scores, key=lambda row: row["message_id"]),
    }


def table_frame(conn, table):
    return pd.read_sql_query(f"SELECT * FROM {table}", conn)


def sorted_checksum(frame):
    ordered = frame.sort_values(list(frame.columns)).reset_index(drop=True)
    csv = ordered.to_csv(index=False, lineterminator="\n")
    return hashlib.sha256(csv.encode()).hexdigest()


def expected_frame(rows):
    return pd.DataFrame(rows)


def assert_artifacts_match(db_path):
    expected = expected_tables(db_path)
    conn = sqlite3.connect(db_path)
    try:
        for table in TABLES:
            actual = table_frame(conn, table)
            want = expected_frame(expected[table])
            assert list(actual.columns) == list(want.columns), table
            assert sorted_checksum(actual) == sorted_checksum(want), table
    finally:
        conn.close()


def fetch_all(db_path, sql, params=()):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def execute_sql(db_path, statements):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(statements)
        conn.commit()
    finally:
        conn.close()


def checksums(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return {table: sorted_checksum(table_frame(conn, table)) for table in TABLES}
    finally:
        conn.close()


def test_baseline_training_artifacts_match_independent_reference(tmp_path):
    """The seeded database produces exact Naive Bayes artifacts recomputed from messages and labels."""
    db_path = db_copy(tmp_path)
    run_migration(db_path)
    assert_artifacts_match(db_path)


def test_tokenization_counts_repeated_tokens_and_excludes_validation_only_terms(tmp_path):
    """Vocabulary statistics use repeated training tokens and ignore words that appear only in validation rows."""
    db_path = db_copy(tmp_path)
    run_migration(db_path)
    rows = fetch_all(
        db_path,
        """
        SELECT token, document_count, total_count
        FROM token_vocabulary
        WHERE token IN ('bonus', 'today', 'notebook')
        ORDER BY token
        """,
    )
    assert rows == [("bonus", 4, 6), ("today", 1, 1)]


def test_smoothed_class_likelihoods_are_complete_for_both_classes(tmp_path):
    """Every vocabulary token has ham and spam smoothed likelihood rows with the documented class order."""
    db_path = db_copy(tmp_path)
    run_migration(db_path)
    vocab_count = fetch_all(db_path, "SELECT COUNT(*) FROM token_vocabulary")[0][0]
    rows = fetch_all(
        db_path,
        """
        SELECT label, COUNT(*), MIN(log_likelihood), MAX(log_likelihood)
        FROM class_token_stats
        GROUP BY label
        ORDER BY label
        """,
    )
    assert rows[0][0] == "ham"
    assert rows[1][0] == "spam"
    assert rows[0][1] == vocab_count
    assert rows[1][1] == vocab_count
    assert_artifacts_match(db_path)


def test_validation_scores_apply_model_scores_and_ham_tie_break(tmp_path):
    """Validation scoring uses model log scores and chooses ham when a no-token example ties."""
    db_path = db_copy(tmp_path)
    execute_sql(
        db_path,
        """
        INSERT INTO messages (id, message_text) VALUES (50, 'x I a!');
        INSERT INTO labels (message_id, label, split) VALUES (50, 'spam', 'validation');
        """,
    )
    run_migration(db_path)
    assert_artifacts_match(db_path)
    tied = fetch_all(
        db_path,
        """
        SELECT predicted_label, log_prob_ham, log_prob_spam, margin, correct
        FROM validation_scores
        WHERE message_id = 50
        """,
    )
    assert tied == [("ham", "-0.693147180560", "-0.693147180560", "0.000000000000", 0)]


def test_rerun_replaces_stale_artifact_rows_without_changing_seed_tables(tmp_path):
    """A second run removes old model rows and leaves the source message and label tables intact."""
    db_path = db_copy(tmp_path)
    before_sources = checksums_for_sources(db_path)
    run_migration(db_path)
    first = checksums(db_path)
    execute_sql(
        db_path,
        """
        INSERT OR REPLACE INTO model_metadata (meta_key, meta_value) VALUES ('stale', 'row');
        INSERT OR REPLACE INTO token_vocabulary (token_id, token, document_count, total_count)
            VALUES (9999, 'staletoken', 9, 9);
        INSERT OR REPLACE INTO validation_scores
            (message_id, true_label, predicted_label, log_prob_ham, log_prob_spam, margin, correct)
            VALUES (9999, 'spam', 'spam', '0.000000000000', '0.000000000000', '0.000000000000', 1);
        """,
    )
    run_migration(db_path)
    assert checksums(db_path) == first
    assert checksums_for_sources(db_path) == before_sources


def checksums_for_sources(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return {
            "messages": sorted_checksum(pd.read_sql_query("SELECT * FROM messages", conn)),
            "labels": sorted_checksum(pd.read_sql_query("SELECT * FROM labels", conn)),
        }
    finally:
        conn.close()


def test_dynamic_training_mutation_retrains_counts_likelihoods_and_scores(tmp_path):
    """Verifier-side message changes force the migration to retrain instead of replaying fixed artifacts."""
    db_path = db_copy(tmp_path)
    execute_sql(
        db_path,
        """
        INSERT INTO messages (id, message_text) VALUES
            (60, 'Orbit orbit ORBIT launch bonus 99 99'),
            (61, 'Orbit meeting agenda 99 notes'),
            (62, 'Launch bonus orbit now'),
            (63, 'quasaronly validation token never trained');
        INSERT INTO labels (message_id, label, split) VALUES
            (60, 'spam', 'train'),
            (61, 'ham', 'train'),
            (62, 'spam', 'validation'),
            (63, 'ham', 'validation');
        """,
    )
    run_migration(db_path)
    assert_artifacts_match(db_path)
    rows = fetch_all(
        db_path,
        """
        SELECT token, document_count, total_count
        FROM token_vocabulary
        WHERE token IN ('orbit', '99', 'quasaronly')
        ORDER BY token
        """,
    )
    assert rows == [("99", 2, 3), ("orbit", 2, 4)]


def test_metadata_tracks_current_training_shape_after_later_successful_rerun(tmp_path):
    """Metadata counts and priors refresh when additional labeled training rows appear later."""
    db_path = db_copy(tmp_path)
    run_migration(db_path)
    execute_sql(
        db_path,
        """
        INSERT INTO messages (id, message_text) VALUES
            (70, 'Calendar notes agenda review'),
            (71, 'Prize refund bonus urgent');
        INSERT INTO labels (message_id, label, split) VALUES
            (70, 'ham', 'train'),
            (71, 'spam', 'train');
        """,
    )
    run_migration(db_path)
    assert_artifacts_match(db_path)
    rows = dict(fetch_all(db_path, "SELECT meta_key, meta_value FROM model_metadata"))
    assert rows["train_message_count"] == "22"
    assert rows["validation_message_count"] == "4"
    assert rows["log_prior.ham"] == "-0.693147180560"
    assert rows["log_prior.spam"] == "-0.693147180560"
