from __future__ import annotations

import re

_CHAR_REPLACEMENTS = {
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "º": "°",
    "˚": "°",
    "–": "-",
    "—": "-",
}


def normalize(text: str) -> str:
    if text is None:
        return ""

    for bad, good in _CHAR_REPLACEMENTS.items():
        text = text.replace(bad, good)

    text = re.sub(r"\bDEGREES?\b", "°", text, flags=re.IGNORECASE)
    text = re.sub(r"\bMINUTES?\b", "'", text, flags=re.IGNORECASE)
    text = re.sub(r"\bSECONDS?\b", '"', text, flags=re.IGNORECASE)

    text = re.sub(r"(?<=\d)\s+°", "°", text)
    text = re.sub(r"°\s+(?=\d)", "°", text)
    text = re.sub(r"(?<=\d)\s+'", "'", text)
    text = re.sub(r"'\s+(?=\d)", "'", text)
    text = re.sub(r'(?<=\d)\s+"', '"', text)

    text = text.replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split())

    return text
