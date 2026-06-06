from __future__ import annotations

import hashlib
import html
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import feedparser
import requests
from dateutil.parser import isoparse


ROOT = Path(__file__).resolve().parent
POSTED_PATH = ROOT / "posted_articles.json"
STATE_PATH = ROOT / "daily_state.json"
POSTING_INTENT_PATH = ROOT / "posting_intent.json"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.3-70b-versatile"
MAX_CANDIDATES = 25
MAX_POSTS_PER_DAY = 3
MIN_HOURS_BETWEEN_POSTS = 3
MAX_ARTICLE_AGE_HOURS = 12
TITLE_SIMILARITY_THRESHOLD = 0.80
POSTED_RETENTION_DAYS = 7
RECENT_TITLE_LOOKBACK_HOURS = 24
REQUIRED_SECRETS = [
    "GROQ_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "GIT_TOKEN",
]
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
    "top 7",
    "top 15",
    "top 20",
    "best tools",
    "best practices",
    "best ai tools",
    "what is",
    "guide to",
    "how to",
    "tutorial",
    "weekly recap",
    "weekly roundup",
    "last week",
    "last month",
    "ultimate guide",
    "everything you need to know",
    "in 2023",
    "in 2024",
    "previously announced",
    "announced last",
    "looking back",
    "retrospective",
    "history of",
    "beginners guide",
    "beginner's guide",
    "getting started",
    "step by step",
    "step-by-step",
    "cheat sheet",
    "roundup",
]
STOP_WORDS = {
    "a",
    "an",
    "and",
    "announces",
    "announcing",
    "for",
    "from",
    "in",
    "launches",
    "new",
    "of",
    "on",
    "releases",
    "the",
    "to",
    "with",
}
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

SCORING_SYSTEM_PROMPT = """
You are a strict AI news curator for a Telegram channel targeting
software engineers and AI researchers.

Your job per run:
1. Score every article using the 4-criteria system (max 10.00)
2. Apply red flags (score = 0.00 if ANY red flag matches)
3. Select the single best article
4. Decide: POST_NOW / SAVE_PENDING / SKIP
5. If decision != SKIP: write the ready Telegram message

SCORING CRITERIA:
- Novelty (0.00-3.00): new release=3, research=2.5, industry move=2,
  update=1.5, opinion=0.5, tutorial=0.2, recap=0
- Impact (0.00-3.00): everyone=3, all devs=2.5, niche=1.5, one company=0.5
- Freshness (0.00-2.00): <1h=2, 1-3h=1.5, 3-6h=1, 6-12h=0.5, >12h=0
- Source (0.00-2.00): Tier S=2, A=1.5, B=1, C=0.5

RED FLAGS (auto 0.00): "top 10", "top 5", "best tools", "what is",
"guide to", "how to", "tutorial", "weekly recap", "roundup",
"last week", "last month", "ultimate guide", "in 2023", "in 2024",
"retrospective", "looking back", "everything you need to know"

DECISION RULES:
- best_score >= 8.5 -> POST_NOW
- best_score >= 6.0 -> SAVE_PENDING
- best_score < 6.0  -> SKIP

Respond ONLY with valid JSON. No markdown, no explanation outside JSON.
""".strip()

TELEGRAM_MESSAGE_TEMPLATE = """
━━━━━━━━━━━━━━━━━━━━━
🔥 *{HEADLINE}*

{1-2 sentence summary in Greek or English - match source language}

🏛️ Source: {Source Name} ({Tier S/A/B/C})
⏰ Published: {X hours ago}
⭐ Score: {total_score}/10

🔗 {article_url}
━━━━━━━━━━━━━━━━━━━━━
""".strip()

GROQ_RESPONSE_SCHEMA = {
    "articles": [
        {
            "index": 0,
            "title": "string",
            "novelty_score": 0.0,
            "impact_score": 0.0,
            "freshness_score": 0.0,
            "source_score": 0.0,
            "total_score": 0.0,
            "red_flag": False,
            "red_flag_reason": "string or null",
            "reason": "string (1 sentence why this score)",
        }
    ],
    "best_index": 0,
    "best_score": 0.0,
    "recommendation": "POST_NOW | SAVE_PENDING | SKIP",
    "telegram_message": "string (ready-to-send Telegram message in Markdown)",
}


@dataclass(frozen=True)
class FeedSource:
    name: str
    tier: str
    urls: tuple[str, ...]
    topic_keywords: tuple[str, ...] = ()


@dataclass
class Article:
    index: int
    title: str
    summary: str
    url: str
    canonical_url: str
    url_hash: str
    cleaned_title: str
    source: str
    tier: str
    published_at: str
    published_ts: float
    source_rank: int


FEEDS: tuple[FeedSource, ...] = (
    FeedSource("OpenAI", "S", ("https://openai.com/news/rss.xml",)),
    # DEAD - needs manual fix (no confirmed working Anthropic RSS endpoint found)
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
    # DEAD - needs manual fix (current Unite AI feed URLs return non-parseable content)
    FeedSource("Unite AI", "B", ("https://www.unite.ai/feed/",)),
    # DEAD - needs manual fix (local feedparser SSL verification fails on current arXiv feed URL)
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
        return isoparse(value).astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def require_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for key in REQUIRED_SECRETS:
        value = os.environ.get(key)
        if not value:
            raise EnvironmentError(f"Missing required secret: {key}")
        values[key] = value
    return values


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
        "hashes": [],
        "recent_titles": [],
        "hash_records": [],
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
    hashes = data.get("hashes")
    recent_titles = data.get("recent_titles")
    hash_records = data.get("hash_records")
    return {
        "hashes": hashes if isinstance(hashes, list) else [],
        "recent_titles": recent_titles if isinstance(recent_titles, list) else [],
        "hash_records": hash_records if isinstance(hash_records, list) else [],
    }


def cleanup_posted_history(posted: dict[str, Any], now: datetime) -> None:
    cutoff = now - timedelta(days=POSTED_RETENTION_DAYS)
    recent_titles: list[dict[str, Any]] = []
    for item in posted.get("recent_titles", []):
        if not isinstance(item, dict):
            continue
        posted_at = parse_iso_datetime(item.get("posted_at"))
        if posted_at and posted_at >= cutoff:
            recent_titles.append(item)

    hash_records: list[dict[str, Any]] = []
    for item in posted.get("hash_records", []):
        if not isinstance(item, dict):
            continue
        posted_at = parse_iso_datetime(item.get("posted_at"))
        if posted_at and posted_at >= cutoff and isinstance(item.get("hash"), str):
            hash_records.append(item)

    posted["recent_titles"] = recent_titles
    posted["hash_records"] = hash_records
    posted["hashes"] = sorted({item["hash"] for item in hash_records})


def reset_state_if_needed(state: dict[str, Any], now: datetime) -> tuple[dict[str, Any], bool]:
    if state.get("date") == now.date().isoformat():
        return state, False
    logging.info("Resetting daily state for new UTC day.")
    return default_state(now), True


def clean_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def clean_multiline_text(value: str) -> str:
    lines = [line.rstrip() for line in str(value).replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def strip_html(value: str) -> str:
    value = re.sub(r"<script[\s\S]*?</script>", " ", value or "", flags=re.IGNORECASE)
    value = re.sub(r"<style[\s\S]*?</style>", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", " ", value)
    return clean_whitespace(html.unescape(value))


def truncate(value: str, max_chars: int) -> str:
    if len(value) <= max_chars:
        return value
    return value[: max_chars - 1].rstrip() + "..."


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
    return urlunparse(cleaned).rstrip("/")


def stable_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_title(title: str) -> str:
    normalized = title.lower()
    normalized = re.sub(r"https?://\S+", " ", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    words = [word for word in normalized.split() if word and word not in STOP_WORDS]
    return " ".join(words)


def word_overlap_ratio(left: str, right: str) -> float:
    left_words = set(left.split())
    right_words = set(right.split())
    if not left_words or not right_words:
        return 0.0
    return len(left_words & right_words) / max(len(left_words), len(right_words))


def title_is_duplicate(cleaned_title: str, other_title: str) -> bool:
    return word_overlap_ratio(cleaned_title, other_title) >= TITLE_SIMILARITY_THRESHOLD


def _get_article_field(article: Any, field: str) -> str:
    if isinstance(article, dict):
        return str(article.get(field) or "")
    return str(getattr(article, field, "") or "")


def find_local_red_flag_pattern(article: Any) -> str | None:
    text = ((_get_article_field(article, "title") + " " + _get_article_field(article, "summary")[:300]).lower())
    for pattern in RED_FLAG_PATTERNS:
        if pattern in text:
            return pattern
    return None


def has_local_red_flag(article: Any) -> bool:
    """
    Hard local check BEFORE sending to Groq.
    Returns True if article should be auto-rejected.
    Check both title and first 300 chars of summary.
    Case-insensitive. If ANY pattern matches -> True.
    """
    return find_local_red_flag_pattern(article) is not None


def contains_topic_keyword(text: str, keywords: tuple[str, ...]) -> bool:
    haystack = f" {text.lower()} "
    return any(keyword.lower() in haystack for keyword in keywords)


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
    response_content = None

    for url in feed.urls:
        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            response_content = response.content
            break
        except requests.RequestException as exc:
            logging.warning("Feed fetch failed for %s via %s: %s", feed.name, url, exc)

    if response_content is None:
        logging.warning("Skipping %s after all feed URLs failed.", feed.name)
        return []

    parsed = feedparser.parse(response_content)
    articles: list[Article] = []

    for entry in parsed.entries:
        published_dt = parse_entry_datetime(entry)
        if not published_dt or published_dt < cutoff or published_dt > now + timedelta(minutes=5):
            continue

        title, summary = extract_entry_text(entry)
        if not title:
            continue

        entry_text = clean_whitespace(f"{title} {summary}")
        if feed.topic_keywords and not contains_topic_keyword(entry_text, feed.topic_keywords):
            continue

        raw_url = clean_whitespace(getattr(entry, "link", ""))
        if not raw_url:
            continue

        canonical_url = canonicalize_url(raw_url)
        articles.append(
            Article(
                index=-1,
                title=title,
                summary=summary,
                url=raw_url,
                canonical_url=canonical_url,
                url_hash=stable_hash(raw_url),
                cleaned_title=normalize_title(title),
                source=feed.name,
                tier=feed.tier,
                published_at=isoformat_utc(published_dt),
                published_ts=published_dt.timestamp(),
                source_rank=TIER_ORDER[feed.tier],
            )
        )

    return sorted(articles, key=lambda item: item.published_ts, reverse=True)


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
            except Exception as exc:  # pragma: no cover
                logging.exception("Unexpected error while processing %s: %s", feed.name, exc)
    return sorted(all_articles, key=lambda item: (item.source_rank, -item.published_ts))


def is_duplicate_against_posted(article: Article, posted: dict[str, Any], now: datetime) -> bool:
    if article.url_hash in set(posted.get("hashes", [])):
        return True

    recent_cutoff = now - timedelta(hours=RECENT_TITLE_LOOKBACK_HOURS)
    for item in posted.get("recent_titles", []):
        if not isinstance(item, dict):
            continue
        posted_at = parse_iso_datetime(item.get("posted_at"))
        cleaned_title = clean_whitespace(str(item.get("cleaned_title", "")))
        if posted_at and posted_at >= recent_cutoff and cleaned_title and title_is_duplicate(article.cleaned_title, cleaned_title):
            return True
    return False


def dedupe_candidates(articles: list[Article], posted: dict[str, Any], now: datetime) -> list[Article]:
    chosen: list[Article] = []
    for article in articles:
        matched_pattern = find_local_red_flag_pattern(article)
        if matched_pattern:
            logging.warning('Local red flag: [%s] matched pattern "%s"', article.title, matched_pattern)
            continue

        if is_duplicate_against_posted(article, posted, now):
            continue

        duplicate_index = None
        for idx, existing in enumerate(chosen):
            same_story = article.url_hash == existing.url_hash or title_is_duplicate(article.cleaned_title, existing.cleaned_title)
            if same_story:
                duplicate_index = idx
                break

        if duplicate_index is None:
            chosen.append(article)
            continue

        existing = chosen[duplicate_index]
        current_key = (article.source_rank, -article.published_ts)
        existing_key = (existing.source_rank, -existing.published_ts)
        if current_key < existing_key:
            chosen[duplicate_index] = article

    for index, article in enumerate(sorted(chosen, key=lambda item: (item.source_rank, -item.published_ts))):
        article.index = index
    return chosen[:MAX_CANDIDATES]


def hours_ago_text(published_ts: float, now: datetime) -> str:
    hours = max(0.0, (now.timestamp() - published_ts) / 3600)
    if hours < 1:
        return "<1 hour ago"
    if hours < 2:
        return "1 hour ago"
    return f"{int(hours)} hours ago"


def parse_retry_after(header_value: str, fallback: float) -> float:
    """
    Parses Groq's retry-after header.
    Supports:
      - Integer seconds: "30"
      - Float seconds: "1.5"
      - HTTP-date: "Fri, 06 Jun 2026 14:00:00 GMT"
    Returns seconds to wait as float. Min=1, Max=120.
    Falls back to fallback if unparseable.
    """
    if not header_value:
        return fallback
    try:
        return max(1.0, min(120.0, float(header_value)))
    except ValueError:
        pass
    try:
        retry_dt = parsedate_to_datetime(header_value)
        now = datetime.now(timezone.utc)
        delta = (retry_dt - now).total_seconds()
        return max(1.0, min(120.0, delta))
    except Exception:
        return fallback


def rebuild_prompt_with_summary_limit(candidates: list[Article], char_limit: int) -> str:
    now = utc_now()
    prompt_payload = {
        "response_schema": GROQ_RESPONSE_SCHEMA,
        "telegram_message_template": TELEGRAM_MESSAGE_TEMPLATE,
        "telegram_rules": [
            "Headline: max 80 chars, do NOT copy title verbatim - rewrite concisely",
            "Summary: 1-2 sentences max, no fluff, no 'in this article we...'",
            "Never include: ads, affiliate links, author names, publication dates as text",
            "Telegram Markdown only: use *bold*, no HTML tags",
            "Total message length: max 300 chars excluding URL",
        ],
        "candidates": [
            {
                "index": article.index,
                "title": article.title,
                "summary": truncate(article.summary, char_limit),
                "source": article.source,
                "tier": article.tier,
                "published_time_utc": article.published_at,
                "published_relative": hours_ago_text(article.published_ts, now),
                "article_url": article.url,
            }
            for article in candidates
        ],
    }
    return json.dumps(prompt_payload, ensure_ascii=True, separators=(",", ":"))


def build_groq_prompt(candidates: list[Article], now: datetime) -> str:
    prompt_payload = {
        "response_schema": GROQ_RESPONSE_SCHEMA,
        "telegram_message_template": TELEGRAM_MESSAGE_TEMPLATE,
        "telegram_rules": [
            "Headline: max 80 chars, do NOT copy title verbatim - rewrite concisely",
            "Summary: 1-2 sentences max, no fluff, no 'in this article we...'",
            "Never include: ads, affiliate links, author names, publication dates as text",
            "Telegram Markdown only: use *bold*, no HTML tags",
            "Total message length: max 300 chars excluding URL",
        ],
        "candidates": [
            {
                "index": article.index,
                "title": article.title,
                "summary": article.summary,
                "source": article.source,
                "tier": article.tier,
                "published_time_utc": article.published_at,
                "published_relative": hours_ago_text(article.published_ts, now),
                "article_url": article.url,
            }
            for article in candidates
        ],
    }
    return json.dumps(prompt_payload, ensure_ascii=True, separators=(",", ":"))


def call_groq(candidates: list[Article], now: datetime, api_key: str) -> dict[str, Any] | None:
    prompt_content = build_groq_prompt(candidates, now)
    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.3,
        "max_completion_tokens": 2000,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SCORING_SYSTEM_PROMPT},
            {"role": "user", "content": prompt_content},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    backoff = 2.0
    for attempt in range(1, 6):
        try:
            response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
        except requests.RequestException as exc:
            logging.warning("Groq request failed on attempt %s: %s", attempt, exc)
            if attempt == 5:
                return None
            time.sleep(backoff)
            backoff *= 2
            continue

        if response.status_code == 429:
            raw_header = response.headers.get("retry-after", "")
            wait_seconds = parse_retry_after(raw_header, backoff)
            logging.warning("Groq rate limited (429). Waiting %.1fs (retry-after: '%s').", wait_seconds, raw_header)
            time.sleep(wait_seconds)
            backoff = min(backoff * 2, 120.0)
            continue

        if response.status_code in {500, 502, 503}:
            logging.warning("Groq server error %s on attempt %s.", response.status_code, attempt)
            if attempt == 5:
                return None
            time.sleep(backoff)
            backoff *= 2
            continue

        if response.status_code == 400:
            logging.warning("Groq 400 Bad Request on attempt %s.", attempt)
            if attempt == 1:
                logging.warning("Retrying with summary truncated to 150 chars...")
                prompt_content = rebuild_prompt_with_summary_limit(candidates, 150)
                payload["messages"][1]["content"] = prompt_content
                continue
            if attempt == 2:
                logging.warning("Retrying with max 10 candidates...")
                prompt_content = rebuild_prompt_with_summary_limit(candidates[:10], 100)
                payload["messages"][1]["content"] = prompt_content
                continue
            logging.error("Groq 400 persists after 2 payload reductions. Skipping run.")
            return None

        if response.status_code == 413:
            if attempt == 1:
                logging.warning("Groq 413: payload too large. Retrying with 15 articles / 200-char summaries.")
                prompt_content = rebuild_prompt_with_summary_limit(candidates[:15], 200)
                payload["messages"][1]["content"] = prompt_content
                continue
            if attempt == 2:
                logging.warning("Groq 413 again. Retrying with 8 articles / 100-char summaries.")
                prompt_content = rebuild_prompt_with_summary_limit(candidates[:8], 100)
                payload["messages"][1]["content"] = prompt_content
                continue
            logging.error("Groq 413 persists after 2 reductions. Skipping run.")
            return None

        if response.status_code == 401:
            logging.error("Groq API key is invalid or missing (401 Unauthorized).")
            logging.error("Check GROQ_API_KEY secret in GitHub -> Settings -> Secrets.")
            return None

        if response.status_code == 403:
            logging.error(
                "Groq API access forbidden (403). Model may not be allowed for this org/project. "
                "Check Groq console -> model permissions."
            )
            return None

        try:
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as exc:
            logging.error("Groq unexpected error on attempt %s: %s", attempt, exc)
            return None

    return None


def normalize_groq_result(result: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(result, dict) or not isinstance(result.get("articles"), list):
        return None
    recommendation = str(result.get("recommendation", "SKIP")).upper()
    if recommendation not in {"POST_NOW", "SAVE_PENDING", "SKIP"}:
        recommendation = "SKIP"

    normalized_articles = []
    for item in result.get("articles", []):
        if not isinstance(item, dict):
            continue
        try:
            normalized_item = {
                "index": int(item.get("index", -1)),
                "title": clean_whitespace(str(item.get("title", ""))),
                "summary": clean_whitespace(str(item.get("summary", ""))),
                "novelty_score": float(item.get("novelty_score", 0.0)),
                "impact_score": float(item.get("impact_score", 0.0)),
                "freshness_score": float(item.get("freshness_score", 0.0)),
                "source_score": float(item.get("source_score", 0.0)),
                "total_score": float(item.get("total_score", 0.0)),
                "red_flag": bool(item.get("red_flag", False)),
                "red_flag_reason": item.get("red_flag_reason"),
                "reason": clean_whitespace(str(item.get("reason", ""))),
            }
            matched_pattern = find_local_red_flag_pattern(normalized_item)
            if matched_pattern and not normalized_item["red_flag"]:
                normalized_item["red_flag"] = True
                normalized_item["total_score"] = 0.0
                normalized_item["red_flag_reason"] = "Local enforcement override"
                logging.warning('Groq missed red flag on [%s] - overriding to 0.00', normalized_item["title"])
            elif normalized_item["red_flag"]:
                normalized_item["total_score"] = 0.0
            normalized_articles.append(normalized_item)
        except (TypeError, ValueError):
            continue

    try:
        best_index = int(result.get("best_index", -1))
    except (TypeError, ValueError):
        best_index = -1

    try:
        best_score = float(result.get("best_score", 0.0))
    except (TypeError, ValueError):
        best_score = 0.0

    valid_articles = [item for item in normalized_articles if item.get("index", -1) >= 0]
    if best_index < 0 or not any(item["index"] == best_index for item in valid_articles):
        if valid_articles:
            logging.warning("Invalid best_index from Groq - using local max")
            local_max = max(valid_articles, key=lambda item: item["total_score"])
            best_index = int(local_max["index"])
        else:
            best_index = -1

    enforced_best_index = best_index
    enforced_best_score = 0.0
    best_article = next((item for item in normalized_articles if item["index"] == best_index), None)
    if not best_article or best_article["red_flag"]:
        non_red_articles = [item for item in normalized_articles if not item["red_flag"]]
        if non_red_articles:
            best_article = max(non_red_articles, key=lambda item: item["total_score"])
            enforced_best_index = int(best_article["index"])
        else:
            enforced_best_index = -1
            enforced_best_score = 0.0
            recommendation = "SKIP"

    if best_article:
        article_score = float(best_article["total_score"])
        if abs(article_score - best_score) > 0.5:
            logging.warning(
                "Score mismatch: Groq best_score=%.2f, article[%s].total_score=%.2f. Using article score.",
                best_score,
                enforced_best_index,
                article_score,
            )
        enforced_best_score = article_score

    if enforced_best_score >= 8.5:
        recommendation = "POST_NOW"
    elif enforced_best_score >= 6.0:
        recommendation = "SAVE_PENDING"
    else:
        recommendation = "SKIP"

    return {
        "articles": normalized_articles,
        "best_index": enforced_best_index,
        "best_score": enforced_best_score,
        "authoritative_score": enforced_best_score,
        "recommendation": recommendation,
        "telegram_message": clean_multiline_text(result.get("telegram_message", "")),
    }


def score_map_from_result(result: dict[str, Any]) -> dict[int, dict[str, Any]]:
    return {item["index"]: item for item in result.get("articles", []) if item.get("index", -1) >= 0}


def build_candidate_payload(article: Article, score: dict[str, Any], telegram_message: str, saved_at: datetime) -> dict[str, Any]:
    authoritative_score = round(float(score.get("authoritative_score", score.get("total_score", 0.0))), 2)
    return {
        "index": article.index,
        "title": article.title,
        "summary": article.summary,
        "url": article.url,
        "canonical_url": article.canonical_url,
        "url_hash": article.url_hash,
        "cleaned_title": article.cleaned_title,
        "source": article.source,
        "tier": article.tier,
        "published_at": article.published_at,
        "score": {
            "novelty_score": round(float(score.get("novelty_score", 0.0)), 2),
            "impact_score": round(float(score.get("impact_score", 0.0)), 2),
            "freshness_score": round(float(score.get("freshness_score", 0.0)), 2),
            "source_score": round(float(score.get("source_score", 0.0)), 2),
            "total_score": authoritative_score,
            "red_flag": bool(score.get("red_flag", False)),
            "red_flag_reason": score.get("red_flag_reason"),
            "reason": clean_whitespace(str(score.get("reason", ""))),
        },
        "authoritative_score": authoritative_score,
        "telegram_message": telegram_message,
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


def post_to_telegram(telegram_message: str, bot_token: str, channel_id: str) -> bool:
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response_payload = {
        "chat_id": channel_id,
        "text": telegram_message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    try:
        response = requests.post(api_url, json=response_payload, timeout=30)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("Telegram post failed: %s", exc)
        return False
    return True


def mark_as_posted(posted: dict[str, Any], payload: dict[str, Any], posted_at: datetime) -> None:
    timestamp = isoformat_utc(posted_at)
    hash_record = {"hash": payload["url_hash"], "posted_at": timestamp}
    title_record = {
        "cleaned_title": payload["cleaned_title"],
        "posted_at": timestamp,
        "source": payload["source"],
        "score": round(float(payload["score"]["total_score"]), 2),
    }
    posted.setdefault("hash_records", []).append(hash_record)
    posted.setdefault("recent_titles", []).append(title_record)
    cleanup_posted_history(posted, posted_at)


def clear_pending_if_matches(state: dict[str, Any], payload: dict[str, Any]) -> None:
    pending = state.get("pending_best")
    if not isinstance(pending, dict):
        return
    same_hash = pending.get("url_hash") == payload.get("url_hash")
    same_title = pending.get("cleaned_title") == payload.get("cleaned_title")
    if same_hash or same_title:
        state["pending_best"] = None


def load_posting_intent() -> dict[str, Any] | None:
    if not POSTING_INTENT_PATH.exists():
        return None
    return load_json(POSTING_INTENT_PATH, dict)


def write_posting_intent(payload: dict[str, Any], now: datetime) -> None:
    save_json(
        POSTING_INTENT_PATH,
        {
            "url_hash": payload["url_hash"],
            "title": payload["title"],
            "score": round(float(payload.get("authoritative_score", payload["score"]["total_score"])), 2),
            "intent_time": isoformat_utc(now),
            "status": "pending",
            "cleaned_title": payload.get("cleaned_title", ""),
            "source": payload.get("source", ""),
        },
    )


def complete_posting_intent() -> None:
    intent = load_posting_intent() or {}
    intent["status"] = "completed"
    save_json(POSTING_INTENT_PATH, intent)


def delete_posting_intent() -> None:
    if POSTING_INTENT_PATH.exists():
        POSTING_INTENT_PATH.unlink()


def recover_incomplete_posting_intent(posted: dict[str, Any], now: datetime) -> None:
    intent = load_posting_intent()
    if not isinstance(intent, dict) or intent.get("status") != "pending":
        return

    url_hash = str(intent.get("url_hash", ""))
    if not url_hash:
        delete_posting_intent()
        return

    if url_hash in set(posted.get("hashes", [])):
        delete_posting_intent()
        return

    logging.warning("Found incomplete posting intent - skipping article")
    hash_record = {
        "hash": url_hash,
        "posted_at": isoformat_utc(now),
        "status": "crash-recovered",
    }
    posted.setdefault("hash_records", []).append(hash_record)
    cleaned_title = clean_whitespace(str(intent.get("cleaned_title", "")))
    if cleaned_title:
        posted.setdefault("recent_titles", []).append(
            {
                "cleaned_title": cleaned_title,
                "posted_at": isoformat_utc(now),
                "source": clean_whitespace(str(intent.get("source", "crash-recovered"))),
                "score": round(float(intent.get("score", 0.0)), 2),
            }
        )
    cleanup_posted_history(posted, now)
    save_json(POSTED_PATH, posted)
    delete_posting_intent()


def post_payload_atomically(
    payload: dict[str, Any],
    state: dict[str, Any],
    posted: dict[str, Any],
    now: datetime,
    bot_token: str,
    channel_id: str,
) -> bool:
    write_posting_intent(payload, now)
    if not payload.get("telegram_message") or not post_to_telegram(payload["telegram_message"], bot_token, channel_id):
        delete_posting_intent()
        logging.error("Telegram post failed - intent cancelled, will retry next run")
        return False

    complete_posting_intent()
    mark_as_posted(posted, payload, now)
    state["posts_today"] = int(state.get("posts_today", 0)) + 1
    state["last_post_time"] = isoformat_utc(now)
    clear_pending_if_matches(state, payload)
    persist_state_files(state, posted)
    delete_posting_intent()
    logging.info("Post completed and state persisted successfully")
    return True


def persist_state_files(state: dict[str, Any], posted: dict[str, Any]) -> None:
    save_json(STATE_PATH, state)
    save_json(POSTED_PATH, posted)


def log_final_decision(score: float, recommendation: str, best_index: int) -> None:
    logging.info(
        "Final decision: score=%.2f, recommendation=%s, source=article[%s]",
        score,
        recommendation,
        best_index,
    )


def main() -> int:
    configure_logging()
    secrets = require_env()
    now = utc_now()
    run_started_at = isoformat_utc(now)

    posted = sanitize_posted(load_json(POSTED_PATH, default_posted))
    cleanup_posted_history(posted, now)
    state = load_json(STATE_PATH, lambda: default_state(now))
    state, _ = reset_state_if_needed(state, now)
    recover_incomplete_posting_intent(posted, now)

    if int(state.get("posts_today", 0)) >= MAX_POSTS_PER_DAY:
        logging.info("Daily post cap reached. Exiting.")
        log_final_decision(0.0, "SKIP", -1)
        persist_state_files(state, posted)
        return 0

    preexisting_pending = state.get("pending_best") if isinstance(state.get("pending_best"), dict) else None
    fetched_articles = fetch_all_feeds(now)
    candidates = dedupe_candidates(fetched_articles, posted, now)
    logging.info("Found %s deduplicated fresh candidate(s).", len(candidates))

    pending_updated = False
    if candidates:
        groq_result = call_groq(candidates, now, secrets["GROQ_API_KEY"])
        normalized = normalize_groq_result(groq_result) if groq_result else None
        if normalized:
            score_map = score_map_from_result(normalized)
            best_index = normalized["best_index"]
            best_article = next((article for article in candidates if article.index == best_index), None)
            best_score = score_map.get(best_index)
            authoritative_score = float(normalized.get("authoritative_score", 0.0))

            if best_article and best_score and not best_score["red_flag"]:
                best_score = dict(best_score)
                best_score["authoritative_score"] = authoritative_score
                payload = build_candidate_payload(best_article, best_score, normalized["telegram_message"], now)
                recommendation = normalized["recommendation"]
                log_final_decision(authoritative_score, recommendation, best_index)

                if recommendation == "POST_NOW" and can_post_now(state, authoritative_score, now):
                    if post_payload_atomically(payload, state, posted, now, secrets["TELEGRAM_BOT_TOKEN"], secrets["TELEGRAM_CHANNEL_ID"]):
                        return 0
                    return 0

                if recommendation in {"POST_NOW", "SAVE_PENDING"} and authoritative_score >= 6.0:
                    if pending_is_better(payload, state.get("pending_best")):
                        state["pending_best"] = payload
                        pending_updated = True
                        logging.info("Saved %s as pending_best with score %.2f.", payload["title"], authoritative_score)
            else:
                log_final_decision(authoritative_score, normalized["recommendation"], best_index)
        else:
            log_final_decision(0.0, "SKIP", -1)

    pending_to_post = None
    if isinstance(preexisting_pending, dict):
        pending_score = float(preexisting_pending.get("authoritative_score", preexisting_pending.get("score", {}).get("total_score", 0.0)))
        if can_post_now(state, pending_score, now):
            saved_at = parse_iso_datetime(preexisting_pending.get("saved_at"))
            is_from_prior_run = saved_at is not None and isoformat_utc(saved_at) < run_started_at
            if is_from_prior_run:
                if is_peak_hours(now):
                    pending_to_post = preexisting_pending
                elif is_2130_or_later(now) and int(state.get("posts_today", 0)) == 0 and pending_score >= 6.0:
                    pending_to_post = preexisting_pending

    if pending_to_post and pending_to_post.get("telegram_message"):
        if post_payload_atomically(pending_to_post, state, posted, now, secrets["TELEGRAM_BOT_TOKEN"], secrets["TELEGRAM_CHANNEL_ID"]):
            return 0

    if not candidates:
        logging.info("No new articles qualified for scoring in this run.")
    elif not pending_updated:
        logging.info("No candidate qualified for posting or pending retention.")

    if not candidates:
        log_final_decision(0.0, "SKIP", -1)

    persist_state_files(state, posted)
    return 0
