from evals.evaluate_run import summarize


def test_summarize_reports_quality_and_api_metrics() -> None:
    payload = {
        "results": [
            {
                "review": {"score": 92},
                "execution": {
                    "status": "pass",
                    "revision_count": 0,
                    "api_calls": 2,
                    "token_usage": {"total": 100},
                    "latency_ms": 500,
                },
            },
            {
                "review": {"score": 80},
                "execution": {
                    "status": "human_review_required",
                    "revision_count": 1,
                    "api_calls": 4,
                    "token_usage": {"total": 220},
                    "latency_ms": 900,
                },
            },
        ]
    }

    result = summarize(payload)

    assert result["rows"] == 2
    assert result["pass"] == 1
    assert result["revision_rate"] == 0.5
    assert result["api_calls"] == 6
    assert result["total_tokens"] == 320
