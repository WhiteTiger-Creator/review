PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS validation_scores;
DROP TABLE IF EXISTS class_token_stats;
DROP TABLE IF EXISTS token_vocabulary;
DROP TABLE IF EXISTS model_metadata;
DROP TABLE IF EXISTS labels;
DROP TABLE IF EXISTS messages;

CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    message_text TEXT NOT NULL
);

CREATE TABLE labels (
    message_id INTEGER PRIMARY KEY,
    label TEXT NOT NULL CHECK (label IN ('ham', 'spam')),
    split TEXT NOT NULL CHECK (split IN ('train', 'validation')),
    FOREIGN KEY (message_id) REFERENCES messages(id)
);

CREATE TABLE model_metadata (
    meta_key TEXT PRIMARY KEY,
    meta_value TEXT NOT NULL
);

CREATE TABLE token_vocabulary (
    token_id INTEGER PRIMARY KEY,
    token TEXT UNIQUE NOT NULL,
    document_count INTEGER NOT NULL,
    total_count INTEGER NOT NULL
);

CREATE TABLE class_token_stats (
    label TEXT NOT NULL,
    token_id INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    log_likelihood TEXT NOT NULL,
    PRIMARY KEY (label, token_id)
);

CREATE TABLE validation_scores (
    message_id INTEGER PRIMARY KEY,
    true_label TEXT NOT NULL,
    predicted_label TEXT NOT NULL,
    log_prob_ham TEXT NOT NULL,
    log_prob_spam TEXT NOT NULL,
    margin TEXT NOT NULL,
    correct INTEGER NOT NULL
);

INSERT INTO messages (id, message_text) VALUES
(1, 'Team reminder: project demo at 10am in room 402. Bring revised slides.'),
(2, 'Lunch moved to cafe 17; Alex will bring the receipts and agenda.'),
(3, 'Can you review the quarterly notes before the client call tomorrow?'),
(4, 'Your package arrived at reception; please pick it up before 6pm.'),
(5, 'Family dinner starts at seven, and mom asked for the salad recipe.'),
(6, 'The printer queue is stuck again; facilities opened ticket 3182.'),
(7, 'Board meeting minutes are attached for finance review and comments.'),
(8, 'Reminder that yoga class moved upstairs after the lobby cleanup.'),
(9, 'Please confirm the hotel booking for the research workshop next week.'),
(10, 'The release checklist passed; staging deploy waits for approval.'),
(11, 'Win cash now claim your exclusive prize bonus by texting WINNER.'),
(12, 'Cheap meds available today, guaranteed discount pharmacy offer.'),
(13, 'Urgent account alert: verify password to unlock your reward points.'),
(14, 'Congratulations selected user, claim free cruise tickets immediately.'),
(15, 'Limited loan approval, no credit check, cash deposited overnight.'),
(16, 'Earn money fast from home with secret bonus code and free trial.'),
(17, 'Final notice: payment overdue, click secure link to avoid penalty.'),
(18, 'Exclusive deal on luxury watches, buy now and receive bonus gift.'),
(19, 'Winner bonus bonus bonus claim cash prize before midnight.'),
(20, 'Verify your bank login for instant refund and account upgrade.'),
(21, 'The notebook backup finished after the encrypted drive mounted.'),
(22, 'Can we move the rehearsal to 3pm after the planning call?'),
(23, 'Claim urgent cash bonus and free reward today today today.'),
(24, 'Cheap loan offer approved instantly with no paperwork required.');

INSERT INTO labels (message_id, label, split) VALUES
(1, 'ham', 'train'),
(2, 'ham', 'train'),
(3, 'ham', 'train'),
(4, 'ham', 'train'),
(5, 'ham', 'train'),
(6, 'ham', 'train'),
(7, 'ham', 'train'),
(8, 'ham', 'train'),
(9, 'ham', 'train'),
(10, 'ham', 'train'),
(11, 'spam', 'train'),
(12, 'spam', 'train'),
(13, 'spam', 'train'),
(14, 'spam', 'train'),
(15, 'spam', 'train'),
(16, 'spam', 'train'),
(17, 'spam', 'train'),
(18, 'spam', 'train'),
(19, 'spam', 'train'),
(20, 'spam', 'train'),
(21, 'ham', 'validation'),
(22, 'ham', 'validation'),
(23, 'spam', 'validation'),
(24, 'spam', 'validation');
