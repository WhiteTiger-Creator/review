# Lab contract

Offline Soft-TPM lab. Seat must precede weave; weave must precede seal. Changing the arm list after seat without re-seating is rejected. Session-start alone is a false green.

NV live state under `/app/var` comes from seal. After damage, `lab recover` restores from the generation snapshot for the pinned epoch (or durable seed material). `lab replay` restores settle_view from that snapshot without re-running fold/pack.

Arms with underscores remain first-class when listed on `--arms`. Request order in settle_view must match the seated arm list.
