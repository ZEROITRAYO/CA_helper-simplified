# CA Helper
Flask + React + Postgres (Neon) lab project. Keep it simple: a beginner should be able to read any file.

Run: `docker compose up` (app http://localhost:5173, API :8000, Mailpit :8025).
Tests: `docker compose exec backend pytest`, `docker compose exec frontend npm test`.

Code style:
- Backend: plain `@app.route` functions in backend/routes_*.py (no Blueprints); tables in models.py; shared
  helpers in helpers.py; filing logic in filings.py. Tables are made with db.create_all() (no migrations).
- No classes unless they make the code shorter (the tables are classes).
- Short functions, plain loops, one-line docstrings, comments only for the "why". No task ids or rule numbers.
- Keep the JSON responses and error codes the frontend uses.
- Commit in the route before returning. Send emails after the commit.
- OCR stays local. Legal thresholds and due dates come from the rule tables, never from code.
- Frontend: plain JS, pages in pages/, all API calls in api.js.
- Never point TEST_DATABASE_URL at Neon. Never commit .env.
