import json
from pathlib import Path
from datetime import datetime, timezone
import structlog

from bot.conversation import handle_query

logger = structlog.get_logger()

GOLDEN_DATASET_PATH = Path("tests/golden_qa_dataset.json")


async def run_accuracy_test() -> dict:
    if not GOLDEN_DATASET_PATH.exists():
        return {"error": "Golden dataset not found"}

    with open(GOLDEN_DATASET_PATH) as f:
        dataset = json.load(f)

    correct = 0
    total = len(dataset)
    results = []

    for item in dataset:
        question = item["question"]
        expected_keywords = item.get("expected_keywords", [])
        expected_intent = item.get("expected_intent", "")

        result = await handle_query(question)

        response_lower = result["response"].lower()
        keyword_matches = sum(
            1 for kw in expected_keywords
            if kw.lower() in response_lower
        )
        keyword_score = keyword_matches / max(len(expected_keywords), 1)

        intent_correct = result["intent"] == expected_intent if expected_intent else True
        has_disclaimer = "disclaimer" in response_lower or "⚠️" in result["response"]

        passed = keyword_score >= 0.5 and has_disclaimer
        if passed:
            correct += 1

        results.append({
            "question": question,
            "intent_detected": result["intent"],
            "intent_correct": intent_correct,
            "keyword_score": keyword_score,
            "has_disclaimer": has_disclaimer,
            "passed": passed,
        })

    accuracy = correct / total if total > 0 else 0

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_questions": total,
        "correct": correct,
        "accuracy": round(accuracy * 100, 1),
        "target": 85.0,
        "passed": accuracy >= 0.85,
        "details": results,
    }

    # Save report
    report_path = Path("data") / "accuracy_reports"
    report_path.mkdir(parents=True, exist_ok=True)
    report_file = report_path / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("accuracy_test_complete", accuracy=report["accuracy"], passed=report["passed"])
    return report
