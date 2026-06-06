from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests


ROOT = Path(__file__).resolve().parent
POSTED_PATH = ROOT / "posted_articles.json"
STATE_PATH = ROOT / "daily_state.json"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_CANDIDATES = 25
MAX_POSTS_PER_DAY = 3
MIN_HOURS_BETWEEN_POSTS = 3
MAX_ARTICLE_AGE_HOURS = 12

TRACKING_QUERY_PREFIXES = (
    "utm_",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
    "igshid",
    "ref",
    "ref_src",
    "ref_url",
    "source",
)
RED_FLAG_PATTERNS = [
    "top 10",
    "top 5",
    "best tools",
    "what is",
    "guide to",
    "how to",
    "tutorial",
    "weekly recap",
    "weekly roundup",
    "last week",
    "last month",
    "ultimate guide",
    "in 2024",
    "in 2023",
    "retrospective",
]
AI_TOPIC_KEYWORDS = (
    "agent",
    "agents",
    "ai",
    "artificial intelligence",
    "benchmark",
    "chatgpt",
    "claude",
    "copilot",
    "deepmind",
    "embedding",
    "foundation model",
    "gemini",
    "generative",
    "gpu",
    "inference",
    "llm",
    "machine learning",
    "mcp",
    "model",
    "multimodal",
    "neural",
    "openai",
    "reasoning",
    "robot",
    "safety",
    "transformer",
)
SOFTWARE_TOPIC_KEYWORDS = (
    "api",
    "compiler",
    "copilot",
    "developer",
    "engineering",
    "framework",
    "github",
    "ide",
    "inference",
    "llm",
    "mcp",
    "model",
    "open source",
    "runtime",
    "sdk",
    "software",
    "tooling",
    "vscode",
)
GENERAL_TOPIC_KEYWORDS = tuple(sorted(set(AI_TOPIC_KEYWORDS + SOFTWARE_TOPIC_KEYWORDS)))
TIER_ORDER = {"S": 0, "A": 1, "B": 2, "C": 3}


@dataclass(frozen=True)
class FeedSource:
    name: str
    tier: str
    urls: tuple[str, ...]
    topic_keywords: tuple[str, ...] = ()


@dataclass
class Article:
    article_id: str
    title: str
    summary: str
    url: str
    canonical_url: str
    url_hash: str
    story_hash: str
    source: str
    tier: str
    published_at: str
    published_ts: float
    source_rank: int


FEEDS: tuple[FeedSource, ...] = (
    FeedSource("OpenAI", "S", ("https://openai.com/news/rss.xml",)),
    FeedSource(
        "Anthropic",
        "S",
        (
            "https://www.anthropic.com/news/rss.xml",
            "https://www.anthropic.com/feed.xml",
        ),
    ),
    FeedSource(
        "Google AI",
        "S",
        (
            "https://blog.google/technology/ai/rss/",
            "https://blog.research.google/feeds/posts/default?alt=rss",
        ),
    ),
    FeedSource("HuggingFace", "S", ("https://huggingface.co/blog/feed.xml",)),
    FeedSource(
        "Microsoft AI",
        "S",
        (
            "https://news.microsoft.com/source/topics/ai/feed/",
            "https://blogs.microsoft.com/ai/feed/",
            "https://blogs.microsoft.com/feed/",
        ),
        topic_keywords=GENERAL_TOPIC_KEYWORDS,
    ),
    FeedSource(
        "TechCrunch",
        "A",
        (
            "https://techcrunch.com/category/artificial-intelligence/feed/",
            "https://techcrunch.com/tag/artificial-intelligence/feed/",
        ),
    ),
    FeedSource(
        "The Verge",
        "A",
        ("https://www.theverge.com/rss/index.xml",),
        topic_keywords=GENERAL_TOPIC_KEYWORDS,
    ),
    FeedSource("Ars Technica", "A", ("https://arstechnica.com/ai/feed/",)),
    FeedSource("MarkTechPost", "A", ("https://www.marktechpost.com/feed/",)),
    FeedSource("Wired AI", "A", ("https://www.wired.com/feed/tag/ai/latest/rss",)),
    FeedSource(
        "MIT News AI",
        "B",
        ("https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml",),
    ),
    FeedSource(
        "InfoQ AI/ML",
        "B",
        ("https://feed.infoq.com/",),
        topic_keywords=GENERAL_TOPIC_KEYWORDS,
    ),
    FeedSource("Unite AI", "B", ("https://www.unite.ai/feed/",)),
    FeedSource("arXiv cs.AI", "C", ("https://rss.arxiv.org/rss/cs.AI",)),
    FeedSource(
        "Hacker News",
        "C",
        ("https://news.ycombinator.com/rss",),
        topic_keywords=GENERAL_TOPIC_KEYWORDS,
    ),
)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    logging.Formatter.converter = time.gmtime


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def default_state(now: datetime | None = None) -> dict[str, Any]:
    current = now or utc_now()
    return {
        "date": current.date().isoformat(),
        "posts_today": 0,
        "last_post_time": None,
        "pending_best": None,
    }


def default_posted() -> dict[str, Any]:
    return {
        "version": 1,
        "articles": {},
        "story_hashes": [],
    }


def load_json(path: Path, default_factory) -> dict[str, Any]:
    if not path.exists():
        return default_factory()
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError) as exc:
        logging.warning("Failed to load %s: %s. Recreating with defaults.", path.name, exc)
    return default_factory()


def save_json(path: Path, payload: dict[str, Any]) -> None:
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temp_path.replace(path)


def sanitize_posted(data: dict[str, Any]) -> dict[str, Any]:
    articles = data.get("articles")
    story_hashes = data.get("story_hashes")
    return {
        "version": 1,
        "articles": articles if isinstance(articles, dict) else {},
        "story_hashes": story_hashes if isinstance(story_hashes, list) else [],
    }


def reset_state_if_needed(state: dict[str, Any], now: datetime) -> tuple[dict[str, Any], bool]:
    if state.get("date") == now.date().isoformat():
        return state, False
    logging.info("Resetting daily state for new UTC day.")
    return default_state(now), True


def clean_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def strip_html(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>", " ", value or "", flags=re.IGNORECASE)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    return clean_whitespace(html.unescape(value))


def truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "…"


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    query_items = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered.startswith("utm_") or lowered in TRACKING_QUERY_PREFIXES:
            continue
        query_items.append((key, val))
    cleaned = parsed._replace(
        scheme=parsed.scheme.lower() or "https",
        netloc=parsed.netloc.lower(),
        query=urlencode(query_items, doseq=True),
        fragment="",
    )
    normalized = urlunparse(cleaned).rstrip("/")
    return normalized


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_title(title: str) -> str:
    normalized = title.lower()
    normalized = re.sub(r"https?://\S+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return clean_whitespace(normalized)


def build_story_hash(title: str) -> str:
    return stable_hash(normalize_title(title))


def contains_topic_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    haystack = f" {text.lower()} "
    return any(keyword.lower() in haystack for keyword in keywords)


def is_red_flag(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(pattern in text for pattern in RED_FLAG_PATTERNS)


def parse_entry_datetime(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        value = getattr(entry, key, None)
        if value:
            try:
                return datetime(*value[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                continue
    for key in ("published", "updated"):
        value = getattr(entry, key, None)
        if value:
            try:
                return parsedate_to_datetime(value).astimezone(timezone.utc)
            except (TypeError, ValueError, IndexError):
                continue
    return None


def extract_entry_text(entry: Any) -> tuple[str, str]:
    title = clean_whitespace(getattr(entry, "title", ""))
    summary_raw = getattr(entry, "summary", "") or getattr(entry, "description", "")
    if not summary_raw and getattr(entry, "content", None):
        try:
            summary_raw = entry.content[0].value
        except (IndexError, AttributeError, KeyError, TypeError):
            summary_raw = ""
    summary = truncate(strip_html(summary_raw), 300)
    return title, summary


def fetch_feed(feed: FeedSource, now: datetime) -> list[Article]:
    cutoff = now - timedelta(hours=MAX_ARTICLE_AGE_HOURS)
    headers = {
        "User-Agent": "NexusFeedBot/1.0 (+https://github.com/mohabdelkarim/NexusFeed)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
    }
    last_error = None
    response_content = None

    for url in feed.urls:
        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            response_content = response.content
            break
        except requests.RequestException as exc:
            last_error = exc
            logging.warning("Feed fetch failed for %s via %s: %s", feed.name, url, exc)

    if response_content is None:
        if last_error:
            logging.warning("Skipping %s after all feed URLs failed.", feed.name)
        return []

    parsed = feedparser.parse(response_content)
    articles: list[Article] = []

    for idx, entry in enumerate(parsed.entries):
        published_dt = parse_entry_datetime(entry)
        if not published_dt or published_dt < cutoff or published_dt > now + timedelta(minutes=5):
            continue

        title, summary = extract_entry_text(entry)
        if not title:
            continue
        if is_red_flag(title, summary):
            continue

        entry_text = clean_whitespace(f"{title} {summary}")
        if feed.topic_keywords and not contains_topic_keyword(entry_text, feed.topic_keywords):
            continue

        raw_url = clean_whitespace(getattr(entry, "link", ""))
        if not raw_url:
            continue

        canonical_url = canonicalize_url(raw_url)
        article = Article(
            article_id=f"{feed.name.lower().replace(' ', '-')}-{idx}",
            title=title,
            summary=summary,
            url=raw_url,
            canonical_url=canonical_url,
            url_hash=stable_hash(canonical_url),
            story_hash=build_story_hash(title),
            source=feed.name,
            tier=feed.tier,
            published_at=isoformat_utc(published_dt),
            published_ts=published_dt.timestamp(),
            source_rank=TIER_ORDER[feed.tier],
        )
        articles.append(article)

    articles.sort(key=lambda item: item.published_ts, reverse=True)
    return articles


def fetch_all_feeds(now: datetime) -> list[Article]:
    all_articles: list[Article] = []
    with ThreadPoolExecutor(max_workers=15) as executor:
        future_map = {executor.submit(fetch_feed, feed, now): feed for feed in FEEDS}
        for future in as_completed(future_map):
            feed = future_map[future]
            try:
                articles = future.result()
                logging.info("Fetched %s article(s) from %s.", len(articles), feed.name)
                all_articles.extend(articles)
            except Exception as exc:  # pragma: no cover - defensive resilience path
                logging.exception("Unexpected error while processing %s: %s", feed.name, exc)
    all_articles.sort(key=lambda item: item.published_ts, reverse=True)
    return all_articles


def dedupe_candidates(articles: list[Article], posted: dict[str, Any]) -> list[Article]:
    posted_articles = posted.get("articles", {})
    posted_url_hashes = set(posted_articles.keys())
    posted_story_hashes = set(posted.get("story_hashes", []))
    best_by_story: dict[str, Article] = {}

    for article in articles:
        if article.url_hash in posted_url_hashes or article.story_hash in posted_story_hashes:
            continue

        existing = best_by_story.get(article.story_hash)
        if existing is None:
            best_by_story[article.story_hash] = article
            continue

        current_key = (article.source_rank, -article.published_ts)
        existing_key = (existing.source_rank, -existing.published_ts)
        if current_key < existing_key:
            best_by_story[article.story_hash] = article

    deduped = list(best_by_story.values())
    deduped.sort(key=lambda item: (item.source_rank, -item.published_ts))
    return deduped


def shortlist_candidates(articles: list[Article]) -> list[Article]:
    ranked = sorted(
        articles,
        key=lambda item: (item.source_rank, -item.published_ts),
    )
    return ranked[:MAX_CANDIDATES]


def build_groq_prompt(candidates: list[Article]) -> str:
    compact_candidates = []
    for article in candidates:
        compact_candidates.append(
            {
                "article_id": article.article_id,
                "title": article.title,
                "summary": article.summary,
                "source": article.source,
                "tier": article.tier,
                "published_time_utc": article.published_at,
            }
        )

    instruction = {
        "role": (
            "You are an autonomous Telegram news curator bot for AI and software engineering news. "
            "You prioritize reliability, freshness, and zero noise over volume."
        ),
        "task": (
            "Score every article, reject low-signal items, pick the single best article if any deserve attention, "
            "and draft the Telegram copy fields."
        ),
        "scoring": {
            "novelty": "0-3",
            "impact": "0-3",
            "freshness": "0-2",
            "source_credibility": "0-2",
            "total": "0.00-10.00",
        },
        "hard_rules": [
            "Set disqualify=true and total_score=0.0 for tutorials, explainers, recaps, roundups, guides, listicles, or stale items.",
            "Favor breaking news, major launches, research breakthroughs, platform moves, policy shifts, and high-signal engineering updates.",
            "Prefer official lab posts and top-tier publications when duplicates or near-duplicates exist.",
            "At most one article can be selected.",
            "Write concise, professional Telegram copy with a one-line summary.",
        ],
        "output_contract": {
            "selected_article_id": "string or null",
            "should_post_now": "boolean",
            "decision_reason": "short string",
            "articles": [
                {
                    "article_id": "string",
                    "novelty": "number",
                    "impact": "number",
                    "freshness": "number",
                    "source_credibility": "number",
                    "total_score": "number with two decimals",
                    "disqualify": "boolean",
                    "reason": "short string",
                }
            ],
            "telegram": {
                "headline": "plain text",
                "summary": "plain text single sentence",
                "score_badge": "plain text like 8.9/10",
            },
        },
        "candidates": compact_candidates,
    }
    return json.dumps(instruction, separators=(",", ":"), ensure_ascii=True)


class GroqError(RuntimeError):
    pass


def call_groq(candidates: list[Article]) -> dict[str, Any] | None:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logging.error("GROQ_API_KEY is missing. Skipping AI scoring cleanly.")
        return None

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.3,
        "max_completion_tokens": 2000,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a strict AI news curator. Return only valid JSON. "
                    "Never include prose outside the JSON object."
                ),
            },
            {
                "role": "user",
                "content": build_groq_prompt(candidates),
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    delay = 2.0
    for attempt in range(1, 6):
        try:
            response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
        except requests.RequestException as exc:
            logging.warning("Groq request failed on attempt %s: %s", attempt, exc)
            if attempt == 5:
                return None
            time.sleep(delay)
            delay *= 2
            continue

        if response.status_code == 429:
            retry_after = response.headers.get("retry-after")
            wait_seconds = float(retry_after) if retry_after and retry_after.isdigit() else delay
            logging.warning("Groq rate limited. Waiting %.1f second(s).", wait_seconds)
            time.sleep(wait_seconds)
            delay *= 2
            continue

        if response.status_code in {500, 502, 503}:
            logging.warning("Groq server error %s on attempt %s.", response.status_code, attempt)
            if attempt == 5:
                return None
            time.sleep(delay)
            delay *= 2
            continue

        if response.status_code == 400:
            logging.error("Groq rejected the payload with 400. Skipping without retry.")
            return None

        if response.status_code == 413:
            logging.error("Groq rejected the payload with 413. Input was too large; skipping without retry.")
            return None

        try:
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as exc:
            logging.error("Failed to parse Groq response: %s", exc)
            return None

    return None


def score_map_from_result(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = result.get("articles")
    if not isinstance(items, list):
        return {}
    output: dict[str, dict[str, Any]] = {}
    for item in items:
        if isinstance(item, dict) and isinstance(item.get("article_id"), str):
            output[item["article_id"]] = item
    return output


def pick_best_article(candidates: list[Article], result: dict[str, Any]) -> tuple[Article | None, dict[str, Any] | None]:
    score_map = score_map_from_result(result)
    selected_id = result.get("selected_article_id")
    if isinstance(selected_id, str):
        for article in candidates:
            if article.article_id == selected_id and article.article_id in score_map:
                return article, score_map[article.article_id]

    best_pair: tuple[Article, dict[str, Any]] | None = None
    for article in candidates:
        score = score_map.get(article.article_id)
        if not score or score.get("disqualify"):
            continue
        total = float(score.get("total_score", 0.0))
        if best_pair is None:
            best_pair = (article, score)
            continue
        best_total = float(best_pair[1].get("total_score", 0.0))
        current_key = (total, -article.source_rank, article.published_ts)
        best_key = (best_total, -best_pair[0].source_rank, best_pair[0].published_ts)
        if current_key > best_key:
            best_pair = (article, score)

    return best_pair if best_pair else (None, None)


def article_payload(article: Article, score: dict[str, Any], telegram: dict[str, Any], saved_at: datetime) -> dict[str, Any]:
    total_score = round(float(score.get("total_score", 0.0)), 2)
    return {
        "article_id": article.article_id,
        "title": article.title,
        "summary": article.summary,
        "url": article.url,
        "canonical_url": article.canonical_url,
        "url_hash": article.url_hash,
        "story_hash": article.story_hash,
        "source": article.source,
        "tier": article.tier,
        "published_at": article.published_at,
        "score": {
            "novelty": float(score.get("novelty", 0.0)),
            "impact": float(score.get("impact", 0.0)),
            "freshness": float(score.get("freshness", 0.0)),
            "source_credibility": float(score.get("source_credibility", 0.0)),
            "total_score": total_score,
            "reason": clean_whitespace(str(score.get("reason", ""))),
        },
        "telegram": {
            "headline": clean_whitespace(str(telegram.get("headline") or article.title)),
            "summary": clean_whitespace(str(telegram.get("summary") or article.summary or article.title)),
            "score_badge": clean_whitespace(str(telegram.get("score_badge") or f"{total_score:.2f}/10")),
        },
        "saved_at": isoformat_utc(saved_at),
    }


def pending_is_better(candidate: dict[str, Any], existing: dict[str, Any] | None) -> bool:
    if not existing:
        return True
    candidate_score = float(candidate.get("score", {}).get("total_score", 0.0))
    existing_score = float(existing.get("score", {}).get("total_score", 0.0))
    if candidate_score != existing_score:
        return candidate_score > existing_score
    candidate_tier = TIER_ORDER.get(str(candidate.get("tier", "C")), 99)
    existing_tier = TIER_ORDER.get(str(existing.get("tier", "C")), 99)
    if candidate_tier != existing_tier:
        return candidate_tier < existing_tier
    return parse_iso_datetime(candidate.get("published_at")) >= parse_iso_datetime(existing.get("published_at"))


def cooldown_ok(state: dict[str, Any], now: datetime) -> bool:
    last_post_time = parse_iso_datetime(state.get("last_post_time"))
    if not last_post_time:
        return True
    return now - last_post_time >= timedelta(hours=MIN_HOURS_BETWEEN_POSTS)


def is_quiet_hours(now: datetime) -> bool:
    return now.hour >= 22 or now.hour < 7


def is_peak_hours(now: datetime) -> bool:
    return 14 <= now.hour < 22


def is_2130_or_later(now: datetime) -> bool:
    return now.hour == 21 and now.minute >= 30


def posting_window_allows(score_total: float, now: datetime) -> bool:
    if is_quiet_hours(now) and score_total < 9.5:
        return False
    return True


def can_post_now(state: dict[str, Any], score_total: float, now: datetime) -> bool:
    if int(state.get("posts_today", 0)) >= MAX_POSTS_PER_DAY:
        return False
    if not cooldown_ok(state, now):
        return False
    return posting_window_allows(score_total, now)


def escape_markdown_v2(value: str) -> str:
    specials = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{char}" if char in specials else char for char in value)


def format_telegram_message(payload: dict[str, Any]) -> str:
    headline = escape_markdown_v2(payload["telegram"]["headline"])
    summary = escape_markdown_v2(payload["telegram"]["summary"])
    source = escape_markdown_v2(payload["source"])
    score = escape_markdown_v2(payload["telegram"]["score_badge"])
    url = payload["url"]
    return (
        f"*{headline}*\n"
        f"{summary}\n\n"
        f"*Source:* {source}\n"
        f"*Score:* {score}\n\n"
        f"{url}"
    )


def post_to_telegram(payload: dict[str, Any]) -> bool:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
    if not bot_token or not channel_id:
        logging.error("Telegram credentials are missing. Skipping post cleanly.")
        return False

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response_payload = {
        "chat_id": channel_id,
        "text": format_telegram_message(payload),
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }

    try:
        response = requests.post(api_url, json=response_payload, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("Telegram post failed: %s", exc)
        return False

    logging.info("Posted to Telegram: %s", payload["title"])
    return True


def mark_as_posted(posted: dict[str, Any], payload: dict[str, Any], posted_at: datetime) -> None:
    posted["articles"][payload["url_hash"]] = {
        "title": payload["title"],
        "url": payload["url"],
        "canonical_url": payload["canonical_url"],
        "source": payload["source"],
        "story_hash": payload["story_hash"],
        "posted_at": isoformat_utc(posted_at),
    }
    if payload["story_hash"] not in posted["story_hashes"]:
        posted["story_hashes"].append(payload["story_hash"])
        posted["story_hashes"].sort()


def clear_pending_if_matches(state: dict[str, Any], payload: dict[str, Any]) -> None:
    pending = state.get("pending_best")
    if not isinstance(pending, dict):
        return
    if pending.get("url_hash") == payload.get("url_hash") or pending.get("story_hash") == payload.get("story_hash"):
        state["pending_best"] = None


def persist_state_files(state: dict[str, Any], posted: dict[str, Any]) -> None:
    save_json(STATE_PATH, state)
    save_json(POSTED_PATH, posted)


def main() -> int:
    configure_logging()
    now = utc_now()
    run_started_at = isoformat_utc(now)

    posted = sanitize_posted(load_json(POSTED_PATH, default_posted))
    state = load_json(STATE_PATH, lambda: default_state(now))
    state, _ = reset_state_if_needed(state, now)

    if int(state.get("posts_today", 0)) >= MAX_POSTS_PER_DAY:
        logging.info("Daily post cap reached. Exiting.")
        persist_state_files(state, posted)
        return 0

    preexisting_pending = state.get("pending_best") if isinstance(state.get("pending_best"), dict) else None
    fetched_articles = fetch_all_feeds(now)
    candidates = dedupe_candidates(fetched_articles, posted)
    logging.info("Found %s deduplicated fresh candidate(s).", len(candidates))

    pending_updated = False

    if candidates:
        shortlist = shortlist_candidates(candidates)
        logging.info("Sending %s candidate(s) to Groq for scoring.", len(shortlist))
        groq_result = call_groq(shortlist)
        if groq_result:
            best_article, best_score = pick_best_article(shortlist, groq_result)
            if best_article and best_score and not best_score.get("disqualify"):
                telegram = groq_result.get("telegram") if isinstance(groq_result.get("telegram"), dict) else {}
                payload = article_payload(best_article, best_score, telegram, now)
                total_score = float(payload["score"]["total_score"])

                if total_score >= 8.5 and can_post_now(state, total_score, now):
                    if post_to_telegram(payload):
                        mark_as_posted(posted, payload, now)
                        state["posts_today"] = int(state.get("posts_today", 0)) + 1
                        state["last_post_time"] = isoformat_utc(now)
                        clear_pending_if_matches(state, payload)
                        persist_state_files(state, posted)
                    return 0

                if total_score >= 6.0:
                    if pending_is_better(payload, state.get("pending_best")):
                        state["pending_best"] = payload
                        pending_updated = True
                        logging.info("Saved %s as pending_best with score %.2f.", payload["title"], total_score)

    pending_to_post = None
    if isinstance(preexisting_pending, dict):
        pending_score = float(preexisting_pending.get("score", {}).get("total_score", 0.0))
        if can_post_now(state, pending_score, now):
            saved_at = parse_iso_datetime(preexisting_pending.get("saved_at"))
            is_from_prior_run = saved_at is not None and isoformat_utc(saved_at) < run_started_at
            if is_from_prior_run:
                if is_peak_hours(now):
                    pending_to_post = preexisting_pending
                elif is_2130_or_later(now) and int(state.get("posts_today", 0)) == 0 and pending_score >= 6.0:
                    pending_to_post = preexisting_pending

    if pending_to_post and post_to_telegram(pending_to_post):
        mark_as_posted(posted, pending_to_post, now)
        state["posts_today"] = int(state.get("posts_today", 0)) + 1
        state["last_post_time"] = isoformat_utc(now)
        clear_pending_if_matches(state, pending_to_post)
        persist_state_files(state, posted)
        return 0

    if not candidates:
        logging.info("No new articles qualified for scoring in this run.")
    elif not pending_updated:
        logging.info("No candidate qualified for posting or pending retention.")

    persist_state_files(state, posted)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - production safety net
        logging.exception("Unhandled error: %s", exc)
        raise SystemExit(0)
