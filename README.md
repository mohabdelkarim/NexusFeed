# NexusFeed

Autonomous AI and software engineering news curator for this repository.

## Overview

NexusFeed fetches curated RSS feeds, filters recent stories, scores them with Groq, and keeps only the strongest candidates.

- `POST_NOW` stories are saved in `posted_now.json`
- `SAVE_PENDING` stories stay in `daily_state.json` as `pending_best`
- Posted story history stays in `posted_articles.json`
- The README is auto-updated with the latest `POST_NOW` items

## How It Works

1. Fetches 15 RSS sources in parallel
2. Keeps articles from the last 24 hours
3. Removes duplicates by URL hash and title similarity
4. Sends up to 25 candidates to Groq for scoring
5. Decides `POST_NOW`, `SAVE_PENDING`, or `SKIP`
6. Saves only actual `POST_NOW` results to `posted_now.json` and this README

## Scoring

The scorer uses 4 criteria:

- `Novelty` up to `3.0`
- `Impact` up to `3.0`
- `Freshness` up to `2.0`
- `Source` up to `2.0`

Decision thresholds:

- `>= 8.5` -> `POST_NOW`
- `>= 6.0` -> `SAVE_PENDING`
- `< 6.0` -> `SKIP`

Articles that match red-flag patterns such as `top 10`, `how to`, `tutorial`, `weekly recap`, and similar listicles are rejected locally.

## Outputs

Main generated files:

- `posted_now.json`: latest `POST_NOW` items
- `posted_articles.json`: dedupe history
- `daily_state.json`: daily counters and `pending_best`
- `digest_history.json`: digest dedupe history
- `latest_digest.json`: latest generated daily digest

## Secrets

Only one secret is required:

- `GROQ_API_KEY`

Example local `.env`:

```bash
GROQ_API_KEY=your_groq_api_key_here
```

## Local Run

```bash
python -m venv .venv
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

Other commands:

```bash
python daily_digest.py
python check_feeds.py
```

## GitHub Actions

`news-bot.yml`

- Runs the main curator on schedule
- Commits `daily_state.json`, `posted_articles.json`, `posted_now.json`, and `README.md`

`daily-digest.yml`

- Generates the top 5 digest
- Commits `digest_history.json` and `latest_digest.json`

`feed-health.yml`

- Checks feed availability
- Fails if too many sources are dead

<!-- POST_NOW_START -->
## Latest POST_NOW

Αυτα ειναι τα πιο προσφατα αρθρα που πηραν αποφαση `POST_NOW`.

- Δεν υπαρχουν ακομα POST_NOW αρθρα.
<!-- POST_NOW_END -->
