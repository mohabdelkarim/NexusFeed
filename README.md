# NexusFeed

> **Autonomous AI News Curator** — A production-grade curation engine for software engineers and AI researchers.

[![GitHub Stars](https://img.shields.io/github/stars/mohabdelkarim/NexusFeed?style=social)](https://github.com/mohabdelkarim/NexusFeed/stargazers)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Powered by Groq](https://img.shields.io/badge/powered%20by-Groq-FF6B35)](https://groq.com)
[![GitHub Actions](https://img.shields.io/badge/runs%20on-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white)](https://github.com/mohabdelkarim/NexusFeed/actions)

**NexusFeed** is a production-grade, fully autonomous AI news curator that discovers, scores, deduplicates, and archives the highest-quality AI and software engineering news without human intervention.

---

## ✨ Why NexusFeed?

| Problem | NexusFeed Solution |
|---------|--------------------|
| Endless low-quality listicles | Strict 4-criteria AI scoring plus red-flag detection |
| Duplicate stories everywhere | Multi-layer deduplication with URL hash and title similarity |
| Inconsistent curation quality | One-shot Groq scoring with deterministic decision rules |
| Manual curation is exhausting | Fully autonomous flow with smart pending queue |
| Server costs | Runs entirely on GitHub Actions and persists state in the repo |

---

<!-- POST_NOW_START -->
## 🔥 Latest Curated News

> **Live examples** of high-quality articles automatically discovered, scored, and marked as `POST_NOW` by NexusFeed

| Score | Headline | Source | Published | Tier |
|-------|----------|--------|-----------|------|
| **8.0** | [Why does Apple keep banning Telegram, but never X?](https://www.theverge.com/tech/976405/apple-telegram-ban-x-app-store-violations) | The Verge | 2026-08-07T11:00:00Z | **A** |
| **8.5** | [Scientists Used AI to Create 16 New Viruses](https://www.wired.com/story/scientists-used-ai-to-create-16-new-viruses/) | Wired AI | 2026-08-07T14:13:57Z | **A** |
| **8.5** | [JetBrains Open-Sources KotlinLLM: Smart Macros That Generate Kotlin Source Code at Runtime and Hot-Reload It Through JDI](https://www.marktechpost.com/2026/07/31/jetbrains-research-open-sources-kotlinllm-intellij-plugin-kotlin-runtime-llm/) | MarkTechPost | 2026-07-31T10:32:53Z | **A** |
| **7.5** | [Some Large Language Models Exhibit Consistent Risk Attitudes](https://arxiv.org/abs/2607.16197) | arXiv cs.AI | 2026-07-21T04:00:00Z | **C** |
| **8.0** | [San Francisco orders Apple, Google to remove nudify apps from app stores](https://arstechnica.com/tech-policy/2026/07/apple-google-must-stop-profiting-off-ai-nudify-apps-san-francisco-ag-says/) | Ars Technica | 2026-07-17T16:10:05Z | **A** |
| **8.0** | [New York becomes the first state to enact a data center moratorium](https://www.theverge.com/policy/965110/new-york-ai-data-center-moratorium) | The Verge | 2026-07-14T09:00:00Z | **A** |
| **8.5** | [Meta accused of using biased AI targeting for mass layoffs](https://www.theverge.com/tech/965486/meta-lawsuit-former-employees-ai-layoffs) | The Verge | 2026-07-14T17:18:11Z | **A** |
| **8.5** | [Spotify expands its AI push with a ChatGPT-like music assistant](https://techcrunch.com/2026/07/14/spotify-expands-its-ai-push-with-a-chatgpt-like-music-assistant/) | TechCrunch | 2026-07-14T14:06:47Z | **A** |
| **8.5** | [Linux Foundation Launches Akrites to Protect Critical Open Source Software from AI-Powered Threats](https://www.infoq.com/news/2026/07/akrites-open-source-ai-threats/?utm_campaign=infoq_content&utm_source=infoq&utm_medium=feed&utm_term=global) | InfoQ AI/ML | 2026-07-10T12:00:00Z | **B** |

*All articles above passed strict scoring, deduplication, and red-flag checks. NexusFeed keeps only the very best.*
<!-- POST_NOW_END -->

---

**Want to see it in action?**  
Run it locally in minutes or let GitHub Actions keep the repository updated automatically.

---

## 🧠 How It Thinks

NexusFeed uses a **4-dimensional scoring system** powered by Groq:

```text
Total Score = Novelty (3) + Impact (3) + Freshness (2) + Source Authority (2)
```

**Red flags are strictly enforced**: tutorials, "top 10" lists, recaps, and how-to guides are automatically rejected.

Real-time decisions:

- `POST_NOW` -> `>= 8.5`
- `SAVE_PENDING` -> `6.0 - 8.4`
- `SKIP` -> `< 6.0`

---

## 🚀 Features

- **15 curated RSS feeds** across AI and software engineering
- **Parallel fetching** with `ThreadPoolExecutor(max_workers=15)`
- **One-shot Groq call** for scoring and decisioning
- **Aggressive deduplication** with URL hash and 80% title similarity
- **Smart pending queue** stored in `daily_state.json`
- **Automatic README updates** with the latest `POST_NOW` stories
- **Daily digest generation** saved to `latest_digest.json`
- **Zero server cost** because everything lives in the GitHub repo

---

## 📦 Quick Start

### 1. Clone The Repository

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
. .venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Create .env file
copy .env.example .env
# Edit .env with your key

python main.py
```

---

## 🏗️ Architecture

```text
┌─────────────────────┐
│   GitHub Actions    │
│   (cron scheduler)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐     ┌──────────────────────┐
│   news_bot.py       │────▶│   Groq (Llama 3.3)   │
│                     │     │   (JSON mode)        │
└──────────┬──────────┘     └──────────────────────┘
           │
           ▼
┌─────────────────────┐
│  posted_now.json    │
│  README dashboard   │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  State persisted    │
│  to GitHub repo     │
└─────────────────────┘
```

**Key files:**

- `news_bot.py` — Scoring, deduplication, decision logic, README updates
- `main.py` — Clean entrypoint
- `daily_state.json` — Persistent daily counters and pending queue
- `posted_articles.json` — Deduplication memory
- `posted_now.json` — Latest `POST_NOW` stories
- `daily_digest.py` — Daily digest generator

---

## 🎯 Curated Sources

**Tier S**

- OpenAI
- Anthropic
- Google AI
- Hugging Face
- Microsoft AI

**Tier A**

- TechCrunch
- The Verge
- Ars Technica
- MarkTechPost
- Wired AI

**Tier B and C**

- MIT News
- InfoQ
- AI News
- arXiv cs.AI
- Hacker News

---

## 🔧 Customization

Want to change behavior? Edit these constants in `news_bot.py`:

```python
MAX_POSTS_PER_DAY = 3
MIN_HOURS_BETWEEN_POSTS = 3
MAX_CANDIDATES = 25
TITLE_SIMILARITY_THRESHOLD = 0.80
```

You can also:

- Add or remove feeds in `FEEDS`
- Extend `RED_FLAG_PATTERNS`
- Tune `SCORING_SYSTEM_PROMPT`

---

## 📁 Outputs

Repository outputs:

- `posted_now.json` — latest `POST_NOW` items
- `posted_articles.json` — dedupe history
- `daily_state.json` — daily counters and `pending_best`
- `digest_history.json` — digest dedupe history
- `latest_digest.json` — latest saved daily digest

---

## ⚙️ GitHub Actions

`news-bot.yml`

- Runs the main curator on schedule
- Updates `posted_now.json`
- Refreshes the `README` curated news section
- Commits repo state back automatically

`daily-digest.yml`

- Generates the top 5 digest
- Saves it to `latest_digest.json`
- Commits digest state back automatically

`feed-health.yml`

- Checks feed availability
- Fails if too many sources are unavailable

---

## 📈 Roadmap

- [ ] Semantic deduplication with embeddings
- [ ] Better README news cards or richer dashboard formatting
- [ ] Weekly digest mode
- [ ] Dynamic source tiering
- [ ] Historical analytics for score trends
