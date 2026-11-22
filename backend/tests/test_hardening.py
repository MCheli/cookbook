"""Guards for the CodeQL findings on the 2.0 PR: slow regexes, static paths, and page fetching."""

import socket
import time

import pytest

from app.main import static_file
from app.services import web_import
from app.services.grocery import ingredient_key
from app.services.recipe_markdown import parse_markdown
from app.services.recipes import _minutes


def _fast(fn, *args, limit=0.5):
    start = time.perf_counter()
    fn(*args)
    assert time.perf_counter() - start < limit


def test_meta_line_is_linear_on_long_input():
    for line in ("**Servings:**" + " " * 20_000, "**Servings:** | **Prep:**" + " " * 20_000):
        _fast(parse_markdown, f"## 🍲 Soup\n\n{line}\n\n### Ingredients\n")


def test_meta_line_still_parses():
    doc = parse_markdown("## 🍲 Soup\n**Servings:** 4 | **Prep:** 10 min | **Cook:** 1 hr | low\n")
    assert (doc.servings_text, doc.prep_text, doc.cook_text) == ("4", "10 min", "1 hr | low")
    assert parse_markdown("## Soup\n**Servings:** 4 | **Cook:** 1 hr\n").servings_text is None


@pytest.mark.parametrize("text", ["(" * 50_000, "," * 50_000, " " * 50_000 + "x", "9" * 50_000])
def test_keys_and_times_are_fast_on_hostile_input(text):
    _fast(ingredient_key, text)
    _fast(_minutes, text)


def test_ingredient_key_unchanged_for_real_names():
    assert ingredient_key("*optional* – cayenne") == "cayenne"
    assert ingredient_key("Chicken thighs (boneless, skinless), cubed") == "chicken thighs"
    assert ingredient_key("  Heavy   cream  ") == "heavy cream"


def test_static_file_stays_inside_root(tmp_path):
    root = tmp_path / "static"
    (root / "assets").mkdir(parents=True)
    (root / "assets" / "app.js").write_text("x")
    (tmp_path / "secret.txt").write_text("no")
    assert static_file(root, "assets/app.js") == (root / "assets" / "app.js").resolve()
    for bad in (
        "../secret.txt",
        "assets/../../secret.txt",
        str(tmp_path / "secret.txt"),
        "",
        "assets",
    ):
        assert static_file(root, bad) is None


def _resolves_to(monkeypatch, *ips):
    def fake(host, port, *a, **kw):
        return [
            (socket.AF_INET6 if ":" in ip else socket.AF_INET, 1, 6, "", (ip, port)) for ip in ips
        ]

    monkeypatch.setattr(web_import.socket, "getaddrinfo", fake)


def test_fetch_connects_to_the_checked_address(monkeypatch):
    _resolves_to(monkeypatch, "93.184.215.14")
    target, headers, ext = web_import._pinned("https://www.example.com/recipe?id=1#top")
    assert target == "https://93.184.215.14:443/recipe?id=1"
    assert headers == {"Host": "www.example.com"} and ext == {"sni_hostname": "www.example.com"}

    _resolves_to(monkeypatch, "2606:2800:21f:cb07:6820:80da:af6b:8b2c")
    target, headers, ext = web_import._pinned("http://example.com:8080/a")
    assert target == "http://[2606:2800:21f:cb07:6820:80da:af6b:8b2c]:8080/a"
    assert headers == {"Host": "example.com:8080"} and ext == {}


@pytest.mark.parametrize(
    "ips",
    [
        ("127.0.0.1",),
        ("10.1.2.3",),
        ("172.18.0.5",),
        ("169.254.169.254",),
        ("::1",),
        ("::ffff:127.0.0.1",),
        ("fd00::1",),
        ("93.184.215.14", "192.168.1.179"),
    ],
)
def test_fetch_refuses_private_addresses(monkeypatch, ips):
    _resolves_to(monkeypatch, *ips)
    with pytest.raises(web_import.ImportError_):
        web_import._pinned("https://sneaky.example.com/")


@pytest.mark.parametrize(
    "url", ["ftp://example.com/x", "file:///etc/passwd", "https:///nohost", "http://x.com:99999/"]
)
def test_fetch_refuses_odd_links(monkeypatch, url):
    _resolves_to(monkeypatch, "93.184.215.14")
    with pytest.raises(web_import.ImportError_):
        web_import._pinned(url)


def test_product_search_term_drops_the_house_brand_boilerplate():
    from app.services.grocery import product_search_term, search_term

    assert (
        product_search_term("365 by Whole Foods Market, Vegetable Oil, 32 Fl Oz")
        == "365 Vegetable Oil 32 Fl Oz"
    )
    assert (
        product_search_term("Calise Bakery Sub Rolls (6 ct), 18 Oz")
        == "Calise Bakery Sub Rolls 18 Oz"
    )
    assert search_term("Chicken thighs (boneless), cubed") == "Chicken thighs"
    _fast(product_search_term, "(" * 50_000)
    _fast(search_term, "(" * 50_000)
