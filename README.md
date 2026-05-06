<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=700&size=28&duration=3000&pause=1000&color=1A237E&center=true&vCenter=true&multiline=true&repeat=true&width=600&height=100&lines=MyCukai+%F0%9F%87%B2%F0%9F%87%BE;Your+Malaysian+Tax+Buddy" alt="MyCukai" />
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Claude_AI-Bedrock-orange?style=for-the-badge&logo=amazon-aws&logoColor=white" />
  <img src="https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" />
</p>

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=14&duration=4000&pause=2000&color=666666&center=true&vCenter=true&width=500&lines=Ask+me+anything+about+Malaysian+tax...;Income+tax+%7C+Reliefs+%7C+SST+%7C+RPGT+%7C+e-Filing;English+%7C+Bahasa+Malaysia+%7C+%E4%B8%AD%E6%96%87;I+talk+like+a+friend%2C+not+a+textbook+%F0%9F%98%8A" alt="Typing SVG" />
</p>

---

## What is this?

**MyCukai** is an AI-powered tax assistant that talks like your smart Malaysian friend — not a boring government robot. Ask it anything about Malaysian tax and it'll explain simply in English, BM, or Chinese.

```
You:  "can i claim my laptop for tax?"
Bot:  "Yeah! Falls under lifestyle relief — up to RM 2,500 total 
       for gadgets, books, sports stuff, internet. Just keep the receipt ya."
```

<p align="center">
  <a href="https://t.me/Mycukai_TaxBot">
    <img src="https://img.shields.io/badge/Try_It_Now-Telegram-26A5E4?style=for-the-badge&logo=telegram&logoColor=white&scale=2" />
  </a>
</p>

---

## Features

```mermaid
mindmap
  root((MyCukai))
    Tax Knowledge
      Personal Income Tax
      Corporate Tax
      SST
      RPGT & Stamp Duty
      Withholding Tax
    Smart Features
      Self-Learning AI
      Auto-updates from LHDN
      Trilingual EN/BM/ZH
      Security Hardened
    Personality
      Talks like a friend
      Malaysian English
      Short & sweet replies
      No walls of text
```

| What it covers | How it feels |
|:---:|:---:|
| Income tax rates & reliefs | Like texting a smart friend |
| e-Filing & deadlines | Short answers, not essays |
| SST registration & rates | Malaysian English lah |
| RPGT on property sales | Empathetic & encouraging |
| Corporate tax & incentives | Code-switches naturally |
| Withholding tax & DTAs | Never judgmental |

---

## Tech Stack

<p align="center">
  <img src="https://skillicons.dev/icons?i=python,aws,docker,fastapi,postgres,redis&theme=dark" />
</p>

| Layer | Tech | What it does |
|:---:|---|---|
| Brain | Claude AI (AWS Bedrock) | Understands and answers questions |
| Memory | ChromaDB + Voyage AI | Finds relevant tax documents |
| Learning | Self-improving feedback loop | Gets smarter with every chat |
| Interface | Telegram Bot API | Where users chat |
| Security | 7-layer defense system | Blocks hackers & abuse |
| Pipeline | pdfplumber + BeautifulSoup | Scrapes LHDN documents |

---

## Quick Start

```bash
# Clone
git clone https://github.com/NyChieng/Tax_consult_Bot.git
cd Tax_consult_Bot

# Install
pip install -r requirements.txt

# Configure (add your API keys)
cp .env.example .env

# Run the bot
python run.py telegram
```

### All Commands

```bash
python run.py telegram    # Start Telegram bot
python run.py api         # Start REST API server
python run.py agent       # Start autonomous AI agent
python run.py pipeline    # Scrape → Process → Embed
python run.py content     # Generate marketing content
python run.py health      # System health check
python run.py test        # Run accuracy tests
```

---

## Architecture

```mermaid
graph LR
    A[User on Telegram] -->|message| B[Security Layer]
    B -->|validated| C[Intent Classifier]
    C --> D[RAG Retriever]
    D -->|context| E[Claude AI - Bedrock]
    E -->|response| F[Output Guard]
    F -->|safe reply| A
    
    G[Online Learner] -->|new facts| D
    H[Self-Improver] -->|better prompts| E
    I[LHDN Scraper] -->|documents| D
    
    style A fill:#26A5E4
    style E fill:#FF9900
    style B fill:#f44336
    style H fill:#4CAF50
```

---

## Self-Learning System

The bot gets **smarter every day** — no manual training needed.

```mermaid
graph TD
    A[User asks question] --> B[Bot answers]
    B --> C{User reaction?}
    C -->|Thanks/Thumbs up| D[Store as golden example]
    C -->|That's wrong| E[Flag knowledge gap]
    C -->|Rephrases| F[Mark as unclear]
    D --> G[Use for future answers]
    E --> H[Auto-search for correct info]
    H --> I[Fill gap & improve]
    F --> J[Adjust response style]
    
    style D fill:#4CAF50
    style E fill:#f44336
    style G fill:#2196F3
```

---

## Security

7 layers protecting your bot from hackers:

| # | Layer | Blocks |
|---|---|---|
| 1 | Rate Limiter | DDoS, burst attacks |
| 2 | Input Guard | Prompt injection, XSS, SQL injection |
| 3 | Output Guard | API key leaks, PII exposure |
| 4 | Authentication | Unauthorized access |
| 5 | Encryption | Data at rest |
| 6 | Audit Log | Tamper-evident logging |
| 7 | Docker | Non-root, read-only filesystem |

---

## Environment Variables

```env
LLM_PROVIDER=bedrock              # or "anthropic"
AWS_ACCESS_KEY_ID=xxx             # Your AWS key
AWS_SECRET_ACCESS_KEY=xxx         # Your AWS secret
AWS_REGION=us-east-1              # Bedrock region
TELEGRAM_BOT_TOKEN=xxx            # From @BotFather (FREE)
```

---

## Contributing

PRs welcome! This bot helps Malaysians understand tax — the more brains on it, the better.

---

## Disclaimer

> This bot is an **educational reference tool** — not a licensed tax agent. It doesn't file returns, calculate your specific liability, or represent you before LHDN. For personal tax matters, consult a registered tax agent (Tax Agents Act 1995).

---

<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=12&duration=3000&pause=1000&color=999999&center=true&vCenter=true&width=400&lines=Built+with+%E2%9D%A4%EF%B8%8F+in+Malaysia;Making+tax+less+scary+since+2026" />
</p>

<p align="center">
  <a href="https://t.me/Mycukai_TaxBot">Try MyCukai on Telegram</a> · 
  <a href="BUSINESS_STRATEGY.md">Business Strategy</a>
</p>
