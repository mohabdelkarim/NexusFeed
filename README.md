# NexusFeed

Autonomous Telegram news curator for AI and software engineering news.

## What It Does

- Fetches 15 curated RSS feeds in parallel with `ThreadPoolExecutor(max_workers=15)`.
- Keeps only articles published in the last 12 hours.
- Rejects tutorials, listicles, recaps, and other low-signal content before scoring.
- Deduplicates by canonical URL hash and cross-source story hash.
- Sends at most 25 candidates to Groq in one JSON-mode request per run.
- Posts at most 1 article per run and 3 per UTC day to Telegram.
- Persists `daily_state.json` and `posted_articles.json` back to the repository through GitHub Actions.

## Required Secrets

Configure these repository secrets before enabling the workflow:

- `GROQ_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHANNEL_ID`

## Local Run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python news_bot.py
```

## Workflow

The scheduler lives in `.github/workflows/news-bot.yml` and uses the required concurrency guard:

```yaml
concurrency:
  group: news-bot
  cancel-in-progress: false
```
