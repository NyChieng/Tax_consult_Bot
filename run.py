"""
MyCukai Tax Bot - Main Entry Point

Usage:
    python run.py api         - Start the FastAPI server
    python run.py telegram    - Start the Telegram bot
    python run.py scrape      - Run all scrapers once
    python run.py process     - Process all raw data
    python run.py embed       - Embed processed chunks
    python run.py scheduler   - Start the scrape scheduler
    python run.py pipeline    - Full pipeline: scrape → process → embed
    python run.py test        - Run accuracy tests
    python run.py agent       - Start autonomous AI agent (runs everything)
    python run.py content     - Generate marketing content
    python run.py health      - Run system health check
    python run.py insights    - Generate analytics insights
"""
import sys


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "api":
        import uvicorn
        from config import settings
        uvicorn.run("api.main:app", host=settings.api_host, port=settings.api_port, reload=True)

    elif command == "telegram":
        from api.telegram_webhook import run_telegram_bot
        run_telegram_bot()

    elif command == "scrape":
        from scraper.lhdn_spider import run as run_lhdn
        from scraper.gazette_spider import run as run_gazette
        from scraper.sst_spider import run as run_sst
        from scraper.big4_spider import run as run_big4
        from scraper.news_monitor import run as run_news

        print("Starting LHDN scrape...")
        run_lhdn()
        print("Starting Gazette scrape...")
        run_gazette()
        print("Starting SST scrape...")
        run_sst()
        print("Starting Big4 scrape...")
        run_big4()
        print("Starting News monitor...")
        run_news()
        print("All scrapers complete.")

    elif command == "process":
        from processor.pipeline import process_all
        total = process_all()
        print(f"Processing complete. Total chunks: {total}")

    elif command == "embed":
        from embedder.vector_store import embed_all_chunks
        total = embed_all_chunks()
        print(f"Embedding complete. Total embedded: {total}")

    elif command == "scheduler":
        from scraper.scheduler import main as scheduler_main
        scheduler_main()

    elif command == "pipeline":
        from scraper.lhdn_spider import run as run_lhdn
        from scraper.sst_spider import run as run_sst
        from scraper.big4_spider import run as run_big4
        from processor.pipeline import process_all
        from embedder.vector_store import embed_all_chunks

        print("=== STEP 1: Scraping ===")
        run_lhdn()
        run_sst()
        run_big4()

        print("\n=== STEP 2: Processing ===")
        total_chunks = process_all()
        print(f"Chunks created: {total_chunks}")

        print("\n=== STEP 3: Embedding ===")
        total_embedded = embed_all_chunks()
        print(f"Chunks embedded: {total_embedded}")

        print("\n=== PIPELINE COMPLETE ===")

    elif command == "test":
        import asyncio
        from monitoring.accuracy_tracker import run_accuracy_test

        report = asyncio.run(run_accuracy_test())
        print(f"\nAccuracy: {report.get('accuracy', 'N/A')}%")
        print(f"Passed: {report.get('passed', 'N/A')}")

    elif command == "agent":
        import asyncio
        from agent.orchestrator import main as agent_main
        print("Starting MyCukai Autonomous Agent...")
        print("Press Ctrl+C to stop.\n")
        asyncio.run(agent_main())

    elif command == "content":
        import asyncio
        from agent.content_generator import generate_daily_content
        print("Generating marketing content...")
        content = asyncio.run(generate_daily_content())
        import json
        print(json.dumps(content, indent=2, ensure_ascii=False)[:2000])
        print("\nFull content saved to data/marketing_content/")

    elif command == "health":
        import asyncio
        from agent.self_healing import SelfHealingAgent
        agent = SelfHealingAgent()
        report = asyncio.run(agent.run_health_check())
        import json
        print(json.dumps(report, indent=2))

    elif command == "insights":
        from agent.analytics_agent import AnalyticsAgent
        agent = AnalyticsAgent()
        insights = agent.generate_insights()
        import json
        print(json.dumps(insights, indent=2))

    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
