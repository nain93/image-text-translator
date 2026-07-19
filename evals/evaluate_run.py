#!/usr/bin/env python3
"""현지화 실행 메타데이터의 품질·비용 지표 요약."""

import argparse
import json
from pathlib import Path


def summarize(payload: dict) -> dict:
    results = payload.get("results", [])
    scores = [result["review"]["score"] for result in results]
    executions = [result["execution"] for result in results]
    return {
        "rows": len(results),
        "pass": sum(result["execution"]["status"] == "pass" for result in results),
        "human_review_required": sum(result["execution"]["status"] != "pass" for result in results),
        "average_review_score": round(sum(scores) / len(scores), 2) if scores else 0,
        "revision_rate": round(
            sum(result["execution"]["revision_count"] > 0 for result in results) / len(results),
            4,
        )
        if results
        else 0,
        "api_calls": sum(execution["api_calls"] for execution in executions),
        "total_tokens": sum(execution["token_usage"]["total"] for execution in executions),
        "latency_ms": sum(execution["latency_ms"] for execution in executions),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("metadata", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.metadata.read_text(encoding="utf-8"))
    print(json.dumps(summarize(payload), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
