"""BYOK and AI routes with a stand-in Anthropic client; the demo's read-only guarantees."""

from __future__ import annotations

import copy
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.ai import client as ai_client
from app.ai.schemas import AdaptResult, RecipeDraft
from app.config import settings
from app.core.crypto import decrypt_secret, encrypt_secret
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models import AiUsage, User
from tests.conftest import client_for, make_user

DRAFT = RecipeDraft(
    title="Spicy Sausage Pasta",
    emoji="🌶️",
    method="stovetop-oven",
    description="Hotter.",
    servings_text="4",
    prep_text="10 min",
    cook_text="20 min (stovetop)",
    tags=["spicy"],
    ingredients=[{"group": "Protein", "item": "Hot Italian sausage links", "amount": "12 oz"}],
    steps=["**Brown** – Brown it."],
    grocery=["**Protein**: 12 oz hot sausage links"],
    notes="",
)


class FakeMessages:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return self.script.pop(0)

    def create(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        return self.script.pop(0)


@pytest.fixture
def fake_ai(monkeypatch):
    holder = {}

    def install(script):
        fake = SimpleNamespace(messages=FakeMessages(script))
        holder["fake"] = fake
        monkeypatch.setattr(ai_client, "client_factory", lambda key: fake)
        return fake

    return install


def _usage():
    return SimpleNamespace(input_tokens=100, output_tokens=50)


async def _user_with_key(email="cook@test.local") -> User:
    user = await make_user(email)
    async with AsyncSessionLocal() as db:
        u = await db.get(User, user.id)
        u.anthropic_key_enc, u.anthropic_key_last4 = encrypt_secret("sk-ant-test-key-1234"), "1234"
        await db.commit()
        return u


def test_secret_round_trip():
    assert decrypt_secret(encrypt_secret("sk-ant-abc")) == "sk-ant-abc"
    assert decrypt_secret("garbage") is None


async def test_ai_needs_the_users_own_key():
    user = await make_user("nokey@test.local")
    async with client_for(user) as c:
        r = await c.post("/api/ai/generate", json={"prompt": "tacos"})
        assert r.status_code == 402 and "your own Anthropic API key" in r.json()["detail"]
        me = (await c.get("/api/auth/me")).json()
        assert me["has_anthropic_key"] is False and "anthropic_key_enc" not in me


async def test_adapt_returns_a_version_without_saving(fake_ai):
    user = await _user_with_key()
    fake = fake_ai(
        [
            SimpleNamespace(
                parsed_output=AdaptResult(
                    recipe=DRAFT, change_summary=["Hot sausage"], variant_name="Spicier"
                ),
                usage=_usage(),
                stop_reason="end_turn",
            )
        ]
    )
    async with client_for(user) as c:
        pasta = (await c.get("/api/recipes/pasta-with-sausage-cream-sauce")).json()
        r = await c.post(
            f"/api/ai/recipes/{pasta['id']}/adapt", json={"instruction": "make it spicier"}
        )
        assert r.status_code == 200
        assert r.json()["variant_name"] == "Spicier"
        sent = fake.messages.calls[0]
        assert "Pasta with Sausage Cream Sauce" in sent["messages"][0]["content"]
        assert (await c.get("/api/recipes?scope=mine")).json() == []
        usage = (await c.get("/api/me/usage")).json()
        assert usage["models"][0]["calls"] == 1


async def test_chat_runs_tools_and_reports_actions(fake_ai):
    user = await _user_with_key()
    tool_turn = SimpleNamespace(
        content=[
            SimpleNamespace(model_dump=lambda **k: {"type": "text", "text": "Saving that."}),
            SimpleNamespace(
                model_dump=lambda **k: {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "create_recipe_draft",
                    "input": {
                        "recipe": DRAFT.model_dump(),
                        "based_on_slug": "pasta-with-sausage-cream-sauce",
                    },
                }
            ),
            SimpleNamespace(
                model_dump=lambda **k: {
                    "type": "tool_use",
                    "id": "t2",
                    "name": "add_recipe_to_list",
                    "input": {"slug": "garlic-butter-shrimp"},
                }
            ),
        ],
        usage=_usage(),
        stop_reason="tool_use",
    )
    final_turn = SimpleNamespace(
        content=[
            SimpleNamespace(model_dump=lambda **k: {"type": "text", "text": "Done: draft saved."})
        ],
        usage=_usage(),
        stop_reason="end_turn",
    )
    fake = fake_ai([tool_turn, final_turn])
    async with client_for(user) as c:
        thread = (
            await c.post(
                "/api/ai/chat", json={"message": "spicier pasta please, and shrimp this week"}
            )
        ).json()
        assert [m["role"] for m in thread["messages"]] == ["user", "assistant"]
        actions = thread["messages"][1]["actions"]
        assert {a["type"] for a in actions} == {"draft", "list"}
        drafts = (await c.get("/api/recipes?scope=mine")).json()
        assert drafts[0]["status"] == "draft" and drafts[0]["source"] == "remix"
        lst = (await c.get("/api/lists/current")).json()
        assert lst["recipes"][0]["slug"] == "garlic-butter-shrimp"
        # The second turn replays the first with alternating roles.
        second = fake.messages.calls[1]["messages"]
        assert [m["role"] for m in second] == ["user", "assistant", "user"]

    fake_ai(
        [
            SimpleNamespace(
                content=[SimpleNamespace(model_dump=lambda **k: {"type": "text", "text": "Sure."})],
                usage=_usage(),
                stop_reason="end_turn",
            )
        ]
    )
    async with client_for(user) as c:
        thread2 = (
            await c.post("/api/ai/chat", json={"message": "thanks", "thread_id": thread["id"]})
        ).json()
        assert len(thread2["messages"]) == 4
    async with AsyncSessionLocal() as db:
        assert len(list(await db.scalars(select(AiUsage)))) == 3


# --- demo -------------------------------------------------------------------------------------


def _write_routes():
    out = []
    for route in app.routes:
        for method in getattr(route, "methods", set()) - {"GET", "HEAD", "OPTIONS"}:
            out.append((method, route.path))
    return out


async def test_every_write_route_is_refused_in_demo_mode():
    settings.DEMO_MODE = True
    allowed = {
        ("POST", "/api/auth/demo"),
        ("POST", "/api/auth/logout"),
        ("POST", "/api/grocery/preview"),
    }
    async with client_for() as c:
        for method, path in _write_routes():
            concrete = path.replace("{recipe_id}", "00000000-0000-0000-0000-000000000000")
            for name in ("{item_id}", "{product_id}", "{key_id}", "{thread_id}", "{entry_id}"):
                concrete = concrete.replace(name, "00000000-0000-0000-0000-000000000000")
            r = await c.request(method, concrete, json={})
            if (method, path) in allowed:
                assert r.status_code != 403 or r.json().get("demo") is not True, path
            else:
                assert r.status_code == 403 and r.json()["demo"] is True, (method, path)
    from app.demo import ALLOWED_WRITES

    assert len(ALLOWED_WRITES) == 2


async def test_demo_guards_refuse_real_settings_and_users():
    from app.demo import check_demo_database, check_demo_settings

    settings.DEMO_MODE = True
    with pytest.raises(RuntimeError):
        check_demo_settings()  # OWNER_EMAILS is set in tests
    async with AsyncSessionLocal() as db:
        with pytest.raises(RuntimeError):
            await check_demo_database(db)


async def test_demo_session_is_read_only_in_postgres():
    from sqlalchemy import text

    from app.demo import make_read_only

    async with AsyncSessionLocal() as db:
        await make_read_only(db)
        with pytest.raises(Exception, match="read-only"):
            await db.execute(text("INSERT INTO site_state (key, value) VALUES ('x', '{}')"))
