<?php

if ($argc !== 2) {
    fwrite(STDERR, "Usage: php /app/migrations/train_naive_bayes.php /app/database/spam_lab.sqlite\n");
    exit(2);
}

fwrite(STDERR, "Training migration is not implemented yet.\n");
exit(1);
