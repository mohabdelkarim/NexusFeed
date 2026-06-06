from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any

import requests

from news_bot import (
    FEEDS,
    GROQ_MODEL,
    GROQ_URL,
    Article,
    clean_multiline_text,
    clean_whitespace,
    configure_logging,
    fetch_feed,
    sanitize_telegram_markdown_text,
    truncate,
    utc_now,
)


MAX_DIGEST_CANDIDATES = 30
REDUCED_DIGEST_CANDIDATES = 15
REQUIRED_SECRETS = ("GROQ_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHANNEL_ID")

DIGEST_SYSTEM_PROMPT = """
You are an AI news curator creating a daily top 5 digest for a
Telegram channel for software engineers and AI researchers.

Select the 5 most important AI/tech stories from today.
Rank them by importance (most important first).

For each story, provide:
- rank: 1-5
- full_title: the complete article title, no truncation
- one_line_summary: max 15 words, what actually happened
- source_name: publication name
- source_tier: S/A/B/C
- score: float 0.00-10.00 using same criteria as always
- article_url: the link

Respond ONLY with valid JSON:
{
  "digest": [
    {
      "rank": 1,
      "full_title": "...",
      "one_line_summary": "...",
      "source_name": "...",
      "source_tier": "S",
      "score": 9.2,
      "article_url": "..."
    }
  ],
  "digest_date": "YYYY-MM-DD"
}
""".strip()


def require_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for key in REQUIRED_SECRETS:
        value = os.environ.get(key)
        if not value:
            raise EnvironmentError(f"Missing required secret: {key}")
        values[key] = value
    return values


def fetch_digest_candidates(now: datetime) -> list[Article]:
    articles: list[Article] = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_map = {executor.submit(fetch_feed, feed, now): feed for feed in FEEDS}
        for future in as_completed(future_map):
            feed = future_map[future]
            try:
                batch = future.result()
                logging.info("Fetched %s article(s) from %s.", len(batch), feed.name)
                articles.extend(batch)
            except Exception as exc:  # pragma: no cover
                logging.exception("Unexpected error while processing %s: %s", feed.name, exc)
    return sorted(articles, key=lambda item: -item.published_ts)


def build_digest_prompt(candidates: list[Article]) -> str:
    prompt_payload = {
        "candidates": [
            {
                "title": article.title,
                "summary": truncate(article.summary, 200),
                "source": article.source,
                "tier": article.tier,
                "published_time": article.published_at,
                "article_url": article.url,
            }
            for article in candidates
        ]
    }
    return json.dumps(prompt_payload, ensure_ascii=True, separators=(",", ":"))


def call_groq_for_digest(candidates: list[Article], api_key: str) -> dict[str, Any] | None:
    active_candidates = list(candidates)
    reduced_payload = False
    retry_count = 0
    backoff = 2.0

    while True:
        payload = {
            "model": GROQ_MODEL,
            "temperature": 0.3,
            "max_completion_tokens": 1500,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": DIGEST_SYSTEM_PROMPT},
                {"role": "user", "content": build_digest_prompt(active_candidates)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
        except requests.RequestException as exc:
            logging.error("Digest Groq request failed: %s", exc)
            return None

        if response.status_code == 429:
            retry_count += 1
            if retry_count > 3:
                logging.error("Digest Groq rate limit persisted after 3 retries.")
                return None
            logging.warning("Digest Groq rate limited (429). Retrying in %.1fs.", backoff)
            time.sleep(backoff)
            backoff *= 2
            continue

        if response.status_code in {400, 413}:
            if not reduced_payload and len(active_candidates) > REDUCED_DIGEST_CANDIDATES:
                logging.warning(
                    "Digest Groq returned %s. Retrying with %s candidates.",
                    response.status_code,
                    REDUCED_DIGEST_CANDIDATES,
                )
                active_candidates = active_candidates[:REDUCED_DIGEST_CANDIDATES]
                reduced_payload = True
                continue
            logging.error("Digest Groq request failed with %s after payload reduction.", response.status_code)
            return None

        if response.status_code == 401:
            logging.error("Digest Groq API key is invalid or missing (401 Unauthorized).")
            return None

        if response.status_code == 403:
            logging.error("Digest Groq API access forbidden (403).")
            return None

        try:
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as exc:
            logging.error("Digest Groq response parsing failed: %s", exc)
            return None


def normalize_digest_result(result: dict[str, Any], now: datetime) -> tuple[list[dict[str, Any]], str]:
    digest_date = clean_whitespace(str(result.get("digest_date", now.date().isoformat())))
    if not isinstance(result.get("digest"), list):
        return [], digest_date

    normalized: list[dict[str, Any]] = []
    for item in result["digest"]:
        if not isinstance(item, dict):
            continue
        try:
            normalized_item = {
                "rank": int(item.get("rank", 0)),
                "full_title": clean_whitespace(str(item.get("full_title", ""))),
                "one_line_summary": clean_whitespace(str(item.get("one_line_summary", ""))),
                "source_name": clean_whitespace(str(item.get("source_name", ""))),
                "source_tier": clean_whitespace(str(item.get("source_tier", ""))).upper()[:1],
                "score": round(float(item.get("score", 0.0)), 2),
                "article_url": clean_whitespace(str(item.get("article_url", ""))),
            }
        except (TypeError, ValueError):
            continue

        if (
            normalized_item["rank"] < 1
            or not normalized_item["full_title"]
            or not normalized_item["one_line_summary"]
            or not normalized_item["source_name"]
            or not normalized_item["article_url"]
        ):
            continue
        normalized.append(normalized_item)

    normalized.sort(key=lambda item: item["rank"])
    return normalized[:5], digest_date


def format_digest_message(stories: list[dict[str, Any]], digest_date: str) -> str:
    lines = [
        f"🗞 *Top 5 AI & Tech — {sanitize_telegram_markdown_text(digest_date)}*",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for story in stories:
        title = sanitize_telegram_markdown_text(story["full_title"])
        summary = sanitize_telegram_markdown_text(story["one_line_summary"])
        source_name = sanitize_telegram_markdown_text(story["source_name"])
        lines.extend(
            [
                f"*{story['rank']}.* {title}",
                f"_{summary}_",
                f"🏛️ {source_name} ({story['source_tier']}) · ⭐ {story['score']}/10",
                f"🔗 {story['article_url']}",
                "",
            ]
        )
    lines.extend(
        [
            "━━━━━━━━━━━━━━━━━━━━━",
            "📅 Daily digest · NexusFeed",
        ]
    )
    return clean_multiline_text("\n".join(lines))


def post_to_telegram(message: str, bot_token: str, channel_id: str) -> bool:
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        response = requests.post(
            api_url,
            json={
                "chat_id": channel_id,
                "text": message,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("Daily digest Telegram post failed: %s", exc)
        return False
    return True


def main() -> int:
    configure_logging()
    secrets = require_env()
    now = utc_now()

    candidates = fetch_digest_candidates(now)[:MAX_DIGEST_CANDIDATES]
    logging.info("Prepared %s digest candidate(s).", len(candidates))
    if not candidates:
        logging.warning("No digest candidates found in the last 24 hours.")
        return 0

    groq_result = call_groq_for_digest(candidates, secrets["GROQ_API_KEY"])
    if not groq_result:
        return 1

    stories, digest_date = normalize_digest_result(groq_result, now)
    if len(stories) < 3:
        logging.warning("Not enough stories for digest today")
        return 0

    message = format_digest_message(stories, digest_date)
    if not post_to_telegram(message, secrets["TELEGRAM_BOT_TOKEN"], secrets["TELEGRAM_CHANNEL_ID"]):
        return 1

    logging.info("Daily digest sent successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
