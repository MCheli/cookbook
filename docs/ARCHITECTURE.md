# Architecture

One container serves the API under `/api` and the built Vue app for every other path. Postgres
is a separate container. Public recipe pages (`/r/<slug>`) get their title, description, Open
Graph tags and schema.org JSON-LD injected into `index.html` by the server.

## Backend (`backend/app`)

| Module | What it holds |
|---|---|
| `config.py` | Settings, `COOKBOOK_` prefix; production refuses public default secrets |
| `models.py` | All tables (below) |
| `dependencies.py` | Session cookie or `X-API-Key` → user; `get_optional_user` for public pages |
| `demo.py` | Demo mode: write refusal middleware, READ ONLY transactions, startup guards |
| `services/recipe_markdown.py` | The original markdown format, both directions |
| `services/quantities.py`, `services/grocery.py` | Amount parsing, scaling, adding up; combining recipes into one list |
| `services/recipes.py` | Slugs, visibility rules, serialization, schema.org JSON-LD |
| `services/lists.py` | Shopping list rebuild, product matching, the Whole Foods cart manifest |
| `services/pdf.py` | WeasyPrint PDFs from the recipe markdown, same stylesheet as the old build script |
| `services/web_import.py` | URL import: locked-down fetch, JSON-LD Recipe parsing, page text for AI |
| `services/seed.py` | First start: the owner's bundled recipes; dev password user |
| `services/demo_seed.py` | Claudius Banks, laid out backwards from today |
| `ai/client.py` | Every Claude call, on the user's own decrypted key; usage logged to `ai_usage` |
| `ai/schemas.py`, `ai/prompts.py`, `ai/tools.py` | Structured outputs, the house style, chat tools |
| `routers/` | `auth`, `account` (BYOK, preferences, API keys, usage), `recipes`, `grocery` (preview, lists, products, cook log), `ai` (adapt, ideas, generate, imports, suggestions, matching, chat) |

### Tables

`users` (Google sub, encrypted Anthropic key, food profile) · `api_keys` · `recipes` (owner,
slug, method, servings/prep/cook text, tags, visibility, status, source, parent for variants, AI
metadata, verbatim source markdown) · `recipe_ingredients` (group, item, amount) · `recipe_steps`
(inline markdown) · `recipe_grocery_lines` · `saved_recipes` · `products` (ASIN, size, price,
`match_keys` ingredient keys, regular flag, distinct purchase dates) · `shopping_lists` /
`shopping_list_recipes` / `shopping_list_items` · `cook_logs` · `chat_threads` / `chat_messages`
(Anthropic content blocks plus what the UI shows) · `ai_usage` · `site_state`.

### Rules

- Every user-owned query filters on the user. Other people's recipes are visible only if public
  and published; only site owners (`COOKBOOK_OWNER_EMAILS`) can publish.
- Anyone with a verified Google account can sign in. Nothing they do can cost the owner money:
  AI runs only on each user's own key, and the cart is filled in each user's own Amazon session.
- AI output is never saved unreviewed: adapted versions come back for the cook to keep or discard;
  chat-created recipes are private drafts; imports open in the editor.
- An ingredient's key is its lower-cased name without parenthetical notes or anything after a
  comma (the original site's rule). Products match ingredients by key; choosing a product for a
  line remembers the key on the product.
- The server-side URL fetch accepts http(s) to public addresses only, re-checked on each redirect.

## Frontend (`frontend/src`)

Views: Home (grid, filters, selection) · Recipe (scale, print, PDF, list, save/copy, edit,
assistant, cook log) · Grocery preview (public) · This week (list, regulars, cart, AI suggestions
and matching) · Products · New recipe (describe/brainstorm, link, photo, markdown, blank) · Edit ·
Chat · History · Settings (key, food profile, cart bookmarklet, API keys) · Login (hero, Google,
demo card).

`lib/print.js` prints from the page into `#print-area` (no pop-ups, for the iPhone Home Screen
app), using the original layout. `lib/cartLoader.js` is the cart bookmarklet. `v-demo-lock`
disables write controls in the demo.
