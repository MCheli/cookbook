"""Import a recipe from a web page.

Most recipe sites publish schema.org/Recipe JSON-LD; that is converted directly, no AI needed.
Pages without it fall back to Claude (on the user's key) reading the page text.

The server fetches the page, so the fetch is locked down: http(s) only, public addresses only
(checked on every redirect hop), a small size cap and a short timeout.
"""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx

from app.services.quantities import parse_amount

MAX_BYTES = 3_000_000
USER_AGENT = "Mozilla/5.0 (compatible; MarkCheliCookbook/2.0; +https://cookbook.markcheli.com)"


class ImportError_(Exception):
    pass


def _check_public(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ImportError_("Only http(s) links can be imported.")
    try:
        infos = socket.getaddrinfo(
            parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80)
        )
    except socket.gaierror as exc:
        raise ImportError_("That site's address couldn't be found.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise ImportError_("That address isn't on the public internet.")


async def fetch_page(url: str) -> str:
    current = url
    async with httpx.AsyncClient(
        timeout=15, follow_redirects=False, headers={"User-Agent": USER_AGENT}
    ) as client:
        for _ in range(5):
            _check_public(current)
            async with client.stream("GET", current) as resp:
                if resp.is_redirect and resp.headers.get("location"):
                    current = urljoin(current, resp.headers["location"])
                    continue
                if resp.status_code >= 400:
                    raise ImportError_(f"The page answered {resp.status_code}.")
                chunks, size = [], 0
                async for chunk in resp.aiter_bytes():
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ImportError_("That page is too large to import.")
                    chunks.append(chunk)
                return b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
    raise ImportError_("Too many redirects.")


def _walk(node):
    if isinstance(node, list):
        for n in node:
            yield from _walk(n)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "mainEntity", "itemListElement"):
            if key in node:
                yield from _walk(node[key])


def find_jsonld_recipe(html: str) -> dict | None:
    for m in re.finditer(
        r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", html, re.S | re.I
    ):
        try:
            data = json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            continue
        for node in _walk(data):
            t = node.get("@type")
            if t == "Recipe" or (isinstance(t, list) and "Recipe" in t):
                return node
    return None


def _text(v) -> str:
    if isinstance(v, list):
        v = v[0] if v else ""
    return unescape(re.sub(r"<[^>]+>", " ", str(v or ""))).strip()


def _duration(iso: str | None) -> str | None:
    if not iso:
        return None
    m = re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:\d+S)?", str(iso).strip())
    if not m or not (m.group(1) or m.group(2)):
        return None
    h, mins = int(m.group(1) or 0), int(m.group(2) or 0)
    return " ".join(p for p in (f"{h} hr" if h else "", f"{mins} min" if mins else "") if p)


def _steps(instructions) -> list[str]:
    out: list[str] = []
    for node in instructions if isinstance(instructions, list) else [instructions]:
        if isinstance(node, str):
            out += [s.strip() for s in re.split(r"\n+", _text(node)) if s.strip()]
        elif isinstance(node, dict):
            if node.get("@type") == "HowToSection":
                out += _steps(node.get("itemListElement", []))
            else:
                t = _text(node.get("text") or node.get("name"))
                if t:
                    out.append(t)
    return out


def split_ingredient(line: str) -> tuple[str | None, str]:
    """'1 lb penne pasta' -> ('1 lb', 'penne pasta'); keeps lines it can't split whole."""
    line = re.sub(r"\s+", " ", line).strip()
    a = parse_amount(line)
    if a is None:
        return None, line
    number_part = line[: len(line) - len(a.rest)].strip()
    rest = a.rest
    unit_m = re.match(
        r"^((?:\([^)]*\)\s*)?(?:lbs?|pounds?|oz|ounces?|cups?|tbsp|tablespoons?|tsp|teaspoons?|cloves?|cans?|"
        r"jars?|packages?|pkgs?|bunch(?:es)?|heads?|slices?|sticks?|pinch(?:es)?|dash(?:es)?|large|medium|small|g|kg|ml|l)\.?)\s+(.*)$",
        rest,
        re.I,
    )
    if unit_m:
        return f"{number_part} {unit_m.group(1)}".strip(), unit_m.group(2).strip()
    return number_part, rest


def jsonld_to_payload(node: dict, url: str) -> dict:
    ingredients = []
    for line in node.get("recipeIngredient") or node.get("ingredients") or []:
        amount, item = split_ingredient(_text(line))
        if item:
            ingredients.append(
                {"group": "Ingredients", "item": item[:240], "amount": (amount or "")[:80] or None}
            )
    yield_text = _text(node.get("recipeYield"))
    category = (
        " ".join(_text(c) for c in (node.get("recipeCategory") or []) if c)
        if isinstance(node.get("recipeCategory"), list)
        else _text(node.get("recipeCategory"))
    )
    blob = f"{_text(node.get('name'))} {category} {_text(node.get('description'))}".lower()
    method = (
        "instapot"
        if "instant pot" in blob or "pressure cook" in blob
        else "crockpot" if "slow cook" in blob or "crock" in blob else "stovetop-oven"
    )
    return {
        "title": _text(node.get("name"))[:200] or "Imported recipe",
        "emoji": None,
        "method": method,
        "description": _text(node.get("description"))[:2000] or None,
        "servings_text": re.sub(r"\s*servings?$", "", yield_text, flags=re.I)[:60] or None,
        "prep_text": _duration(node.get("prepTime")),
        "cook_text": _duration(node.get("cookTime")),
        "tags": [],
        "ingredients": ingredients,
        "steps": _steps(node.get("recipeInstructions") or []),
        "grocery": [],
        "source": "import",
        "source_url": url,
        "visibility": "private",
        "status": "draft",
    }


def page_text(html: str, limit: int = 40_000) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg|nav|footer|header)[^>]*>.*?</\1>", " ", html)
    text = unescape(re.sub(r"<[^>]+>", " ", html))
    return re.sub(r"\s+", " ", text).strip()[:limit]
