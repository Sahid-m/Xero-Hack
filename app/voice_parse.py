"""Shared speech-to-amount parsing for voice write paths."""

from __future__ import annotations

import re

WORD_NUM: dict[str, int] = {
    "a": 1,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
    "hundred": 100,
    "thousand": 1000,
}

CONFIRM_RE = re.compile(
    r"\b(yes|yeah|yep|yup|go ahead|create them|do it|please|sure|ok|okay|that's fine|sounds good)\b",
    re.I,
)
DENY_RE = re.compile(r"\b(no|nope|don't|do not|cancel|stop|never mind)\b", re.I)


def parse_gbp(text: str) -> float | None:
    text = text.lower().strip()
    m = re.search(r"£\s*([\d,]+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1).replace(",", ""))
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*pounds?", text)
    if m:
        return float(m.group(1).replace(",", ""))
    cleaned = re.sub(r"\b(quid|pounds?|gbp|sterling)\b", "", text).strip()
    cleaned = cleaned.strip("—-., ")
    if cleaned and re.match(r"^[\d,]+(?:\.\d+)?$", cleaned):
        return float(cleaned.replace(",", ""))
    words = cleaned.split()
    total = 0
    current = 0
    for word in words:
        n = WORD_NUM.get(word)
        if n is None:
            continue
        if n == 100:
            current = max(current, 1) * 100
        elif n == 1000:
            current = max(current, 1) * 1000
            total += current
            current = 0
        else:
            current += n
    total += current
    return float(total) if total > 0 else None


def clean_tail(text: str) -> str:
    text = re.sub(r"\s*[—\-].*$", "", text, flags=re.I)
    text = re.sub(r"\s+(yes|go ahead|please|now)\b.*$", "", text, flags=re.I)
    return text.strip(" .,—-")
