# BirdCatch

A gamified birdwatching app — spot real birds, earn XP, level up, complete daily
quests, and fill your Birdex. Think Pokédex, but for birds you actually see.

This is a **proof of concept**: a Flask backend with a server-rendered web
frontend, intended to validate the game loop before a native mobile build.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py                      # http://127.0.0.1:5000
```

The database is created and seeded (49 birds, 21 achievements) on first run at
`instance/birding.db`.

### Running in production

Never use `python app.py` outside development — it starts the Werkzeug debug
server. Use the WSGI entrypoint with a real server:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export FLASK_ENV=production
gunicorn wsgi:app
```

The app **refuses to boot** with `FLASK_ENV=production` if `SECRET_KEY` is unset,
rather than silently signing session cookies with a public development key.

### Tests

```bash
pytest tests/ -v
```

Tests run against a throwaway in-memory SQLite database and never touch
`instance/birding.db`.

---

## Game mechanics

| Rarity | Birds | Base XP |
|---|---|---|
| Common | 15 | 10 |
| Uncommon | 12 | 25 |
| Rare | 10 | 50 |
| Epic | 7 | 100 |
| Legendary | 5 | 250 |

- **XP & levels** — 20 levels on a rising threshold curve. A sighting earns the
  bird's `xp_value`, doubled for a new species, plus a streak bonus (up to +50).
- **Anti-farming** — re-logging the *same* species on the same day earns 25% base
  XP and no streak bonus, so the leaderboard reflects birding rather than clicking.
- **Streaks & daily quests** — roll over at the user's **local** midnight, driven
  by their IANA timezone (`PUT /api/profile/timezone`), defaulting to UTC.
- **Daily quests** — three randomized quests per day with XP rewards.
- **Achievements** — 21 badges across collection, streak, and mastery categories.

## Pages

| Page | Route | Auth |
|---|---|---|
| Landing / login | `/` | — |
| Dashboard | `/dashboard` | ✓ |
| Explore (encounters) | `/explore` | ✓ |
| Catch a bird | `/catch` | ✓ |
| Daily quests | `/challenges` | ✓ |
| Birdex | `/birdex` | ✓ |
| Badges | `/achievements` | ✓ |
| Bird catalog | `/catalog` | — |
| Activity feed | `/feed` | — |
| Leaderboard | `/leaderboard` | — |
| Public profile | `/profile/<id>` | — |

## API

`GET /api/info` returns the full endpoint listing. Highlights:

```
POST /api/register            POST /api/login           POST /api/logout
PUT  /api/profile/timezone    GET  /api/profile/<id>
GET  /api/birds               GET  /api/birds/<id>
POST /api/sightings           GET  /api/sightings/user/<id>   (owner only)
GET  /api/birdex/<id>         GET  /api/birdex/<id>/stats
GET  /api/challenges          GET  /api/encounter
GET  /api/leaderboard?sort=xp|level|total_sightings|unique_species|streak
```

### API conventions

- **Auth** is a signed session cookie. The acting user always comes from the
  session; a `user_id` in a request body is ignored.
- **CSRF**: authenticated state-changing requests must echo the `csrf_token`
  cookie in an `X-CSRF-Token` header.
- **Errors** under `/api/` are always JSON: `{"error": "...", "status": 4xx}`.
- **Privacy**: sightings carry GPS coordinates, so sighting reads are owner-only.

## Project layout

```
app.py            application factory, CSRF, error handlers, seeding
wsgi.py           production entrypoint
models.py         User / Bird / Sighting / Achievement / DailyChallenge
seed_data.py      49 birds + 21 achievements
routes/           auth, birds, sightings, birdex, leaderboard,
                  challenges, encounter, pages
templates/        Jinja2 pages
static/           CSS + vanilla JS (no build step)
tests/            pytest suite (conftest.py holds fixtures/helpers)
```

## Known limitations

Deliberate scope cuts for the proof of concept:

- **SQLite** with no migration tool. Model changes require recreating
  `instance/birding.db`; adopt Alembic + Postgres before launch.
- **No rate limiting** on any endpoint.
- **No photo upload** — `photo_url` is accepted but nothing is hosted.
- **Sightings are unverified** (honour system); there is no image or
  location validation proving a bird was actually seen.
