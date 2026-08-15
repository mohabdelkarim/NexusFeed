<pre align="center">
∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿
                                             
              N E X U S F E E D              
         shortwave for software + ai         
                                             
     tune → weigh → gate → stamp → wire      
                                             
∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿∿
</pre>

<p align="center">
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

<!-- POST_NOW_START -->
<a id="cleared"></a>
## Cleared

<p align="center"><sub>Live clears · refreshed by GitHub Actions</sub></p>

> [AMIE, our research medical AI system, demonstrates real-time clinical video consultation capabilities in a…](https://blog.google/innovation-and-ai/models-and-research/google-research/amie-video-consultations)  
> Google AI · Aug 11

> [AI Is Dead. Organoids Are Alive](https://www.wired.com/story/organoids-lab-grown-brains-neural-networks)  
> Wired AI · Aug 11

> [OpenAI puts the brakes on a new model because it’s supposedly too powerful](https://www.theverge.com/ai-artificial-intelligence/976948/openai-astra-model-pause-critical-cyber-capabilities)  
> The Verge · Aug 07

> [Scientists Used AI to Create 16 New Viruses](https://www.wired.com/story/scientists-used-ai-to-create-16-new-viruses)  
> Wired AI · Aug 07

> [JetBrains Open-Sources KotlinLLM: Smart Macros That Generate Kotlin Source Code at Runtime and Hot-Reload It…](https://www.marktechpost.com/2026/07/31/jetbrains-research-open-sources-kotlinllm-intellij-plugin-kotlin-runtime-llm)  
> MarkTechPost · Jul 31

> [Meta accused of using biased AI targeting for mass layoffs](https://www.theverge.com/tech/965486/meta-lawsuit-former-employees-ai-layoffs)  
> The Verge · Jul 14

> [Spotify expands its AI push with a ChatGPT-like music assistant](https://techcrunch.com/2026/07/14/spotify-expands-its-ai-push-with-a-chatgpt-like-music-assistant)  
> TechCrunch · Jul 14

> [Linux Foundation Launches Akrites to Protect Critical Open Source Software from AI-Powered Threats](https://www.infoq.com/news/2026/07/akrites-open-source-ai-threats)  
> InfoQ AI/ML · Jul 10

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
