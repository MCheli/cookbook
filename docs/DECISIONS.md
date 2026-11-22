# Decisions

## 2026-11-21 — Database instead of markdown files
**Decision:** Postgres is the source of truth. The 38 markdown recipes were imported and removed
from the repo; their text is bundled verbatim in `backend/app/seed/recipes.json` for fresh
databases and the demo, and stored per recipe in `recipes.source_markdown`.
**Why:** Editing, variants, AI drafts, per-user recipes and lists need a database. A round-trip
test proves nothing was lost, and PDFs/print are rendered from the regenerated markdown so they
look as before.

## 2026-11-21 — Bring your own Anthropic key
**Decision:** Every user (including the owner) pastes their own key in Settings. Keys are
Fernet-encrypted with `COOKBOOK_SECRETS_KEY`, validated with one `models.list` call, never
returned (last four characters only). There is no server-wide AI key.
**Why:** Anyone can sign in; nobody should be able to spend someone else's money.

## 2026-11-21 — Whole Foods cart via bookmarklet, not an API
**Decision:** The app produces a cart manifest (ASIN × quantity). A bookmarklet run on amazon.com
in the user's own session opens each product's Whole Foods page in a hidden same-origin frame and
presses its add button (the same method the weekly grocery skill uses through Claude in Chrome).
Agents read the manifest via `GET /api/lists/current/cart`.
**Why:** Amazon offers no Whole Foods cart API; PA-API was retired in May 2026 and its successor
(Creators API) is catalog data for affiliates. The manifest travels in the URL fragment, which is
never sent to Amazon's servers. Checkout always stays with the person.

## 2026-11-22 — Every recipe prints on one page
**Decision:** Both print paths fit each recipe to a single Letter page. They try the normal layout
a little smaller first, then a compact one: ingredients folded into two Item | Amount column pairs,
without the category column, and narrower margins in the PDF. Only then do they step the text down,
with a floor (7pt in the PDF, 9px in the browser) below which a recipe prints on two pages instead.
The server PDF (`services/pdf.py`) renders each recipe on its own with WeasyPrint and checks the page
count. The Print button (`lib/print.js`) measures each page off-screen at the printed width before
calling `window.print()`.
**Why:** Mark asked that recipes always fit on one page. All 38 current recipes already fit at full
size, but long, imported or AI-written ones didn't.

## 2026-11-22 — Per-item Add buttons first; the bookmarklet becomes optional
**Decision:** Each list item gets an Add button (matched product page, or a Whole Foods search)
that also ticks the item `in_cart`; the card shows "n of m in your cart". The bookmarklet moves to
Settings as a computer-only extra: it reads the cart first, adds only what's missing, presses the
cart's + button until quantities match, and offers "Tick them off in Cookbook"
(`/list?in_cart=ASIN,…`). The cart manifest leaves out items already in the cart.
**Why:** Tried for real on 2026-11-22: "Send to Whole Foods cart" only opened Amazon and looked
broken unless the bookmark was installed, and on iPhone it couldn't run at all (Home Screen app
and Amazon app can't run bookmarks). Tapping through ~10–15 items works everywhere.

## 2026-11-21 — Public cookbook, owner-only publishing
**Decision:** Public pages show public, published recipes. Only `COOKBOOK_OWNER_EMAILS` can make a
recipe public; everyone else's recipes are private to them (they can save or copy public ones).
**Why:** Keeps the public site Mark's cookbook, with nothing to moderate.

## 2026-11-21 — Demo is a second deployment
**Decision:** cookbook-demo.markcheli.com runs the same image with `COOKBOOK_DEMO_MODE=true` on its
own database, reseeded on every start, following Tallied's demo playbook. Allowed writes: demo
sign-in, sign-out and the grocery preview (a pure calculation). No AI calls: the persona has no
key; the demo shows saved example chats and AI-made recipes.

## 2026-11-21 — Voice input
**Decision:** The mic uses the browser's Web Speech API. Where it isn't available (it has been
missing in some iOS Home Screen web apps) the button points to the keyboard's dictation key.
**Why:** Anthropic's API takes no audio; a server-side transcriber can be added if the phone needs it.
