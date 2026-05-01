import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(os.getcwd(), ".numba_cache"))

from tradegumi.signal_engine import get_threshold_version
from tradegumi.strategy_metrics import (
    CriterionResult,
    EvaluatedOpportunity,
    compare_periods,
    export_summary,
    get_opportunities,
    get_summary,
    init_schema,
    record_opportunity,
    write_state_snapshot,
)


def iso(days: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def opportunity(idx: int, *, decision: str = "rejected", failed: int = 1, threshold_version: str = "v1") -> EvaluatedOpportunity:
    criteria = [
        CriterionResult(
            criterion_name="stoch_rsi",
            layer="signal_stack",
            measured_value=20,
            threshold_value="pullback+cross",
            passed=failed < 1,
            margin=-0.1 if failed >= 1 else 0.2,
            normalized_margin=0.1,
            required=True,
        ),
        CriterionResult(
            criterion_name="macd",
            layer="signal_stack",
            measured_value=0.1,
            threshold_value="histogram improves",
            passed=failed < 2,
            margin=-0.2 if failed >= 2 else 0.3,
            normalized_margin=0.2,
            required=True,
        ),
        CriterionResult(
            criterion_name="keltner",
            layer="signal_stack",
            measured_value=1.1,
            threshold_value="band breach",
            passed=True,
            margin=0.4,
            normalized_margin=0.4,
            required=True,
        ),
    ]
    return EvaluatedOpportunity(
        id=f"opp-{idx}",
        evaluated_at=iso(),
        symbol="EURUSD",
        final_decision=decision,
        decision_reason="criteria_failed" if decision == "rejected" else decision,
        threshold_version=threshold_version,
        criteria=criteria,
    )


def test_schema_near_miss_state_and_serialization(tmp_path):
    db = tmp_path / "metrics.db"
    state = tmp_path / "strategy_metrics.json"
    init_schema(db)
    recorded = record_opportunity(opportunity(1), db)
    assert recorded.near_miss is True

    summary = get_summary(iso(-1), iso(1), db_path=db)
    assert summary["total_evaluated"] == 1
    assert summary["near_miss_count"] == 1

    write_state_snapshot(summary, state)
    assert state.exists()
    assert "near_miss_count" in state.read_text()

    rows = get_opportunities(iso(-1), iso(1), near_miss=True, db_path=db)
    assert rows[0]["criteria"][0]["criterion_name"] == "stoch_rsi"


def test_retention_prunes_old_rows(tmp_path):
    db = tmp_path / "metrics.db"
    old = opportunity(1)
    old.evaluated_at = iso(-120)
    record_opportunity(old, db)
    record_opportunity(opportunity(2), db)
    summary = get_summary(iso(-200), iso(1), db_path=db)
    assert summary["total_evaluated"] == 1


def test_threshold_version_is_stable():
    assert get_threshold_version() == get_threshold_version()
    assert len(get_threshold_version()) == 12


def test_criterion_summary_blockers_and_warnings(tmp_path):
    db = tmp_path / "metrics.db"
    record_opportunity(opportunity(1, failed=1, threshold_version="v1"), db)
    record_opportunity(opportunity(2, failed=2, threshold_version="v2"), db)
    summary = get_summary(iso(-1), iso(1), db_path=db)

    assert summary["rejected_count"] == 2
    assert summary["criterion_summaries"]
    assert summary["top_blockers"][0]["combined_score"] >= 0
    assert "Strategy threshold version changed during selected period" in summary["data_quality_warnings"]


def test_comparison_and_export(tmp_path):
    db = tmp_path / "metrics.db"
    first = opportunity(1)
    first.evaluated_at = iso(-10)
    second = opportunity(2, decision="emitted", failed=0)
    record_opportunity(first, db)
    record_opportunity(second, db)

    comparison = compare_periods(iso(-14), iso(-7), iso(-1), iso(1), db_path=db)
    assert comparison["deltas"]["total_evaluated"] == 0
    assert comparison["deltas"]["emitted_count"] == 1

    exported = export_summary(iso(-14), iso(1), include_opportunities=True, db_path=db)
    assert len(exported["opportunities"]) == 2


def test_seeded_summary_performance(tmp_path):
    db = tmp_path / "metrics.db"
    start = datetime.now(timezone.utc)
    for i in range(250):
        record_opportunity(opportunity(i, failed=1 if i % 2 else 2), db)
    summary = get_summary(iso(-1), iso(1), db_path=db)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    assert summary["total_evaluated"] == 250
    assert elapsed < 5
