# Browser checks

The order flow in a real browser engine, as a phone (iPhone 15 on WebKit, Pixel 7 on Chromium)
and as a computer: picking recipes, the Whole Foods buttons, printing, placing an order,
undoing it and starting a second one. Not run in CI (they need browsers and a database).

```bash
# 1. A database and the app with the dev password user (see the main README):
#    COOKBOOK_DATABASE_URL=… COOKBOOK_TEST_USER_EMAIL=dev@cookbook.local COOKBOOK_TEST_USER_PASSWORD=dev-password
cd backend && alembic upgrade head && uvicorn app.main:app --port 8001 &
cd frontend && npm run dev &                 # http://localhost:5173
# 2. The checks:
cd e2e && npm install && npx playwright install webkit chromium && npx playwright test
```

`E2E_BASE_URL`, `E2E_EMAIL` and `E2E_PASSWORD` point it elsewhere. Full-page screenshots of each
step land in `e2e/screenshots/`. Amazon is stubbed; `window.print` is replaced by a recorder that
checks each print runs inside the tap, which is what iPhone Safari requires.
