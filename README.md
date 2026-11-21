# Cookbook

Mark's recipes at [cookbook.markcheli.com](https://cookbook.markcheli.com), and a working kitchen
app around them: pick dinners for the week, get one combined grocery list matched to the Whole
Foods products you actually buy, fill the Whole Foods cart in one tap, print the recipes, and ask an
assistant to change, scale or invent recipes on your own Anthropic key.

A read-only demo with a made-up cook runs at [cookbook-demo.markcheli.com](https://cookbook-demo.markcheli.com).

## What it does

- **Public cookbook.** Anyone can browse, search and filter the recipes, open a recipe page (with
  schema.org Recipe data for link previews), combine several into a grocery list with Whole Foods
  search links, and print the cooking instructions one recipe per page, as the original site did.
- **Your own space (Google sign-in, anyone).** Your recipes (private), saved and copied recipes,
  this week's shopping list with amounts added up and scaled, "I have this" checks, a catalog of
  your Whole Foods products matched to ingredients, weekly regulars, a cooking log and past lists.
- **Whole Foods cart.** Amazon has no cart API for Whole Foods, so a bookmarklet ("Cookbook cart",
  in Settings) adds the week's products from your own signed-in browser. Agents can read the same
  list with an API key: `GET /api/lists/current/cart` (`X-API-Key`).
- **Assistant (bring your own key).** Each person pastes their own Anthropic API key in Settings
  (stored encrypted). It powers: changing a recipe ("I'm out of heavy cream", "Instant Pot
  version", "serves 2") shown as a diff you can keep as a variant; writing recipes from a prompt or
  brainstorm; importing from a photo or a page without recipe data; weekly suggestions; matching
  list items to products; and a chat (typed or spoken) that can search recipes, save drafts and
  edit the list. AI output is never published unreviewed.
- **Formats.** Recipes are stored relationally (groups, items, amounts, steps) and export as the
  original markdown, schema.org JSON-LD or PDF. The 38 recipes that used to be markdown files in
  this repo are bundled in `backend/app/seed/recipes.json` and imported on a fresh database; a test
  proves each one round-trips back to its original markdown.

## Stack

FastAPI + SQLAlchemy (async) + Postgres, Vue 3 + Vite + Tailwind, one Docker image
(`ghcr.io/mcheli/cookbook`) published by CI from `main` and deployed by Watchtower on the
83RR PowerEdge. Same layout and conventions as Tasks and Tallied.

## Develop

```bash
# Postgres on :5433 with databases cookbook and cookbook_test, then:
cd backend && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
cat > .env <<'ENV'
COOKBOOK_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/cookbook
COOKBOOK_OWNER_EMAILS=dev@cookbook.local
COOKBOOK_TEST_USER_EMAIL=dev@cookbook.local
COOKBOOK_TEST_USER_PASSWORD=dev-password
ENV
alembic upgrade head && uvicorn app.main:app --reload --port 8001
cd ../frontend && npm install && npm run dev        # http://localhost:5173 (proxies /api to :8001)
```

Tests: `cd backend && pytest` (Postgres at `COOKBOOK_TEST_DATABASE_URL`, default
`postgresql+asyncpg://postgres:postgres@localhost:5433/cookbook_test`), `cd frontend && npm test`.

More: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · [docs/DEPLOYING.md](docs/DEPLOYING.md) ·
[docs/DECISIONS.md](docs/DECISIONS.md)

## License

MIT
