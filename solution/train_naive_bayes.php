<?php

if ($argc !== 2) {
    fwrite(STDERR, "Usage: php /app/migrations/train_naive_bayes.php /app/database/spam_lab.sqlite\n");
    exit(2);
}

$dbPath = $argv[1];
$pdo = new PDO("sqlite:" . $dbPath);
$pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
$pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);

function tokens_for_text(string $text): array
{
    $lower = strtolower($text);
    preg_match_all('/[a-z0-9]+/', $lower, $matches);
    $tokens = [];
    foreach ($matches[0] as $token) {
        if (strlen($token) >= 2) {
            $tokens[] = $token;
        }
    }
    return $tokens;
}

function fixed12(float $value): string
{
    if (round($value, 12) == 0.0) {
        $value = 0.0;
    }
    return sprintf('%.12f', $value);
}

$rows = $pdo->query(
    "SELECT m.id, m.message_text, l.label, l.split
     FROM messages AS m
     JOIN labels AS l ON l.message_id = m.id
     ORDER BY m.id"
)->fetchAll();

$labels = ["ham", "spam"];
$trainDocs = ["ham" => [], "spam" => []];
$validation = [];
foreach ($rows as $row) {
    if ($row["split"] === "train") {
        $trainDocs[$row["label"]][] = tokens_for_text($row["message_text"]);
    } elseif ($row["split"] === "validation") {
        $validation[] = $row;
    }
}

$vocabSet = [];
foreach ($labels as $label) {
    foreach ($trainDocs[$label] as $docTokens) {
        foreach ($docTokens as $token) {
            $vocabSet[$token] = true;
        }
    }
}
$vocabulary = array_keys($vocabSet);
sort($vocabulary, SORT_STRING);
$tokenIds = [];
foreach ($vocabulary as $index => $token) {
    $tokenIds[$token] = $index + 1;
}
$vocabSize = count($vocabulary);

$classTokenCounts = ["ham" => [], "spam" => []];
$classTotalTokens = ["ham" => 0, "spam" => 0];
$documentCounts = [];
$totalCounts = [];
foreach ($labels as $label) {
    foreach ($trainDocs[$label] as $docTokens) {
        $seen = [];
        foreach ($docTokens as $token) {
            $classTokenCounts[$label][$token] = ($classTokenCounts[$label][$token] ?? 0) + 1;
            $classTotalTokens[$label]++;
            $totalCounts[$token] = ($totalCounts[$token] ?? 0) + 1;
            $seen[$token] = true;
        }
        foreach (array_keys($seen) as $token) {
            $documentCounts[$token] = ($documentCounts[$token] ?? 0) + 1;
        }
    }
}

$trainCount = count($trainDocs["ham"]) + count($trainDocs["spam"]);
if ($trainCount === 0 || $vocabSize === 0 || count($trainDocs["ham"]) === 0 || count($trainDocs["spam"]) === 0) {
    fwrite(STDERR, "Training data must contain both classes and at least one training token.\n");
    exit(1);
}

$logPriors = [];
foreach ($labels as $label) {
    $logPriors[$label] = log(count($trainDocs[$label]) / $trainCount);
}

$pdo->beginTransaction();
try {
    $pdo->exec("DELETE FROM validation_scores");
    $pdo->exec("DELETE FROM class_token_stats");
    $pdo->exec("DELETE FROM token_vocabulary");
    $pdo->exec("DELETE FROM model_metadata");

    $insertMeta = $pdo->prepare("INSERT INTO model_metadata (meta_key, meta_value) VALUES (?, ?)");
    $metadata = [
        "algorithm" => "multinomial_naive_bayes",
        "alpha" => "1.000000000000",
        "class_order" => "ham,spam",
        "tokenizer" => "ascii_alnum_min2_lower",
        "train_message_count" => (string) $trainCount,
        "validation_message_count" => (string) count($validation),
        "vocabulary_size" => (string) $vocabSize,
        "log_prior.ham" => fixed12($logPriors["ham"]),
        "log_prior.spam" => fixed12($logPriors["spam"]),
    ];
    ksort($metadata, SORT_STRING);
    foreach ($metadata as $key => $value) {
        $insertMeta->execute([$key, $value]);
    }

    $insertVocab = $pdo->prepare(
        "INSERT INTO token_vocabulary (token_id, token, document_count, total_count) VALUES (?, ?, ?, ?)"
    );
    foreach ($vocabulary as $token) {
        $insertVocab->execute([
            $tokenIds[$token],
            $token,
            $documentCounts[$token] ?? 0,
            $totalCounts[$token] ?? 0,
        ]);
    }

    $likelihoods = ["ham" => [], "spam" => []];
    $insertStats = $pdo->prepare(
        "INSERT INTO class_token_stats (label, token_id, token_count, log_likelihood) VALUES (?, ?, ?, ?)"
    );
    foreach ($labels as $label) {
        $denominator = $classTotalTokens[$label] + $vocabSize;
        foreach ($vocabulary as $token) {
            $count = $classTokenCounts[$label][$token] ?? 0;
            $logLikelihood = log(($count + 1.0) / $denominator);
            $likelihoods[$label][$token] = $logLikelihood;
            $insertStats->execute([$label, $tokenIds[$token], $count, fixed12($logLikelihood)]);
        }
    }

    $insertScore = $pdo->prepare(
        "INSERT INTO validation_scores
         (message_id, true_label, predicted_label, log_prob_ham, log_prob_spam, margin, correct)
         VALUES (?, ?, ?, ?, ?, ?, ?)"
    );
    foreach ($validation as $row) {
        $scores = ["ham" => $logPriors["ham"], "spam" => $logPriors["spam"]];
        foreach (tokens_for_text($row["message_text"]) as $token) {
            if (!array_key_exists($token, $tokenIds)) {
                continue;
            }
            foreach ($labels as $label) {
                $scores[$label] += $likelihoods[$label][$token];
            }
        }
        $predicted = $scores["spam"] > $scores["ham"] ? "spam" : "ham";
        $insertScore->execute([
            (int) $row["id"],
            $row["label"],
            $predicted,
            fixed12($scores["ham"]),
            fixed12($scores["spam"]),
            fixed12($scores["spam"] - $scores["ham"]),
            $predicted === $row["label"] ? 1 : 0,
        ]);
    }

    $pdo->commit();
} catch (Throwable $error) {
    $pdo->rollBack();
    throw $error;
}

echo json_encode([
    "train_message_count" => $trainCount,
    "validation_message_count" => count($validation),
    "vocabulary_size" => $vocabSize,
], JSON_UNESCAPED_SLASHES) . PHP_EOL;
