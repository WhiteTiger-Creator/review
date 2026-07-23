#!/bin/bash
set -euo pipefail

cp "$(dirname "$0")/train_naive_bayes.php" /app/migrations/train_naive_bayes.php
php /app/migrations/train_naive_bayes.php /app/database/spam_lab.sqlite
