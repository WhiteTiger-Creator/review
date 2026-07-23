"""Documents stdlib modules the offline verifier may use for independent checks."""

from __future__ import annotations

import duckdb
import hashlib
import jsonschema
import random
import tomllib
import unicodedata

DERIVATION_SURFACE = (
    duckdb.__name__,
    hashlib.__name__,
    jsonschema.__name__,
    random.__name__,
    tomllib.__name__,
    unicodedata.__name__,
)
