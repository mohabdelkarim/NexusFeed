from __future__ import annotations

import unittest

from news_bot import (
    POST_NOW_MIN_SCORE,
    canonicalize_url,
    escape_markdown_cell,
    format_display_date,
    item_authoritative_score,
    shorten_title,
    stable_hash,
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


if __name__ == "__main__":
    unittest.main()
