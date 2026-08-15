<h1 align="center">NEXUSFEED</h1>

<p align="center">
  <code>SHORTWAVE FOR SOFTWARE + AI</code><br>
  <sub>RSS noise in &nbsp;·&nbsp; scored clearance out &nbsp;·&nbsp; zero servers</sub>
</p>

<p align="center">
  <a href="https://github.com/mohabdelkarim/NexusFeed/actions/workflows/news_bot.yml"><img src="https://github.com/mohabdelkarim/NexusFeed/actions/workflows/news_bot.yml/badge.svg" alt="curator status"></a>
  &nbsp;
  <img src="https://img.shields.io/badge/clearance-8.5%2B-1a1a1a?labelColor=0b0b0b" alt="clearance">
  &nbsp;
  <img src="https://img.shields.io/badge/runtime-GitHub%20Actions-2088FF?logo=githubactions&logoColor=white" alt="actions">
  &nbsp;
  <img src="https://img.shields.io/badge/license-MIT-2ea44f" alt="license">
</p>

<br>

<p align="center"><b>This repository is the product.</b> A curator listens to fifteen feeds, asks Groq for a hard score, kills duplicates, and stamps only the clears onto this page.</p>

```text
   ∿∿∿  tune  →  weigh  →  gate  →  stamp  ∿∿∿
   feeds        Groq       8.5+      README
```

<!-- POST_NOW_START -->
<a id="cleared"></a>
## Cleared

<p align="center"><sub>Scored 8.5+ · refreshed by GitHub Actions</sub></p>

<p>
  <a href="https://blog.google/innovation-and-ai/models-and-research/google-research/amie-video-consultations"><strong>AMIE, our research medical AI system, demonstrates real-time clinical video consultation capabilities in a…</strong></a><br>
  <code>9.0</code> &nbsp;·&nbsp; Google AI &nbsp;·&nbsp; Aug 11
</p>

<p>
  <a href="https://www.wired.com/story/organoids-lab-grown-brains-neural-networks"><strong>AI Is Dead. Organoids Are Alive</strong></a><br>
  <code>8.5</code> &nbsp;·&nbsp; Wired AI &nbsp;·&nbsp; Aug 11
</p>

<p>
  <a href="https://www.theverge.com/ai-artificial-intelligence/976948/openai-astra-model-pause-critical-cyber-capabilities"><strong>OpenAI puts the brakes on a new model because it’s supposedly too powerful</strong></a><br>
  <code>8.5</code> &nbsp;·&nbsp; The Verge &nbsp;·&nbsp; Aug 07
</p>

<p>
  <a href="https://www.wired.com/story/scientists-used-ai-to-create-16-new-viruses"><strong>Scientists Used AI to Create 16 New Viruses</strong></a><br>
  <code>8.5</code> &nbsp;·&nbsp; Wired AI &nbsp;·&nbsp; Aug 07
</p>

<p>
  <a href="https://www.marktechpost.com/2026/07/31/jetbrains-research-open-sources-kotlinllm-intellij-plugin-kotlin-runtime-llm"><strong>JetBrains Open-Sources KotlinLLM: Smart Macros That Generate Kotlin Source Code at Runtime and Hot-Reload It…</strong></a><br>
  <code>8.5</code> &nbsp;·&nbsp; MarkTechPost &nbsp;·&nbsp; Jul 31
</p>

<p>
  <a href="https://www.theverge.com/tech/965486/meta-lawsuit-former-employees-ai-layoffs"><strong>Meta accused of using biased AI targeting for mass layoffs</strong></a><br>
  <code>8.5</code> &nbsp;·&nbsp; The Verge &nbsp;·&nbsp; Jul 14
</p>

<p>
  <a href="https://techcrunch.com/2026/07/14/spotify-expands-its-ai-push-with-a-chatgpt-like-music-assistant"><strong>Spotify expands its AI push with a ChatGPT-like music assistant</strong></a><br>
  <code>8.5</code> &nbsp;·&nbsp; TechCrunch &nbsp;·&nbsp; Jul 14
</p>

<p>
  <a href="https://www.infoq.com/news/2026/07/akrites-open-source-ai-threats"><strong>Linux Foundation Launches Akrites to Protect Critical Open Source Software from AI-Powered Threats</strong></a><br>
  <code>8.5</code> &nbsp;·&nbsp; InfoQ AI/ML &nbsp;·&nbsp; Jul 10
</p>

<p align="center"><sub>8 clears · full state in <code>posted_now.json</code></sub></p>

<!-- POST_NOW_END -->

## Signal path

```mermaid
flowchart LR
  A[15 RSS feeds] --> B[Parallel fetch]
  B --> C[Groq JSON score]
  C --> D{Clearance 8.5+}
  D -->|yes| E[posted_now + README]
  D -->|hold| F[pending queue]
  D -->|no| G[drop]
```

Novelty · Impact · Freshness · Source authority. Local red flags override the model when a story smells like a listicle. Canonical URL hashing keeps the same piece from returning in a new outfit.

## Bring the desk online

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
cp .env.example .env
```

Drop your `GROQ_API_KEY` into `.env`, then:

```bash
python main.py
```

Same secret in Actions. The desk opens Tuesday and Friday.

<details>
<summary><code>// operator notes</code></summary>

<br>

**Knobs** in `news_bot.py`: `FEEDS` · `POST_NOW_MIN_SCORE` · `MAX_POSTS_PER_DAY` · `RED_FLAG_PATTERNS`

**Side channels**

```bash
python daily_digest.py
python check_feeds.py
python -m unittest discover -s tests -v
```

**Band list** · OpenAI · Anthropic · Google AI · Hugging Face · Microsoft AI · TechCrunch · The Verge · Ars Technica · MarkTechPost · Wired AI · MIT News · InfoQ · AI News · arXiv cs.AI · Hacker News

**License** · MIT

</details>
