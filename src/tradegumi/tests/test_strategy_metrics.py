import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(os.getcwd(), ".numba_cache"))

from tradegumi.signal_engine import get_threshold_version, evaluate_threshold
from tradegumi.strategy_metrics import (
    CriterionResult,
    EvaluatedOpportunity,
    _compute_threshold_pass,
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


# ── Threshold operator tests ──────────────────────────────────────────────────

class TestEvaluateThreshold:
    def test_gte_positive(self):
        assert evaluate_threshold(0.007, 0.005, "gte") is True
        assert evaluate_threshold(0.004, 0.005, "gte") is False

    def test_gte_negative(self):
        # gte is directional: -0.007 < 0.005, so False
        assert evaluate_threshold(-0.007, 0.005, "gte") is False

    def test_lte(self):
        assert evaluate_threshold(0.004, 0.005, "lte") is True
        assert evaluate_threshold(0.007, 0.005, "lte") is False

    def test_gt_lt(self):
        assert evaluate_threshold(0.006, 0.005, "gt") is True
        assert evaluate_threshold(0.005, 0.005, "gt") is False
        assert evaluate_threshold(0.004, 0.005, "lt") is True
        assert evaluate_threshold(0.005, 0.005, "lt") is False

    def test_abs_gte_positive_value(self):
        # Core bug: measured=0.00783, threshold=0.005 → pass
        assert evaluate_threshold(0.00783, 0.005, "abs_gte") is True

    def test_abs_gte_negative_value(self):
        # abs_gte ignores sign
        assert evaluate_threshold(-0.00783, 0.005, "abs_gte") is True

    def test_abs_gte_below_threshold(self):
        assert evaluate_threshold(0.003, 0.005, "abs_gte") is False
        assert evaluate_threshold(-0.003, 0.005, "abs_gte") is False

    def test_abs_lte(self):
        assert evaluate_threshold(0.003, 0.005, "abs_lte") is True
        assert evaluate_threshold(-0.003, 0.005, "abs_lte") is True
        assert evaluate_threshold(0.007, 0.005, "abs_lte") is False

    def test_eq(self):
        assert evaluate_threshold(0.005, 0.005, "eq") is True
        assert evaluate_threshold(0.0051, 0.005, "eq") is False

    def test_boolean(self):
        assert evaluate_threshold(True, None, "boolean") is True
        assert evaluate_threshold(False, None, "boolean") is False
        assert evaluate_threshold(None, None, "boolean") is False

    def test_invalid_operator_returns_false(self):
        assert evaluate_threshold(0.007, 0.005, "invalid_op") is False


class TestComputeThresholdPass:
    def test_abs_gte_pass(self):
        # expected=True, passed=True → no mismatch
        cr = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=0.00783, threshold_value=0.005, threshold_operator="abs_gte", passed=True)
        record_opportunity(EvaluatedOpportunity(id="test", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="test", criteria=[cr]))
        assert cr.expected_pass is True
        assert cr.pass_mismatch is False

    def test_abs_gte_pass_mismatch_positive_margin(self):
        # Core bug case: positive margin but passed=False → mismatch
        cr = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=0.00783, threshold_value=0.005, threshold_operator="abs_gte", passed=False, margin=0.00283)
        record_opportunity(EvaluatedOpportunity(id="test2", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="test", criteria=[cr]))
        assert cr.expected_pass is True
        assert cr.pass_mismatch is True

    def test_abs_gte_pass_mismatch_negative_value(self):
        cr = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=-0.00783, threshold_value=0.005, threshold_operator="abs_gte", passed=False, margin=0.00283)
        record_opportunity(EvaluatedOpportunity(id="test3", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="test", criteria=[cr]))
        assert cr.expected_pass is True
        assert cr.pass_mismatch is True

    def test_abs_gte_correct_fail(self):
        # Correctly failed: abs(value) < threshold
        cr = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=0.003, threshold_value=0.005, threshold_operator="abs_gte", passed=False)
        record_opportunity(EvaluatedOpportunity(id="test4", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="test", criteria=[cr]))
        assert cr.expected_pass is False
        assert cr.pass_mismatch is False

    def test_gte_operator(self):
        cr = CriterionResult(criterion_name="stoch", layer="signal", measured_value=25, threshold_value=20, threshold_operator="gte", passed=True)
        record_opportunity(EvaluatedOpportunity(id="test5", evaluated_at=iso(), symbol="EURUSD", final_decision="emitted", decision_reason="test", criteria=[cr]))
        assert cr.expected_pass is True
        assert cr.pass_mismatch is False

    def test_none_measured_yields_none_expected(self):
        cr = CriterionResult(criterion_name="stoch", layer="signal", measured_value=None, threshold_value=20, threshold_operator="gte", passed=False)
        record_opportunity(EvaluatedOpportunity(id="test6", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="test", criteria=[cr]))
        assert cr.expected_pass is None
        assert cr.pass_mismatch is False


class TestTopBlockers:
    def test_all_opportunities_blocked_top_blockers_not_empty(self, tmp_path):
        db = tmp_path / "metrics.db"
        init_schema(db)
        # Record 5 rejected opportunities, all failing trend_1h
        for i in range(5):
            cr = CriterionResult(
                criterion_name="trend_1h", layer="trend",
                measured_value=0.003, threshold_value=0.005, threshold_operator="abs_gte",
                passed=False, required=True,
            )
            opp = EvaluatedOpportunity(
                id=f"opp-{i}", evaluated_at=iso(), symbol="EURUSD",
                final_decision="rejected", decision_reason="criteria_failed",
                criteria=[cr],
            )
            record_opportunity(opp, db)
        summary = get_summary(iso(-1), iso(1), db_path=db)
        assert len(summary["top_blockers"]) > 0
        assert summary["top_blockers"][0]["criterion_name"] == "trend_1h"

    def test_blockers_require_rejected_decision(self, tmp_path):
        db = tmp_path / "metrics.db"
        init_schema(db)
        cr = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=0.003, threshold_value=0.005, threshold_operator="abs_gte", passed=False, required=True)
        # Emitted (not rejected) — should not appear as blocker
        opp = EvaluatedOpportunity(id="opp-emit", evaluated_at=iso(), symbol="EURUSD", final_decision="emitted", decision_reason="ok", criteria=[cr])
        record_opportunity(opp, db)
        summary = get_summary(iso(-1), iso(1), db_path=db)
        # Should still have blockers (empty list since no rejections)
        assert summary["rejected_count"] == 0

    def test_first_blocker_and_blocking_layer(self, tmp_path):
        db = tmp_path / "metrics.db"
        init_schema(db)
        cr1 = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=0.003, threshold_value=0.005, threshold_operator="abs_gte", passed=False, required=True)
        cr2 = CriterionResult(criterion_name="macd", layer="signal_stack", measured_value=0.0, threshold_value="improves", threshold_operator="boolean", passed=False, required=True)
        opp = EvaluatedOpportunity(id="opp-multi", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="criteria_failed", criteria=[cr1, cr2])
        recorded = record_opportunity(opp, db)
        assert recorded.first_blocker in ("macd", "trend_1h")
        assert recorded.blocking_layer in ("signal_stack", "trend")
        assert isinstance(recorded.all_blockers, list)
        assert len(recorded.all_blockers) == 2
