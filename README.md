# NexusFeed

RSS in. Noise out. The strongest AI and software engineering stories land here automatically.

Runs on Groq + GitHub Actions. No server. State lives in this repo.

[![Curator](https://github.com/mohabdelkarim/NexusFeed/actions/workflows/news_bot.yml/badge.svg)](https://github.com/mohabdelkarim/NexusFeed/actions/workflows/news_bot.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

<!-- POST_NOW_START -->
## On the wire

Live picks scored **8.5+**. Refreshed by GitHub Actions.

1. **9.0** · Google AI · Aug 11  
   [AMIE, our research medical AI system, demonstrates real-time clinical video consultation capabilities in a…](https://blog.google/innovation-and-ai/models-and-research/google-research/amie-video-consultations)

2. **8.5** · Wired AI · Aug 11  
   [AI Is Dead. Organoids Are Alive](https://www.wired.com/story/organoids-lab-grown-brains-neural-networks)

3. **8.5** · The Verge · Aug 07  
   [OpenAI puts the brakes on a new model because it’s supposedly too powerful](https://www.theverge.com/ai-artificial-intelligence/976948/openai-astra-model-pause-critical-cyber-capabilities)

4. **8.5** · Wired AI · Aug 07  
   [Scientists Used AI to Create 16 New Viruses](https://www.wired.com/story/scientists-used-ai-to-create-16-new-viruses)

5. **8.5** · MarkTechPost · Jul 31  
   [JetBrains Open-Sources KotlinLLM: Smart Macros That Generate Kotlin Source Code at Runtime and Hot-Reload It…](https://www.marktechpost.com/2026/07/31/jetbrains-research-open-sources-kotlinllm-intellij-plugin-kotlin-runtime-llm)

6. **8.5** · The Verge · Jul 14  
   [Meta accused of using biased AI targeting for mass layoffs](https://www.theverge.com/tech/965486/meta-lawsuit-former-employees-ai-layoffs)

7. **8.5** · TechCrunch · Jul 14  
   [Spotify expands its AI push with a ChatGPT-like music assistant](https://techcrunch.com/2026/07/14/spotify-expands-its-ai-push-with-a-chatgpt-like-music-assistant)

8. **8.5** · InfoQ AI/ML · Jul 10  
   [Linux Foundation Launches Akrites to Protect Critical Open Source Software from AI-Powered Threats](https://www.infoq.com/news/2026/07/akrites-open-source-ai-threats)

_Showing 8 of the latest clears. Full state lives in `posted_now.json`._

<!-- POST_NOW_END -->

## How it works

Fifteen curated feeds → score on novelty, impact, freshness, and source authority → keep only clears at **8.5+** → write them into this README and `posted_now.json`.

```text
Actions cron  →  news_bot.py  →  Groq (JSON)  →  repo state
```

Duplicates die on canonical URL hash and title overlap. Local red flags override the model when a story smells like a listicle.

## Run it

```bash
git clone https://github.com/mohabdelkarim/NexusFeed.git
cd NexusFeed
python -m venv .venv
```

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
. .venv/Scripts/Activate.ps1
```

```bash
pip install -r requirements.txt
cp .env.example .env   # Windows: copy .env.example .env
```

Set `GROQ_API_KEY` in `.env`, then:

```bash
python main.py
```

For Actions, add the same key as a repository secret. The curator runs on Tuesday and Friday.

<details>
<summary>Dig deeper</summary>

**Tune** in `news_bot.py`: `FEEDS`, `POST_NOW_MIN_SCORE`, `MAX_POSTS_PER_DAY`, `RED_FLAG_PATTERNS`.

**Also runs:** `python daily_digest.py` · `python check_feeds.py` · `python -m unittest discover -s tests -v`

**Sources:** OpenAI, Anthropic, Google AI, Hugging Face, Microsoft AI, TechCrunch, The Verge, Ars Technica, MarkTechPost, Wired AI, MIT News, InfoQ, AI News, arXiv cs.AI, Hacker News.

**License:** MIT

</details>
