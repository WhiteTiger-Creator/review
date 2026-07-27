"""Bounded N.N.N versions and =/^ requirements."""

from __future__ import annotations

import re
from dataclasses import dataclass

_VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
_REQ_RE = re.compile(r"^([=\^])(\d+\.\d+\.\d+)$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, order=True)
class Version:
    major: int
    minor: int
    patch: int

    @staticmethod
    def parse(text: str) -> Version:
        m = _VERSION_RE.fullmatch(text)
        if not m:
            raise ValueError(f"malformed version: {text}")
        return Version(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


@dataclass(frozen=True)
class Requirement:
    kind: str  # "=" or "^"
    version: Version

    @staticmethod
    def parse(text: str) -> Requirement:
        m = _REQ_RE.fullmatch(text)
        if not m:
            raise ValueError(f"malformed requirement: {text}")
        return Requirement(m.group(1), Version.parse(m.group(2)))

    def matches(self, candidate: Version) -> bool:
        if self.kind == "=":
            return candidate == self.version
        v = self.version
        if candidate < v:
            return False
        if v.major > 0:
            return candidate < Version(v.major + 1, 0, 0)
        if v.minor > 0:
            return candidate < Version(0, v.minor + 1, 0)
        return candidate < Version(0, 0, v.patch + 1)


def parse_sha256(text: str) -> str:
    if not _SHA_RE.fullmatch(text):
        raise ValueError(f"malformed sha256: {text}")
    return text
