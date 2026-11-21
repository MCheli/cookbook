"""Amounts like '1½ lb', '2–3 cloves', '½ cup': parse, scale, add up, print.

Anything that doesn't parse ('to taste', 'a handful') is kept as text and never guessed at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction

_UNICODE_FRACTIONS = {
    "½": Fraction(1, 2),
    "⅓": Fraction(1, 3),
    "⅔": Fraction(2, 3),
    "¼": Fraction(1, 4),
    "¾": Fraction(3, 4),
    "⅕": Fraction(1, 5),
    "⅛": Fraction(1, 8),
    "⅜": Fraction(3, 8),
    "⅝": Fraction(5, 8),
    "⅞": Fraction(7, 8),
    "⅙": Fraction(1, 6),
}
_NUM = r"(?:\d+\s*[½⅓⅔¼¾⅕⅛⅜⅝⅞⅙]|\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?|\.\d+|[½⅓⅔¼¾⅕⅛⅜⅝⅞⅙])"
_AMOUNT_RE = re.compile(
    rf"^\s*(?P<lo>{_NUM})(?:\s*(?:–|-|‑|to|—)\s*(?P<hi>{_NUM}))?\s*(?P<rest>.*)$", re.IGNORECASE
)

# unit -> (family, size in the family's base unit)
_UNITS: dict[str, tuple[str, Fraction]] = {
    "lb": ("mass", Fraction(16)),
    "lbs": ("mass", Fraction(16)),
    "pound": ("mass", Fraction(16)),
    "pounds": ("mass", Fraction(16)),
    "oz": ("mass", Fraction(1)),
    "ounce": ("mass", Fraction(1)),
    "ounces": ("mass", Fraction(1)),
    "cup": ("volume", Fraction(48)),
    "cups": ("volume", Fraction(48)),
    "tbsp": ("volume", Fraction(3)),
    "tablespoon": ("volume", Fraction(3)),
    "tablespoons": ("volume", Fraction(3)),
    "tsp": ("volume", Fraction(1)),
    "teaspoon": ("volume", Fraction(1)),
    "teaspoons": ("volume", Fraction(1)),
}
_CANONICAL = {
    "mass": [("lb", Fraction(16)), ("oz", Fraction(1))],
    "volume": [("cup", Fraction(48)), ("Tbsp", Fraction(3)), ("tsp", Fraction(1))],
}
_PRETTY = {
    Fraction(1, 2): "½",
    Fraction(1, 3): "⅓",
    Fraction(2, 3): "⅔",
    Fraction(1, 4): "¼",
    Fraction(3, 4): "¾",
    Fraction(1, 8): "⅛",
    Fraction(3, 8): "⅜",
    Fraction(5, 8): "⅝",
    Fraction(7, 8): "⅞",
}


def _to_fraction(s: str) -> Fraction:
    s = s.strip()
    if s in _UNICODE_FRACTIONS:
        return _UNICODE_FRACTIONS[s]
    m = re.fullmatch(r"(\d+)\s*([½⅓⅔¼¾⅕⅛⅜⅝⅞⅙])", s)
    if m:
        return int(m[1]) + _UNICODE_FRACTIONS[m[2]]
    m = re.fullmatch(r"(\d+)\s+(\d+)/(\d+)", s)
    if m:
        return int(m[1]) + Fraction(int(m[2]), int(m[3]))
    if "/" in s:
        a, b = s.split("/")
        return Fraction(int(a), int(b))
    return Fraction(s)


@dataclass
class Amount:
    lo: Fraction
    hi: Fraction | None
    unit: str | None  # first word of the rest, lower-cased, if it's a known unit or count word
    rest: str  # everything after the number(s), as written

    @property
    def family(self) -> str | None:
        return _UNITS[self.unit][0] if self.unit in _UNITS else None


def parse_amount(text: str | None) -> Amount | None:
    if not text:
        return None
    t = text.replace(" ", " ").replace(" ", " ").strip()
    m = _AMOUNT_RE.match(t)
    if not m:
        return None
    try:
        lo = _to_fraction(m["lo"])
        hi = _to_fraction(m["hi"]) if m["hi"] else None
    except (ValueError, ZeroDivisionError):
        return None
    rest = m["rest"].strip()
    first = re.split(r"[\s,(]", rest, maxsplit=1)[0].lower().rstrip(".") if rest else ""
    return Amount(lo=lo, hi=hi, unit=first or None, rest=rest)


def format_number(q: Fraction) -> str:
    if q <= 0:
        return "0"
    whole, frac = divmod(q, 1)
    whole = int(whole)
    if frac == 0:
        return str(whole)
    nearest = min(_PRETTY, key=lambda f: abs(f - frac))
    if abs(nearest - frac) < Fraction(1, 40):
        return f"{whole}{_PRETTY[nearest]}" if whole else _PRETTY[nearest]
    return f"{float(q):.2f}".rstrip("0").rstrip(".")


def _format_family(family: str, total: Fraction) -> str:
    """Pick the unit a cook would write: cups from ¼ cup up, lb from 1 lb up."""
    if family == "mass":
        return f"{format_number(total / 16)} lb" if total >= 16 else f"{format_number(total)} oz"
    cups = total / 48
    if total >= 12 and (cups.denominator in (1, 2, 3, 4, 8) or total >= 48):
        return f"{format_number(cups)} {'cups' if cups > 1 else 'cup'}"
    if total >= 3 and (total / 3).denominator in (1, 2):
        return f"{format_number(total / 3)} Tbsp"
    return f"{format_number(total)} tsp"


def scale_amount(text: str | None, factor: float) -> str | None:
    """'1 lb' × 1.5 -> '1½ lb'. Unparseable amounts come back unchanged."""
    if text is None or factor == 1:
        return text
    a = parse_amount(text)
    if a is None:
        return text
    f = Fraction(factor).limit_denominator(16)
    lo = format_number(a.lo * f)
    hi = f"–{format_number(a.hi * f)}" if a.hi is not None else ""
    return f"{lo}{hi} {a.rest}".strip()


def add_amounts(texts: list[str]) -> str:
    """Add up amounts for one ingredient. Same-family units are summed ('½ cup' + '2 Tbsp' ->
    '½ cup + 2 Tbsp' becomes '⅝ cup'); things that can't be added are listed with ' + '."""
    sums: dict[str, Fraction] = {}
    counts: dict[str, Fraction] = {}
    leftovers: list[str] = []
    for t in texts:
        a = parse_amount(t)
        if a is None or a.hi is not None:
            if t and t not in leftovers:
                leftovers.append(t)
            continue
        if a.family:
            sums[a.family] = sums.get(a.family, Fraction(0)) + a.lo * _UNITS[a.unit][1]
        else:  # '3 cloves', '2', '1 medium', '1 (15 oz) can'
            counts[a.rest] = counts.get(a.rest, Fraction(0)) + a.lo
    parts: list[str] = []
    for family, total in sums.items():
        parts.append(_format_family(family, total))
    for rest, total in counts.items():
        parts.append(f"{format_number(total)} {rest}".strip())
    return " + ".join(parts + leftovers)
