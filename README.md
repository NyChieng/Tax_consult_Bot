# MyCukai - Malaysia Tax Consultant Bot

AI-powered Malaysian tax reference assistant built with RAG (Retrieval-Augmented Generation) and Claude API. Supports English, Bahasa Malaysia, and Mandarin Chinese.

## Features

- **Personal Income Tax**: Rates, reliefs, deductions, PCB, e-Filing guidance
- **Corporate Tax**: SME rates, incentives, pioneer status, capital allowances
- **SST**: Registration thresholds, rates, filing procedures
- **RPGT**: Property gains tax rates, exemptions, holding periods
- **Stamp Duty**: Rates and calculations
- **Withholding Tax**: Rates by country and payment type, DTA provisions
- **Auto-updating**: Daily scraping of LHDN, Gazette, and professional sources
- **Multilingual**: English, Bahasa Malaysia, Chinese (auto-detected)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Claude Sonnet (Anthropic) |
| Embeddings | Voyage AI voyage-3 |
| Vector DB | ChromaDB |
| Re-ranking | Cohere rerank-multilingual-v3 |
| API | FastAPI |
| Bot | Telegram Bot API |
| Database | PostgreSQL |
| Cache | Redis |
| Scraping | httpx + BeautifulSoup + pdfplumber |

## Quick Start

### Prerequisites
- Python 3.11+
- Docker & Docker Compose (optional, for full stack)

### Local Development

```bash
# Clone and setup
git clone https://github.com/yourusername/Tax_consult_Bot.git
cd Tax_consult_Bot

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Run the API server
python -m api.main
```

### Docker Deployment

```bash
docker-compose up -d
```

### Data Pipeline

```bash
# 1. Scrape sources
python -m scraper.lhdn_spider
python -m scraper.gazette_spider
python -m scraper.sst_spider
python -m scraper.big4_spider

# 2. Process documents
python -m processor.pipeline

# 3. Embed into vector store
python -m embedder.vector_store
```

### Run Telegram Bot

```bash
python -m api.telegram_webhook
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Main query endpoint |
| GET | `/health` | Health check |
| GET | `/freshness` | Knowledge base freshness |
| POST | `/admin/trigger-update` | Force re-scrape (admin) |

## Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Claude API key |
| `VOYAGE_API_KEY` | Voyage AI embeddings key |
| `COHERE_API_KEY` | Cohere reranking key |
| `DATABASE_URL` | PostgreSQL connection string |
| `REDIS_URL` | Redis connection string |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token |

## Testing

```bash
pytest tests/ -v
```

## Legal Disclaimer

This bot is an **educational reference tool** — NOT a licensed tax advisory service. It does not file returns, calculate specific liabilities, or represent users before LHDN. Users should always consult a qualified tax agent registered under the Tax Agents Act 1995.

## License

MIT License - see [LICENSE](LICENSE)
