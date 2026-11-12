from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from news_bot import (
    POST_NOW_MIN_SCORE,
    Article,
    build_candidate_payload,
    build_groq_prompt,
    canonicalize_url,
    compute_freshness_score,
    default_posted,
    default_state,
    diversify_candidates,
    enforce_local_article_scores,
    escape_markdown_cell,
    find_local_red_flag_pattern,
    format_display_date,
    is_safe_http_url,
    item_authoritative_score,
    normalize_groq_result,
    reset_state_if_needed,
    seed_posted_from_posted_now,
    shorten_title,
    stable_hash,
    unwrap_groq_payload,
    write_run_result,
)


def _article(
    *,
    index: int = 0,
    title: str = "OpenAI launches new model",
    summary: str = "A real product launch for developers.",
    source: str = "OpenAI",
    tier: str = "S",
    url: str = "https://openai.com/index/example",
    hours_ago: float = 1.0,
    now: datetime | None = None,
) -> Article:
    anchor = now or datetime.now(timezone.utc)
    published = anchor - timedelta(hours=hours_ago)
    canonical = canonicalize_url(url)
    return Article(
        index=index,
        title=title,
        summary=summary,
        url=canonical,
        canonical_url=canonical,
        url_hash=stable_hash(canonical),
        cleaned_title="openai launches model",
        source=source,
        tier=tier,
        published_at=published.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        published_ts=published.timestamp(),
        source_rank={"S": 0, "A": 1, "B": 2, "C": 3}[tier],
    )


class CanonicalUrlTests(unittest.TestCase):
    def test_strips_tracking_and_trailing_slash(self) -> None:
        raw = "https://Example.com/path/?utm_source=feed&utm_campaign=x&id=1"
        self.assertEqual(canonicalize_url(raw), "https://example.com/path?id=1")

    def test_hash_uses_canonical_form(self) -> None:
        a = "https://example.com/story?utm_source=rss"
        b = "https://example.com/story/"
        self.assertEqual(stable_hash(canonicalize_url(a)), stable_hash(canonicalize_url(b)))


class MarkdownEscapeTests(unittest.TestCase):
    def test_unescapes_entities_and_escapes_pipes(self) -> None:
        self.assertEqual(
            escape_markdown_cell("Gemini&#8217;s | model"),
            "Gemini’s \\| model",
        )


class DisplayHelpersTests(unittest.TestCase):
    def test_format_display_date(self) -> None:
        self.assertEqual(format_display_date("2026-08-11T17:00:00Z"), "Aug 11")

    def test_shorten_title(self) -> None:
        long_title = "A" * 140
        shortened = shorten_title(long_title, max_chars=40)
        self.assertLessEqual(len(shortened), 40)
        self.assertTrue(shortened.endswith("…"))


class ScoreGateTests(unittest.TestCase):
    def test_authoritative_score_prefers_top_level(self) -> None:
        item = {"authoritative_score": 8.5, "score": {"total_score": 7.0}}
        self.assertEqual(item_authoritative_score(item), 8.5)

    def test_post_now_threshold(self) -> None:
        self.assertEqual(POST_NOW_MIN_SCORE, 8.5)
        self.assertGreaterEqual(item_authoritative_score({"authoritative_score": 8.5}), POST_NOW_MIN_SCORE)
        self.assertLess(item_authoritative_score({"authoritative_score": 8.0}), POST_NOW_MIN_SCORE)


class RedFlagTests(unittest.TestCase):
    def test_does_not_match_what_is_inside_unrelated_phrase(self) -> None:
        article = _article(title="When Proofs Are Abundant, What Is a Paper For?")
        self.assertIsNone(find_local_red_flag_pattern(article))

    def test_matches_true_listicle(self) -> None:
        article = _article(title="Top 10 AI tools for startups")
        self.assertEqual(find_local_red_flag_pattern(article), "top 10")

    def test_matches_author_qa(self) -> None:
        article = _article(title="Author Q+A: finprim is a Case for One Library")
        self.assertEqual(find_local_red_flag_pattern(article), "author q+a")


class PendingStateTests(unittest.TestCase):
    def test_day_reset_keeps_pending_best(self) -> None:
        now = datetime(2026, 11, 12, 10, 0, tzinfo=timezone.utc)
        pending = {"title": "Keep me", "url_hash": "abc", "authoritative_score": 8.7}
        state = default_state(now - timedelta(days=1))
        state["pending_best"] = pending
        state["posts_today"] = 2
        state["last_post_time"] = "2026-11-11T18:00:00Z"

        reset, changed = reset_state_if_needed(state, now)
        self.assertTrue(changed)
        self.assertEqual(reset["date"], "2026-11-12")
        self.assertEqual(reset["posts_today"], 0)
        self.assertIsNone(reset["last_post_time"])
        self.assertEqual(reset["pending_best"], pending)


class FreshnessAndScoreTests(unittest.TestCase):
    def test_compute_freshness_buckets(self) -> None:
        now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(compute_freshness_score((now - timedelta(minutes=30)).timestamp(), now), 2.0)
        self.assertEqual(compute_freshness_score((now - timedelta(hours=2)).timestamp(), now), 1.5)
        self.assertEqual(compute_freshness_score((now - timedelta(hours=4)).timestamp(), now), 1.0)
        self.assertEqual(compute_freshness_score((now - timedelta(hours=8)).timestamp(), now), 0.5)
        self.assertEqual(compute_freshness_score((now - timedelta(hours=20)).timestamp(), now), 0.0)

    def test_enforce_local_scores_overrides_inflated_freshness(self) -> None:
        now = datetime(2026, 11, 12, 21, 38, tzinfo=timezone.utc)
        article = _article(hours_ago=2.0, now=now, source="The Verge", tier="A")
        score = {
            "index": 0,
            "novelty_score": 2.5,
            "impact_score": 2.5,
            "freshness_score": 2.0,
            "source_score": 1.5,
            "total_score": 8.5,
            "red_flag": False,
            "red_flag_reason": None,
            "reason": "model said so",
        }
        fixed = enforce_local_article_scores(score, article, now)
        self.assertEqual(fixed["freshness_score"], 1.5)
        self.assertEqual(fixed["source_score"], 1.5)
        self.assertEqual(fixed["total_score"], 8.0)
        self.assertLess(fixed["total_score"], POST_NOW_MIN_SCORE)


class GroqNormalizeTests(unittest.TestCase):
    def test_unwraps_response_schema_wrapper(self) -> None:
        wrapped = {
            "response_schema": {
                "articles": [
                    {
                        "index": 0,
                        "title": "IBM Quantum",
                        "novelty_score": 3.0,
                        "impact_score": 2.5,
                        "freshness_score": 1.5,
                        "source_score": 1.5,
                        "total_score": 8.5,
                        "red_flag": False,
                        "red_flag_reason": None,
                        "reason": "solid",
                    }
                ],
                "best_index": 0,
                "best_score": 8.5,
                "recommendation": "POST_NOW",
            }
        }
        unwrapped = unwrap_groq_payload(wrapped)
        self.assertIn("articles", unwrapped)
        normalized = normalize_groq_result(unwrapped)
        assert normalized is not None
        self.assertEqual(normalized["best_index"], 0)
        self.assertEqual(normalized["recommendation"], "POST_NOW")


class DiversifyTests(unittest.TestCase):
    def test_caps_per_source_and_total(self) -> None:
        articles = [
            _article(index=i, source="TechCrunch", tier="A", url=f"https://techcrunch.com/a/{i}", hours_ago=0.1 * (i + 1))
            for i in range(10)
        ] + [
            _article(index=100 + i, source="OpenAI", tier="S", url=f"https://openai.com/a/{i}", hours_ago=0.2 * (i + 1))
            for i in range(5)
        ]
        chosen = diversify_candidates(articles, max_per_source=3, max_total=8)
        counts: dict[str, int] = {}
        for item in chosen:
            counts[item.source] = counts.get(item.source, 0) + 1
        self.assertLessEqual(len(chosen), 8)
        self.assertLessEqual(counts.get("TechCrunch", 0), 3)
        self.assertGreaterEqual(counts.get("OpenAI", 0), 1)


class UrlSafetyTests(unittest.TestCase):
    def test_rejects_non_http_schemes(self) -> None:
        self.assertFalse(is_safe_http_url("javascript:alert(1)"))
        self.assertFalse(is_safe_http_url("data:text/html;base64,xxx"))
        self.assertTrue(is_safe_http_url("https://example.com/x"))


class PostedSeedTests(unittest.TestCase):
    def test_seed_hashes_from_posted_now(self) -> None:
        now = datetime(2026, 11, 12, 12, 0, tzinfo=timezone.utc)
        posted = default_posted()
        items = [
            {
                "url_hash": "abc123",
                "cleaned_title": "openai model",
                "source": "OpenAI",
                "saved_at": (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "authoritative_score": 9.0,
            }
        ]
        seed_posted_from_posted_now(posted, items, now)
        self.assertIn("abc123", posted["hashes"])


class RunResultTests(unittest.TestCase):
    def test_write_run_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run_result.json"
            write_run_result(path, posted=True, title="Hello", url="https://example.com", reason="POST_NOW")
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertTrue(data["posted"])
            self.assertEqual(data["title"], "Hello")


class PromptShapeTests(unittest.TestCase):
    def test_prompt_does_not_nest_response_schema_key(self) -> None:
        now = datetime.now(timezone.utc)
        prompt = build_groq_prompt([_article()], now)
        payload = json.loads(prompt)
        self.assertNotIn("response_schema", payload)
        self.assertIn("candidates", payload)
        self.assertIn("expected_response_keys", payload)


class CandidatePayloadTests(unittest.TestCase):
    def test_build_candidate_payload_roundtrip_score(self) -> None:
        article = _article()
        now = datetime.now(timezone.utc)
        score = {
            "novelty_score": 2.5,
            "impact_score": 2.5,
            "freshness_score": 1.5,
            "source_score": 2.0,
            "total_score": 8.5,
            "authoritative_score": 8.5,
            "red_flag": False,
            "red_flag_reason": None,
            "reason": "ok",
        }
        payload = build_candidate_payload(article, score, now)
        self.assertEqual(payload["authoritative_score"], 8.5)
        self.assertTrue(is_safe_http_url(payload["url"]))


if __name__ == "__main__":
    unittest.main()
