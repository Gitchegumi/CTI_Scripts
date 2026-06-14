"""Postgres-backed strategy metrics tests.

Require a live Postgres via ``TRADEGUMI_TEST_DATABASE_URL`` (otherwise skipped).
"""

import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")

import pytest

from tradegumi import journal
from tradegumi.strategy_metrics import (
    CriterionResult,
    EvaluatedOpportunity,
    compare_periods,
    get_summary,
    prune_retention,
    record_opportunity,
)
from tradegumi.tests._pg import requires_postgres

pytestmark = requires_postgres


def iso(days: int = 0) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def make_opportunity(idx: int, *, decision: str = "rejected", failed: int = 1,
                     threshold_version: str = "v1", usable=None, exclusion=None) -> EvaluatedOpportunity:
    criteria = [
        CriterionResult(criterion_name="stoch_rsi", layer="signal_stack", measured_value=20,
                        threshold_value="pullback+cross", passed=failed < 1,
                        margin=-0.1 if failed >= 1 else 0.2, normalized_margin=0.1, required=True),
        CriterionResult(criterion_name="macd", layer="signal_stack", measured_value=0.1,
                        threshold_value="histogram improves", passed=failed < 2,
                        margin=-0.2 if failed >= 2 else 0.3, normalized_margin=0.2, required=True),
        CriterionResult(criterion_name="keltner", layer="signal_stack", measured_value=1.1,
                        threshold_value="band breach", passed=True, margin=0.4,
                        normalized_margin=0.4, required=True),
    ]
    return EvaluatedOpportunity(
        id=f"opp-{idx}",
        evaluated_at=iso(),
        symbol="EURUSD",
        final_decision=decision,
        decision_reason="criteria_failed" if decision == "rejected" else decision,
        threshold_version=threshold_version,
        usable_for_strategy_stats=usable,
        stats_exclusion_reason=exclusion,
        criteria=criteria,
    )


def test_record_opportunity_db_is_durable(pg_backend):
    """record_opportunity commits the opportunity and its criteria atomically."""
    record_opportunity(make_opportunity(1, failed=1), db=pg_backend)
    opps = pg_backend.fetchone("SELECT COUNT(*) AS c FROM evaluated_opportunities")["c"]
    crits = pg_backend.fetchone("SELECT COUNT(*) AS c FROM criterion_results")["c"]
    assert opps == 1
    assert crits == 3


def test_summary_populates_meaningful_fields(monkeypatch, tmp_path, pg_backend):
    """Regression for the empty-structure placeholder: fields are populated."""
    monkeypatch.setattr(journal, "JOURNAL_FILE", tmp_path / "signal_journal.jsonl")
    record_opportunity(make_opportunity(1, failed=1, threshold_version="v1"), db=pg_backend)
    record_opportunity(make_opportunity(2, failed=2, threshold_version="v2"), db=pg_backend)

    summary = get_summary(iso(-1), iso(1), db=pg_backend)
    assert summary["total_evaluated"] == 2
    assert summary["rejected_count"] == 2
    assert summary["criterion_summaries"]
    assert summary["top_blockers"]
    assert summary["top_blockers"][0]["combined_score"] >= 0
    assert summary["pipeline_funnel"]["total_evaluated"] == 2
    assert summary["first_blocker"] is not None
    assert "Strategy threshold version changed during selected period" in summary["data_quality_warnings"]


def test_compare_periods_uses_backend(monkeypatch, tmp_path, pg_backend):
    monkeypatch.setattr(journal, "JOURNAL_FILE", tmp_path / "signal_journal.jsonl")
    old = make_opportunity(1)
    old.evaluated_at = iso(-10)
    recent = make_opportunity(2, decision="emitted", failed=0)
    record_opportunity(old, db=pg_backend)
    record_opportunity(recent, db=pg_backend)

    comparison = compare_periods(iso(-14), iso(-7), iso(-1), iso(1), db=pg_backend)
    assert comparison["deltas"]["total_evaluated"] == 0
    assert comparison["deltas"]["emitted_count"] == 1


def test_append_only_versions_counted(pg_backend):
    """Same id re-evaluated (different evaluated_at) yields two summary rows."""
    opp = make_opportunity(1, decision="rejected", failed=1)
    opp.evaluated_at = iso(-1)
    record_opportunity(opp, db=pg_backend)
    opp2 = make_opportunity(1, decision="emitted", failed=0)
    opp2.evaluated_at = iso()
    record_opportunity(opp2, db=pg_backend)

    summary = get_summary(iso(-2), iso(1), db=pg_backend)
    assert summary["total_evaluated"] == 2
    assert summary["emitted_count"] == 1
    assert summary["rejected_count"] == 1


def test_prune_retention_deletes_old_rows(pg_backend):
    old = make_opportunity(1)
    old.evaluated_at = iso(-120)
    record_opportunity(old, db=pg_backend)
    record_opportunity(make_opportunity(2), db=pg_backend)

    prune_retention(db=pg_backend)

    summary = get_summary(iso(-200), iso(1), db=pg_backend)
    assert summary["total_evaluated"] == 1
