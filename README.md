# NexusFeed

> Autonomous AI and software engineering news curator powered by Groq and GitHub Actions.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Powered by Groq](https://img.shields.io/badge/powered%20by-Groq-FF6B35)](https://groq.com)
[![Curator](https://github.com/mohabdelkarim/NexusFeed/actions/workflows/news_bot.yml/badge.svg)](https://github.com/mohabdelkarim/NexusFeed/actions/workflows/news_bot.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**NexusFeed** fetches RSS feeds, scores stories with Groq, deduplicates them, and writes the strongest AI / software engineering picks into this repository. No separate server is required.

---

## Why NexusFeed?

| Problem | NexusFeed Solution |
|---------|--------------------|
| Endless low quality listicles | 4 criteria scoring plus local red flag checks |
| Duplicate stories everywhere | Canonical URL hashing and title similarity |
| Manual curation is exhausting | Scheduled GitHub Actions with a pending queue |
| Hosting cost | State and dashboard live in the repo |

---

<!-- POST_NOW_START -->
## Latest Curated News

> Live examples scored `POST_NOW` (>= 8.5) by NexusFeed

| Score | Headline | Source | Published | Tier |
|-------|----------|--------|-----------|------|
| **9.0** | [AMIE, our research medical AI system, demonstrates real-time clinical video consultation capabilities in a first-of-its-kind study.](https://blog.google/innovation-and-ai/models-and-research/google-research/amie-video-consultations) | Google AI | 2026-08-11T17:00:00Z | **S** |
| **8.5** | [AI Is Dead. Organoids Are Alive](https://www.wired.com/story/organoids-lab-grown-brains-neural-networks) | Wired AI | 2026-08-11T10:00:00Z | **A** |
| **8.5** | [OpenAI puts the brakes on a new model because it’s supposedly too powerful](https://www.theverge.com/ai-artificial-intelligence/976948/openai-astra-model-pause-critical-cyber-capabilities) | The Verge | 2026-08-07T18:40:34Z | **A** |
| **8.5** | [Scientists Used AI to Create 16 New Viruses](https://www.wired.com/story/scientists-used-ai-to-create-16-new-viruses) | Wired AI | 2026-08-07T14:13:57Z | **A** |
| **8.5** | [JetBrains Open-Sources KotlinLLM: Smart Macros That Generate Kotlin Source Code at Runtime and Hot-Reload It Through JDI](https://www.marktechpost.com/2026/07/31/jetbrains-research-open-sources-kotlinllm-intellij-plugin-kotlin-runtime-llm) | MarkTechPost | 2026-07-31T10:32:53Z | **A** |
| **8.5** | [Meta accused of using biased AI targeting for mass layoffs](https://www.theverge.com/tech/965486/meta-lawsuit-former-employees-ai-layoffs) | The Verge | 2026-07-14T17:18:11Z | **A** |
| **8.5** | [Spotify expands its AI push with a ChatGPT-like music assistant](https://techcrunch.com/2026/07/14/spotify-expands-its-ai-push-with-a-chatgpt-like-music-assistant) | TechCrunch | 2026-07-14T14:06:47Z | **A** |
| **8.5** | [Linux Foundation Launches Akrites to Protect Critical Open Source Software from AI-Powered Threats](https://www.infoq.com/news/2026/07/akrites-open-source-ai-threats) | InfoQ AI/ML | 2026-07-10T12:00:00Z | **B** |

*Articles above passed scoring, deduplication, and red-flag checks.*
<!-- POST_NOW_END -->

---

Run it locally or let GitHub Actions update the repository on schedule (Tuesday and Friday).

---

## How It Scores

NexusFeed uses a 4 dimensional scoring system powered by Groq (`temperature: 0`):

```text
Total Score = Novelty (3) + Impact (3) + Freshness (2) + Source Authority (2)
```

Red flags (tutorials, top 10 lists, recaps, how to guides) are enforced locally and override the model when needed.

Decision rules:

- `POST_NOW` -> score `>= 8.5` (only these are written to `posted_now.json` and the README table)
- `SAVE_PENDING` -> `6.0` to `8.4` (held for a later peak window if they reach `>= 8.5`)
- `SKIP` -> `< 6.0`

---

## Features

- 15 curated RSS feeds across AI and software engineering
- Parallel feed fetching
- One Groq call per run for scoring and recommendation
- Deduplication via canonical URL hash and title similarity
- Pending queue in `daily_state.json`
- Automatic README updates for `POST_NOW` stories
- Daily digest output in `latest_digest.json`
- Runs on GitHub Actions with repo persisted state

---

## Quick Start

### 1. Clone

```bash
git clone https://github.com/mohabdelkarim/NexusFeed.git
cd NexusFeed
```

### 2. Required Secret

Add this GitHub Actions secret:

| Secret | Description |
|--------|-------------|
| `GROQ_API_KEY` | Your Groq API key |

### 3. Local Development

```bash
python -m venv .venv
```

Activate the virtualenv:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
. .venv/Scripts/Activate.ps1
```

```bash
pip install -r requirements.txt
cp .env.example .env   # Windows: copy .env.example .env
# Edit .env and set GROQ_API_KEY

python main.py
```

Optional:

```bash
python daily_digest.py
python check_feeds.py
python -m unittest discover -s tests -v
```

---

## Architecture

```text
GitHub Actions (cron)
        |
        v
   news_bot.py  ---->  Groq (Llama 3.3, JSON mode)
        |
        v
 posted_now.json + README table + daily_state.json
```

Key files:

- `news_bot.py` scoring, dedupe, decisions, README updates
- `main.py` curator entrypoint
- `daily_digest.py` daily digest generator
- `check_feeds.py` feed health checks
- `daily_state.json` counters and pending queue
- `posted_articles.json` dedupe memory
- `posted_now.json` latest `POST_NOW` stories

---

## Curated Sources

**Tier S:** OpenAI, Anthropic, Google AI, Hugging Face, Microsoft AI

**Tier A:** TechCrunch, The Verge, Ars Technica, MarkTechPost, Wired AI

**Tier B / C:** MIT News, InfoQ, AI News, arXiv cs.AI, Hacker News

---

## Customization

Tune these constants in `news_bot.py`:

```python
MAX_POSTS_PER_DAY = 3
MIN_HOURS_BETWEEN_POSTS = 3
MAX_CANDIDATES = 25
TITLE_SIMILARITY_THRESHOLD = 0.80
POST_NOW_MIN_SCORE = 8.5
```

You can also edit `FEEDS`, `RED_FLAG_PATTERNS`, and `SCORING_SYSTEM_PROMPT`.

---

## Outputs

- `posted_now.json` latest `POST_NOW` items (`>= 8.5`)
- `posted_articles.json` dedupe history
- `daily_state.json` daily counters and `pending_best`
- `digest_history.json` digest dedupe history
- `latest_digest.json` latest daily digest

---

## GitHub Actions

`news_bot.yml`

- Runs the curator on Tuesday and Friday schedules
- Updates `posted_now.json` and the README section
- Commits state back to the repo

`daily_digest.yml`

- Builds the top 5 digest
- Saves `latest_digest.json`

`feed_health.yml`

- Checks feed availability weekly
- Fails if too many sources are down

---

## License

MIT. See [LICENSE](LICENSE).

---

## Roadmap

- [ ] Semantic deduplication with embeddings
- [ ] Richer README news cards
- [ ] Weekly digest mode
- [ ] Dynamic source tiering
- [ ] Historical score analytics
