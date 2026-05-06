"""
MyCukai Autonomous Agent Orchestrator

This agent runs continuously and handles:
1. Data collection (scraping on schedule)
2. Data processing (PDF extraction, chunking, embedding)
3. Knowledge freshness monitoring
4. Accuracy self-testing
5. Content generation for marketing
6. User query analytics
7. Self-healing (detects and fixes issues)

Usage:
    python -m agent.orchestrator
"""
import asyncio
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import structlog

from config import settings

logger = structlog.get_logger()

STATE_FILE = Path("data/agent_state.json")


class AgentState:
    def __init__(self):
        self.last_scrape: Optional[str] = None
        self.last_process: Optional[str] = None
        self.last_embed: Optional[str] = None
        self.last_accuracy_test: Optional[str] = None
        self.last_content_gen: Optional[str] = None
        self.total_documents: int = 0
        self.total_chunks: int = 0
        self.accuracy_score: float = 0.0
        self.errors: list[dict] = []
        self.tasks_completed: int = 0
        self._load()

    def _load(self):
        if STATE_FILE.exists():
            data = json.loads(STATE_FILE.read_text())
            for key, value in data.items():
                if hasattr(self, key):
                    setattr(self, key, value)

    def save(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_scrape": self.last_scrape,
            "last_process": self.last_process,
            "last_embed": self.last_embed,
            "last_accuracy_test": self.last_accuracy_test,
            "last_content_gen": self.last_content_gen,
            "total_documents": self.total_documents,
            "total_chunks": self.total_chunks,
            "accuracy_score": self.accuracy_score,
            "errors": self.errors[-50:],
            "tasks_completed": self.tasks_completed,
        }
        STATE_FILE.write_text(json.dumps(data, indent=2))

    def record_error(self, task: str, error: str):
        self.errors.append({
            "task": task,
            "error": error,
            "time": datetime.now(timezone.utc).isoformat(),
        })
        self.save()


class MyCukaiAgent:
    """
    Autonomous agent that manages the entire MyCukai bot lifecycle.
    Runs continuously, making decisions about what to do next.
    """

    def __init__(self):
        self.state = AgentState()
        self.running = True

    async def run(self):
        logger.info("agent_starting", state=self.state.__dict__)
        print("=" * 60)
        print("  MyCukai Autonomous Agent Started")
        print("=" * 60)
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Mode: {'Production' if settings.environment == 'production' else 'Development'}")
        print("=" * 60)

        while self.running:
            try:
                task = self._decide_next_task()
                if task:
                    await self._execute_task(task)
                else:
                    logger.info("agent_idle", next_check="5 minutes")
                    await asyncio.sleep(300)
            except KeyboardInterrupt:
                self.running = False
                logger.info("agent_shutdown_requested")
            except Exception as e:
                logger.error("agent_loop_error", error=str(e))
                self.state.record_error("main_loop", str(e))
                await asyncio.sleep(60)

        logger.info("agent_stopped")

    def _decide_next_task(self) -> Optional[str]:
        """AI-like decision engine: picks the most important task to do next."""
        now = datetime.now(timezone.utc)

        # Priority 1: Never scraped before — do initial setup
        if not self.state.last_scrape:
            return "initial_scrape"

        # Priority 2: Data not processed yet
        if not self.state.last_process:
            return "process_data"

        # Priority 3: Not embedded yet
        if not self.state.last_embed:
            return "embed_data"

        # Priority 4: Accuracy below threshold — needs attention
        if self.state.accuracy_score < 85.0 and self.state.last_accuracy_test:
            return "improve_accuracy"

        # Priority 5: Scrape if stale (older than 24 hours)
        last_scrape_time = datetime.fromisoformat(self.state.last_scrape)
        if now - last_scrape_time > timedelta(hours=24):
            return "refresh_scrape"

        # Priority 6: Run accuracy test weekly
        if self.state.last_accuracy_test:
            last_test = datetime.fromisoformat(self.state.last_accuracy_test)
            if now - last_test > timedelta(days=7):
                return "accuracy_test"
        else:
            return "accuracy_test"

        # Priority 7: Self-learning cycle (every 6 hours)
        if hasattr(self.state, 'last_learning') and self.state.last_learning:
            last_learn = datetime.fromisoformat(self.state.last_learning)
            if now - last_learn > timedelta(hours=6):
                return "self_learn"
        elif not hasattr(self.state, 'last_learning'):
            self.state.last_learning = None
            return "self_learn"

        # Priority 8: Generate marketing content daily
        if self.state.last_content_gen:
            last_gen = datetime.fromisoformat(self.state.last_content_gen)
            if now - last_gen > timedelta(days=1):
                return "generate_content"
        else:
            return "generate_content"

        # Priority 9: Security health check (every 2 hours)
        return "security_check"

    async def _execute_task(self, task: str):
        logger.info("executing_task", task=task)
        print(f"\n[AGENT] Executing: {task}")

        try:
            if task == "initial_scrape":
                await self._task_initial_scrape()
            elif task == "process_data":
                await self._task_process_data()
            elif task == "embed_data":
                await self._task_embed_data()
            elif task == "refresh_scrape":
                await self._task_refresh_scrape()
            elif task == "accuracy_test":
                await self._task_accuracy_test()
            elif task == "generate_content":
                await self._task_generate_content()
            elif task == "check_freshness":
                await self._task_check_freshness()
            elif task == "improve_accuracy":
                await self._task_improve_accuracy()
            elif task == "self_learn":
                await self._task_self_learn()
            elif task == "security_check":
                await self._task_security_check()

            self.state.tasks_completed += 1
            self.state.save()
            logger.info("task_complete", task=task, total_completed=self.state.tasks_completed)

        except Exception as e:
            logger.error("task_failed", task=task, error=str(e))
            self.state.record_error(task, str(e))

    async def _task_initial_scrape(self):
        """First-time scraping of all sources."""
        print("[AGENT] Running initial data collection from all sources...")

        from scraper.lhdn_spider import LHDNSpider
        from scraper.sst_spider import SSTSpider
        from scraper.big4_spider import Big4Spider
        from scraper.news_monitor import NewsMonitor

        spiders = [
            ("LHDN", LHDNSpider),
            ("SST", SSTSpider),
            ("Big4", Big4Spider),
            ("News", NewsMonitor),
        ]

        for name, SpiderClass in spiders:
            try:
                print(f"  [SCRAPING] {name}...")
                spider = SpiderClass()
                spider.scrape_all()
                print(f"  [DONE] {name} complete")
            except Exception as e:
                print(f"  [ERROR] {name}: {e}")
                self.state.record_error(f"scrape_{name}", str(e))

        self.state.last_scrape = datetime.now(timezone.utc).isoformat()
        self.state.save()

    async def _task_process_data(self):
        """Process all raw scraped data into chunks."""
        print("[AGENT] Processing raw data into chunks...")

        from processor.pipeline import process_all
        total = process_all()

        self.state.total_chunks = total
        self.state.last_process = datetime.now(timezone.utc).isoformat()
        self.state.save()
        print(f"  [DONE] Created {total} chunks")

    async def _task_embed_data(self):
        """Embed all chunks into vector store."""
        print("[AGENT] Embedding chunks into vector store...")

        if not settings.voyage_api_key:
            print("  [SKIP] No VOYAGE_API_KEY configured")
            self.state.last_embed = datetime.now(timezone.utc).isoformat()
            return

        from embedder.vector_store import embed_all_chunks
        total = embed_all_chunks()

        self.state.last_embed = datetime.now(timezone.utc).isoformat()
        self.state.save()
        print(f"  [DONE] Embedded {total} chunks")

    async def _task_refresh_scrape(self):
        """Re-scrape sources that have changed."""
        print("[AGENT] Checking for updated content...")

        from monitoring.freshness_checker import check_freshness
        report = check_freshness()

        if report["status"] == "needs_update":
            print(f"  [UPDATE] {report['changes_detected']} sources changed, re-scraping...")
            await self._task_initial_scrape()
            await self._task_process_data()
            await self._task_embed_data()
        else:
            print("  [FRESH] All sources are up to date")
            self.state.last_scrape = datetime.now(timezone.utc).isoformat()
            self.state.save()

    async def _task_accuracy_test(self):
        """Run the golden QA dataset to check bot accuracy."""
        print("[AGENT] Running accuracy self-test...")

        if not settings.anthropic_api_key:
            print("  [SKIP] No ANTHROPIC_API_KEY — cannot run accuracy test")
            self.state.last_accuracy_test = datetime.now(timezone.utc).isoformat()
            return

        from monitoring.accuracy_tracker import run_accuracy_test
        report = await run_accuracy_test()

        self.state.accuracy_score = report.get("accuracy", 0)
        self.state.last_accuracy_test = datetime.now(timezone.utc).isoformat()
        self.state.save()

        print(f"  [RESULT] Accuracy: {self.state.accuracy_score}%")
        if self.state.accuracy_score >= 85:
            print("  [PASS] Above 85% threshold")
        else:
            print("  [FAIL] Below 85% — will attempt improvements")

    async def _task_generate_content(self):
        """Generate marketing content (social media posts, blog ideas)."""
        print("[AGENT] Generating marketing content...")

        if not settings.anthropic_api_key:
            print("  [SKIP] No ANTHROPIC_API_KEY configured")
            self.state.last_content_gen = datetime.now(timezone.utc).isoformat()
            return

        from agent.content_generator import generate_daily_content
        content = await generate_daily_content()

        output_dir = Path("data/marketing_content")
        output_dir.mkdir(parents=True, exist_ok=True)

        date_str = datetime.now().strftime("%Y%m%d")
        output_file = output_dir / f"content_{date_str}.json"
        output_file.write_text(json.dumps(content, indent=2, ensure_ascii=False))

        self.state.last_content_gen = datetime.now(timezone.utc).isoformat()
        self.state.save()
        print(f"  [DONE] Generated content saved to {output_file}")

    async def _task_check_freshness(self):
        """Quick check if any sources have new content."""
        from monitoring.freshness_checker import check_freshness
        report = check_freshness()

        if report["status"] == "needs_update":
            print(f"  [ALERT] {report['changes_detected']} sources need updating")
        else:
            print("  [OK] All sources fresh")

        # Sleep before next cycle
        await asyncio.sleep(3600)

    async def _task_improve_accuracy(self):
        """Attempt to improve accuracy by re-processing or adding data."""
        print("[AGENT] Attempting accuracy improvement...")
        print("  [ACTION] Re-running full pipeline with updated data...")

        await self._task_refresh_scrape()
        await self._task_accuracy_test()

        if self.state.accuracy_score >= 85:
            print("  [FIXED] Accuracy now above threshold!")
        else:
            print("  [MANUAL] Accuracy still low — may need manual intervention")
            print("  [HINT] Consider adding more source documents or adjusting chunking")

    async def _task_self_learn(self):
        """
        Self-learning cycle (OpenClaw-inspired):
        1. Review feedback from recent interactions
        2. Fill knowledge gaps automatically
        3. Consolidate memory
        4. Evolve system prompt based on patterns
        """
        print("[AGENT] Running self-learning cycle...")

        from agent.learning.self_improver import SelfImprover
        from agent.learning.feedback_loop import FeedbackLoop
        from agent.learning.memory_store import MemoryStore

        improver = SelfImprover()
        feedback = FeedbackLoop()
        memory = MemoryStore()

        # Step 1: Fill knowledge gaps
        gaps = feedback.get_unresolved_gaps()
        if gaps:
            print(f"  [LEARN] Found {len(gaps)} knowledge gaps to fill...")
            await improver.fill_knowledge_gaps()
            print(f"  [DONE] Processed knowledge gaps")

        # Step 2: Consolidate memory (merge duplicates, prune old data)
        memory.consolidate()
        print("  [DONE] Memory consolidated")

        # Step 3: Evolve system prompt based on accumulated learnings
        if settings.anthropic_api_key:
            suggestions = await improver.evolve_system_prompt()
            if suggestions:
                print(f"  [EVOLVED] System prompt improvement suggestions generated")
            else:
                print("  [OK] No prompt evolution needed yet")

        # Update state
        if not hasattr(self.state, 'last_learning'):
            self.state.last_learning = None
        self.state.last_learning = datetime.now(timezone.utc).isoformat()
        self.state.save()
        print("  [DONE] Self-learning cycle complete")

    async def _task_security_check(self):
        """Run security health checks and detect anomalies."""
        print("[AGENT] Running security check...")

        from agent.self_healing import SelfHealingAgent
        from security.audit_log import audit_log

        # Health check
        healer = SelfHealingAgent()
        report = await healer.run_health_check()

        if not report["overall_healthy"]:
            print(f"  [ALERT] Health issues detected: {[k for k,v in report['checks'].items() if not v['healthy']]}")
        else:
            print("  [OK] All systems healthy")

        # Anomaly detection
        anomalies = audit_log.detect_anomalies()
        if anomalies:
            print(f"  [ALERT] Security anomalies: {len(anomalies)}")
            for a in anomalies:
                print(f"    - {a['type']}: {a}")
        else:
            print("  [OK] No security anomalies")

        # Verify audit log integrity
        integrity = audit_log.verify_integrity()
        if not integrity["valid"]:
            print(f"  [CRITICAL] Audit log may be tampered! {integrity['corrupted_entries']} corrupted entries")
        else:
            print(f"  [OK] Audit log integrity verified ({integrity['entries']} entries)")

        await asyncio.sleep(7200)  # Check every 2 hours


async def main():
    agent = MyCukaiAgent()
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
