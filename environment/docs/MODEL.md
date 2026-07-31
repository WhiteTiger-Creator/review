# Skiff lab model

Bodies move on a fixed timestep with constant downward acceleration.
Contact with solids and thin one-sided bands updates support. Short
timing windows around leaving support and recent presses decide when an
upward impulse applies.

Each report row records the lowest vertical sample (apex_y), hop totals,
and a quantized position footprint. Draft sketches under docs/drafts/
are outdated relative to this note.
