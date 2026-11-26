"""Evaluate classifier prompt versions against the labelled benchmark."""

import argparse
import asyncio
import csv
import json
from collections import Counter
from pathlib import Path

from carecover.config import get_settings
from carecover.db.llm_calls import make_recorder
from carecover.db.session import make_engine, make_sessionmaker
from carecover.llm.classify import LABELS, accuracy, classify
from carecover.llm.gateway import LLMGateway, OpenAICompatProvider
from carecover.llm.prompts import read_prompt, versions

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "classify_eval.json"
PROMPTS = ROOT / "prompts"
OUTPUT = ROOT / "reports" / "classifier"


async def evaluate(
    limit: int | None = None,
    delay: float = 0.5,
    dataset: Path = DATASET,
    output: Path = OUTPUT,
) -> None:
    rows = json.loads(DATASET.read_text(encoding="utf-8-sig"))
    if limit:
        rows = rows[:limit]

    prompt_versions = versions(PROMPTS, "classify")
    if not prompt_versions:
        raise SystemExit("No classify_vN.md prompt files found.")

    settings = get_settings()
    engine = make_engine(settings)
    sessionmaker = make_sessionmaker(engine)
    groq = OpenAICompatProvider(
        "groq",
        settings.llm_fallback_base_url,
        settings.groq_api_key,
        settings.llm_fallback_model,
        timeout=settings.llm_timeout_seconds,
    )
    gateway = LLMGateway(
        [groq],
        recorder=make_recorder(sessionmaker),
        usd_inr=settings.usd_inr,
    )

    results = []

    try:
        for version in prompt_versions:
            prompt = read_prompt(PROMPTS, f"{version}")
            print(f"\nEvaluating {version}: {len(rows)} questions", flush=True)

            for index, item in enumerate(rows, start=1):
                question = item["question"]
                expected = item["label"]

                record = {
                    "version": version,
                    "question": question,
                    "expected": expected,
                    "predicted": "error",
                    "correct": False,
                    "provider": "",
                    "model": "",
                    "fallback_used": False,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "latency_ms": 0,
                    "cost_inr": 0.0,
                    "error": "",
                }

                try:
                    predicted, result = await classify(gateway, prompt, version, question)
                    record.update(
                        {
                            "predicted": predicted,
                            "correct": predicted == expected,
                            "provider": result.provider,
                            "model": result.model,
                            "fallback_used": result.fallback_used,
                            "tokens_in": result.tokens_in,
                            "tokens_out": result.tokens_out,
                            "latency_ms": result.latency_ms,
                            "cost_inr": float(result.cost_inr),
                        }
                    )
                except Exception as exc:
                    record["error"] = f"{type(exc).__name__}: {exc}"
                    print(f"  [{index}/{len(rows)}] ERROR: {record['error']}", flush=True)

                results.append(record)
                if not record["error"]:
                    status = "OK" if record["correct"] else "WRONG"
                    print(
                        f"  [{index}/{len(rows)}] {status}: "
                        f"{record['predicted']} (expected {expected})",
                        flush=True,
                    )

                if delay:
                    await asyncio.sleep(delay)

    finally:
        await engine.dispose()

    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    fields = list(results[0].keys()) if results else []
    with (OUTPUT / "results.csv").open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    summaries = []
    for version in prompt_versions:
        version_rows = [r for r in results if r["version"] == version]
        score_rows = [{"label": r["expected"], "got": r["predicted"]} for r in version_rows]
        summary = {
            "version": version,
            "accuracy": accuracy(score_rows),
            "correct": sum(r["correct"] for r in version_rows),
            "total": len(version_rows),
            "errors": sum(bool(r["error"]) for r in version_rows),
            "invalid": sum(r["predicted"] == "invalid" for r in version_rows),
            "by_class": {},
            "confusion": {},
        }

        for label in LABELS:
            class_rows = [r for r in version_rows if r["expected"] == label]
            summary["by_class"][label] = {
                "correct": sum(r["correct"] for r in class_rows),
                "total": len(class_rows),
                "accuracy": accuracy(
                    [{"label": r["expected"], "got": r["predicted"]} for r in class_rows]
                ),
            }

        for expected in LABELS:
            summary["confusion"][expected] = dict(
                Counter(r["predicted"] for r in version_rows if r["expected"] == expected)
            )

        summaries.append(summary)

    (OUTPUT / "accuracy.json").write_text(
        json.dumps(summaries, indent=2),
        encoding="utf-8",
    )

    print("\n=== CLASSIFIER ACCURACY ===")
    print(f"{'Version':<18} {'Correct':>8} {'Total':>7} {'Accuracy':>10} {'Errors':>8}")
    for summary in summaries:
        print(
            f"{summary['version']:<18} "
            f"{summary['correct']:>8} "
            f"{summary['total']:>7} "
            f"{summary['accuracy']:>9.1%} "
            f"{summary['errors']:>8}"
        )

    print(f"\nSaved results to: {OUTPUT.relative_to(ROOT)}")
    print("Files: results.json, results.csv, accuracy.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate classifier prompt versions.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Evaluate only the first N questions.",
    )
    parser.add_argument("--delay", type=float, default=0.5, help="Seconds between model calls.")
    args = parser.parse_args()
    asyncio.run(evaluate(args.limit, args.delay))


if __name__ == "__main__":
    main()
