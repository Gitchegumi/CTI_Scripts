import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
os.environ.setdefault("NUMBA_CACHE_DIR", os.path.join(os.getcwd(), ".numba_cache"))

from tradegumi.signal_engine import classify_trend_decision, get_threshold_version, evaluate_threshold
from tradegumi import journal
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


def temp_db(name: str = "metrics.db") -> Path:
    base = Path(__file__).resolve().parents[3] / ".tmp" / "cti_strategy_metrics_tests" / uuid.uuid4().hex
    base.mkdir(parents=True, exist_ok=True)
    return base / name


def opportunity(
    idx: int,
    *,
    decision: str = "rejected",
    failed: int = 1,
    threshold_version: str = "v1",
    usable_for_strategy_stats=None,
    stats_exclusion_reason=None,
) -> EvaluatedOpportunity:
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
        usable_for_strategy_stats=usable_for_strategy_stats,
        stats_exclusion_reason=stats_exclusion_reason,
        criteria=criteria,
    )


def test_schema_near_miss_state_and_serialization():
    db = temp_db()
    state = db.with_name("strategy_metrics.json")
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


def test_retention_prunes_old_rows():
    db = temp_db()
    old = opportunity(1)
    old.evaluated_at = iso(-120)
    record_opportunity(old, db)
    record_opportunity(opportunity(2), db)
    summary = get_summary(iso(-200), iso(1), db_path=db)
    assert summary["total_evaluated"] == 1


def test_threshold_version_is_stable():
    assert get_threshold_version() == get_threshold_version()
    assert len(get_threshold_version()) == 12


def test_threshold_version_includes_pullback_thresholds(monkeypatch):
    import tradegumi.config as config_module

    before = get_threshold_version()
    monkeypatch.setattr(config_module, "PULLBACK_15M_MEMORY_CANDLES", config_module.PULLBACK_15M_MEMORY_CANDLES + 1, raising=False)

    assert get_threshold_version() != before


def test_threshold_version_includes_pullback_trigger_and_macd_settings(monkeypatch):
    import tradegumi.config as config_module

    before = get_threshold_version()
    monkeypatch.setattr(
        config_module,
        "PULLBACK_TRIGGER_MAX_BODY_RANGE_RATIO",
        config_module.PULLBACK_TRIGGER_MAX_BODY_RANGE_RATIO + 0.01,
        raising=False,
    )
    assert get_threshold_version() != before

    before = get_threshold_version()
    monkeypatch.setattr(
        config_module,
        "PULLBACK_STOCH_MEMORY_BARS",
        config_module.PULLBACK_STOCH_MEMORY_BARS + 1,
        raising=False,
    )
    assert get_threshold_version() != before

    before = get_threshold_version()
    monkeypatch.setattr(
        config_module,
        "PULLBACK_MACD_HARD_BLOCK_ENABLED",
        not config_module.PULLBACK_MACD_HARD_BLOCK_ENABLED,
        raising=False,
    )
    assert get_threshold_version() != before


def test_additive_pipeline_fields_round_trip_and_json_compatible():
    db = temp_db()
    cr = CriterionResult(
        criterion_name="signal_engine_data",
        layer="data_quality",
        measured_value={"missing_input": "candles"},
        threshold_value="complete signal stack inputs",
        passed=None,
        required=True,
        data_quality="missing",
        diagnostic_state="missing_data",
        reason="signal_engine_data:missing",
        context={"timeframe": "M5", "missing_input": "candles"},
    )
    opp = EvaluatedOpportunity(
        id="round-trip",
        evaluated_at=iso(),
        symbol="EURUSD",
        final_decision="indeterminate",
        decision_reason="missing_signal_engine_data",
        threshold_version="unknown",
        criteria=[cr],
    )
    record_opportunity(opp, db)

    exported = get_opportunities(iso(-1), iso(1), db_path=db)[0]

    assert exported["pipeline_state"] == "trend_candidate_signal_data_missing"
    assert exported["threshold_version_unknown_reason"] == "legacy_or_missing_threshold_version"
    assert exported["criteria"][0]["diagnostic_state"] == "missing_data"
    assert exported["criteria"][0]["context"]["missing_input"] == "candles"


def test_legacy_signal_engine_data_typo_is_normalized():
    db = temp_db()
    cr = CriterionResult(
        criterion_name="singal_engine_data",
        layer="data_quality",
        measured_value={"missing_input": "last_closed_candle_or_indicator_window"},
        threshold_value="complete signal stack inputs",
        passed=None,
        required=True,
        data_quality="missing",
        diagnostic_state="missing_data",
        reason=None,
        context={"missing_input": "last_closed_candle_or_indicator_window"},
    )
    opp = EvaluatedOpportunity(
        id="legacy-typo",
        evaluated_at=iso(),
        symbol="EURUSD",
        final_decision="indeterminate",
        decision_reason="missing_signal_engine_data",
        criteria=[cr],
    )

    record_opportunity(opp, db)
    exported = get_opportunities(iso(-1), iso(1), db_path=db)[0]
    summary = get_summary(iso(-1), iso(1), db_path=db)

    assert exported["criteria"][0]["criterion_name"] == "signal_engine_data"
    assert summary["criterion_summaries"][0]["criterion_name"] == "signal_engine_data"


def test_criterion_summary_blockers_and_warnings():
    db = temp_db()
    record_opportunity(opportunity(1, failed=1, threshold_version="v1"), db)
    record_opportunity(opportunity(2, failed=2, threshold_version="v2"), db)
    summary = get_summary(iso(-1), iso(1), db_path=db)

    assert summary["rejected_count"] == 2
    assert summary["criterion_summaries"]
    assert summary["top_blockers"][0]["combined_score"] >= 0
    assert "Strategy threshold version changed during selected period" in summary["data_quality_warnings"]
    assert summary["threshold_version_counts"]["v1"] == 1
    assert summary["threshold_version_counts"]["v2"] == 1


def test_comparison_and_export():
    db = temp_db()
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


def test_summary_counts_only_usable_emitted_signals_as_trade_opportunities():
    db = temp_db()
    record_opportunity(opportunity(1, decision="emitted", failed=0, usable_for_strategy_stats=True), db)
    record_opportunity(opportunity(2, decision="emitted", failed=0, usable_for_strategy_stats=False, stats_exclusion_reason="duplicate_setup"), db)
    record_opportunity(opportunity(3, decision="emitted", failed=0), db)

    summary = get_summary(iso(-1), iso(1), db_path=db)
    exported = get_opportunities(iso(-1), iso(1), db_path=db)

    assert summary["emitted_count"] == 3
    assert summary["trade_opportunity_count"] == 1
    assert summary["stats_excluded_count"] == 1
    assert summary["stats_unknown_eligibility_count"] == 1
    assert summary["stats_exclusion_counts"] == {"duplicate_setup": 1}
    assert {row["id"]: row["usable_for_strategy_stats"] for row in exported}["opp-1"] is True


def test_summary_includes_prime_suppression_metrics(tmp_path, monkeypatch):
    journal_file = tmp_path / "signal_journal.jsonl"
    monkeypatch.setattr(journal, "JOURNAL_FILE", journal_file)
    journal_file.write_text(
        "\n".join(
            [
                '{"signal_id":"sig-1","symbol":"EURUSD","signal_timestamp":"2026-05-06T12:00:00+00:00","prime_suppressed_signal_count":3,"prime_suppressed_same_direction_count":1,"prime_suppressed_opposite_direction_count":2,"prime_suppressed_signal_outcomes":[{"outcome":"invalidated_by_prime"},{"outcome":"invalidated_by_prime"},{"outcome":"invalidated_by_prime"}],"prime_closed_reason":"inferred_sl","prime_close_ambiguous":true}',
                '{"signal_id":"sig-2","symbol":"GBPJPY","signal_timestamp":"2026-05-06T13:00:00+00:00","prime_suppressed_signal_count":1,"prime_suppressed_same_direction_count":1,"prime_closed_reason":"inferred_tp","prime_close_ambiguous":false}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    summary = get_summary("2026-05-06", "2026-05-06", db_path=temp_db())

    assert summary["total_prime_suppressed_signals"] == 4
    assert summary["prime_suppressed_signals_by_symbol"] == {"GBPJPY": 1, "EURUSD": 3}
    assert summary["prime_suppressed_same_direction_count"] == 2
    assert summary["prime_suppressed_opposite_direction_count"] == 2
    assert summary["prime_invalidated_by_prime_count"] == 4
    assert summary["inferred_tp_close_count"] == 1
    assert summary["inferred_sl_close_count"] == 1
    assert summary["ambiguous_prime_close_count"] == 1


def test_date_only_end_includes_selected_day_and_excludes_following_day():
    db = temp_db()
    selected_day = opportunity(1)
    selected_day.evaluated_at = "2026-05-06T23:59:59+00:00"
    following_day = opportunity(2)
    following_day.evaluated_at = "2026-05-07T00:00:00+00:00"
    record_opportunity(selected_day, db)
    record_opportunity(following_day, db)

    summary = get_summary("2026-05-06", "2026-05-06", db_path=db)
    opportunities = get_opportunities("2026-05-06", "2026-05-06", db_path=db)
    exported = export_summary("2026-05-06", "2026-05-06", include_opportunities=True, db_path=db)

    assert summary["total_evaluated"] == 1
    assert opportunities[0]["id"] == "opp-1"
    assert [opp["id"] for opp in exported["opportunities"]] == ["opp-1"]


def test_metrics_filters_and_offset_pagination():
    db = temp_db()
    first = opportunity(1, decision="rejected")
    first.strategy = "CTI-v1"
    first.signal_type = "pullback"
    first.evaluated_at = "2026-05-06T12:00:00+00:00"
    second = opportunity(2, decision="rejected")
    second.strategy = "CTI-v2"
    second.signal_type = "continuation"
    second.evaluated_at = "2026-05-06T12:01:00+00:00"
    third = opportunity(3, decision="emitted", failed=0)
    third.strategy = "CTI-v2"
    third.signal_type = "continuation"
    third.evaluated_at = "2026-05-06T12:02:00+00:00"
    record_opportunity(first, db)
    record_opportunity(second, db)
    record_opportunity(third, db)

    summary = get_summary(
        "2026-05-06",
        "2026-05-06",
        strategy="CTI-v2",
        signal_type="continuation",
        decision="rejected",
        first_blocker="stoch_rsi",
        db_path=db,
    )
    page = get_opportunities("2026-05-06", "2026-05-06", limit=1, offset=1, db_path=db)

    assert summary["total_evaluated"] == 1
    assert summary["strategy_counts"] == {"CTI-v2": 1}
    assert summary["signal_type_counts"] == {"continuation": 1}
    assert page[0]["id"] == "opp-2"


def test_seeded_summary_performance():
    db = temp_db()
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
        db = temp_db()
        # expected=True, passed=True → no mismatch
        cr = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=0.00783, threshold_value=0.005, threshold_operator="abs_gte", passed=True)
        record_opportunity(EvaluatedOpportunity(id="test", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="test", criteria=[cr]), db)
        assert cr.expected_pass is True
        assert cr.pass_mismatch is False

    def test_abs_gte_pass_mismatch_positive_margin(self):
        db = temp_db()
        # Core bug case: positive margin but passed=False → mismatch
        cr = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=0.00783, threshold_value=0.005, threshold_operator="abs_gte", passed=False, margin=0.00283)
        record_opportunity(EvaluatedOpportunity(id="test2", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="test", criteria=[cr]), db)
        assert cr.expected_pass is True
        assert cr.pass_mismatch is True

    def test_abs_gte_pass_mismatch_negative_value(self):
        db = temp_db()
        cr = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=-0.00783, threshold_value=0.005, threshold_operator="abs_gte", passed=False, margin=0.00283)
        record_opportunity(EvaluatedOpportunity(id="test3", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="test", criteria=[cr]), db)
        assert cr.expected_pass is True
        assert cr.pass_mismatch is True

    def test_abs_gte_correct_fail(self):
        db = temp_db()
        # Correctly failed: abs(value) < threshold
        cr = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=0.003, threshold_value=0.005, threshold_operator="abs_gte", passed=False)
        record_opportunity(EvaluatedOpportunity(id="test4", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="test", criteria=[cr]), db)
        assert cr.expected_pass is False
        assert cr.pass_mismatch is False

    def test_gte_operator(self):
        db = temp_db()
        cr = CriterionResult(criterion_name="stoch", layer="signal", measured_value=25, threshold_value=20, threshold_operator="gte", passed=True)
        record_opportunity(EvaluatedOpportunity(id="test5", evaluated_at=iso(), symbol="EURUSD", final_decision="emitted", decision_reason="test", criteria=[cr]), db)
        assert cr.expected_pass is True
        assert cr.pass_mismatch is False

    def test_expected_pass_rehydrates_from_export(self):
        db = temp_db()
        cr = CriterionResult(
            criterion_name="trend_1h",
            layer="trend",
            measured_value=-0.00783,
            threshold_value=0.005,
            threshold_operator="abs_gte",
            passed=False,
        )
        record_opportunity(
            EvaluatedOpportunity(
                id="rehydrate",
                evaluated_at=iso(),
                symbol="EURUSD",
                final_decision="skipped",
                decision_reason="no_trend",
                criteria=[cr],
            ),
            db,
        )
        exported = get_opportunities(iso(-1), iso(1), db_path=db)
        criterion = exported[0]["criteria"][0]
        assert criterion["expected_pass"] is True
        assert criterion["pass_mismatch"] is True
        assert criterion["blocked_signal"] is True

    def test_none_measured_yields_none_expected(self):
        db = temp_db()
        cr = CriterionResult(criterion_name="stoch", layer="signal", measured_value=None, threshold_value=20, threshold_operator="gte", passed=False)
        record_opportunity(EvaluatedOpportunity(id="test6", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="test", criteria=[cr]), db)
        assert cr.expected_pass is None
        assert cr.pass_mismatch is False


class TestTopBlockers:
    def test_all_opportunities_blocked_top_blockers_not_empty(self):
        db = temp_db()
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

    def test_top_blocker_quality_component_uses_other_required_criteria(self):
        db = temp_db()
        init_schema(db)
        opp = EvaluatedOpportunity(
            id="opp-quality",
            evaluated_at=iso(),
            symbol="EURUSD",
            final_decision="rejected",
            decision_reason="criteria_failed",
            criteria=[
                CriterionResult(
                    criterion_name="stoch_rsi",
                    layer="signal_stack",
                    measured_value=10,
                    threshold_value=20,
                    threshold_operator="gte",
                    passed=False,
                    normalized_margin=0.25,
                    required=True,
                ),
                CriterionResult(
                    criterion_name="macd",
                    layer="signal_stack",
                    measured_value=0.1,
                    threshold_value="histogram improves",
                    passed=True,
                    required=True,
                ),
                CriterionResult(
                    criterion_name="keltner",
                    layer="signal_stack",
                    measured_value=1.1,
                    threshold_value="band breach",
                    passed=True,
                    required=True,
                ),
            ],
        )
        record_opportunity(opp, db)

        blocker = get_summary(iso(-1), iso(1), db_path=db)["top_blockers"][0]

        assert blocker["criterion_name"] == "stoch_rsi"
        assert blocker["quality_component"] == 1.0
        assert blocker["combined_score"] > 0.7

    def test_blockers_require_rejected_decision(self):
        db = temp_db()
        init_schema(db)
        cr = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=0.003, threshold_value=0.005, threshold_operator="abs_gte", passed=False, required=True)
        # Emitted (not rejected) — should not appear as blocker
        opp = EvaluatedOpportunity(id="opp-emit", evaluated_at=iso(), symbol="EURUSD", final_decision="emitted", decision_reason="ok", criteria=[cr])
        record_opportunity(opp, db)
        summary = get_summary(iso(-1), iso(1), db_path=db)
        # Should still have blockers (empty list since no rejections)
        assert summary["rejected_count"] == 0

    def test_first_blocker_and_blocking_layer(self):
        db = temp_db()
        init_schema(db)
        cr1 = CriterionResult(criterion_name="trend_1h", layer="trend", measured_value=0.003, threshold_value=0.005, threshold_operator="abs_gte", passed=False, required=True)
        cr2 = CriterionResult(criterion_name="macd", layer="signal_stack", measured_value=0.0, threshold_value="improves", threshold_operator="boolean", passed=False, required=True)
        opp = EvaluatedOpportunity(id="opp-multi", evaluated_at=iso(), symbol="EURUSD", final_decision="rejected", decision_reason="criteria_failed", criteria=[cr1, cr2])
        recorded = record_opportunity(opp, db)
        assert recorded.first_blocker in ("macd", "trend_1h")
        assert recorded.blocking_layer in ("signal_stack", "trend")
        assert isinstance(recorded.all_blockers, list)
        assert len(recorded.all_blockers) == 2

    def test_skipped_no_trend_classification_counts_as_top_blocker(self):
        db = temp_db()
        init_schema(db)
        trend_decision = classify_trend_decision(0.009, 0.011, -0.003, 0.005, 0.008, 0.002)
        opp = EvaluatedOpportunity(
            id="opp-conflict",
            evaluated_at=iso(),
            symbol="EURUSD",
            final_decision="skipped",
            decision_reason="no_trend",
            trend="flat",
            direction="none",
            trend_decision=trend_decision,
            criteria=[
                CriterionResult("trend_1h", "trend", 0.009, 0.005, "abs_gte", True),
                CriterionResult("trend_15m", "trend", 0.011, 0.008, "abs_gte", True),
                CriterionResult("trend_5m", "trend", -0.003, 0.002, "abs_gte", True),
            ],
        )
        recorded = record_opportunity(opp, db)
        summary = get_summary(iso(-1), iso(1), db_path=db)

        assert recorded.first_blocker == "trend:direction_conflict"
        assert recorded.all_blockers == ["trend:direction_conflict"]
        assert recorded.blocking_layer == "trend"
        assert summary["skipped_count"] == 1
        assert summary["indeterminate_count"] == 0
        assert summary["top_blockers"][0]["criterion_name"] == "trend:direction_conflict"

    def test_indeterminate_signal_engine_missing_counts_as_top_blocker(self):
        db = temp_db()
        init_schema(db)
        cr = CriterionResult(
            criterion_name="signal_engine_data",
            layer="data_quality",
            measured_value={"missing_input": "last_closed_candle_or_indicator_window"},
            threshold_value="complete signal stack inputs",
            passed=None,
            required=True,
            data_quality="missing",
            diagnostic_state="missing_data",
            reason="signal_engine_data:missing",
            context={"stage": "signal_stack", "timeframe": "M5"},
        )
        opp = EvaluatedOpportunity(
            id="opp-signal-missing",
            evaluated_at=iso(),
            symbol="EURUSD",
            final_decision="indeterminate",
            decision_reason="missing_signal_engine_data",
            direction="BUY",
            criteria=[cr],
        )
        recorded = record_opportunity(opp, db)
        summary = get_summary(iso(-1), iso(1), db_path=db)

        assert recorded.first_blocker == "signal_engine_data:missing"
        assert recorded.all_blockers == ["signal_engine_data:missing"]
        assert recorded.blocking_layer == "data_quality"
        assert recorded.criteria[0].blocked_signal is True
        assert summary["top_blockers"][0]["criterion_name"] == "signal_engine_data:missing"

    def test_signal_stack_data_not_ready_populates_readiness_fields(self):
        db = temp_db()
        context = {
            "stage": "signal_stack",
            "timeframe": "M5",
            "missing_input": "last_closed_candle_or_indicator_window",
            "error_type": "DataNotReady",
            "required_candles": 35,
            "available_candles": 17,
            "required_closed_candles": 35,
            "available_closed_candles": 17,
            "required_indicator_window": 14,
            "available_indicator_window": 0,
            "message": "Signal stack skipped because the last closed candle or required indicator window is unavailable.",
        }
        cr = CriterionResult(
            criterion_name="signal_engine_data",
            layer="data_quality",
            measured_value=context,
            threshold_value="complete candles and indicators",
            passed=None,
            required=True,
            data_quality="missing",
            diagnostic_state="missing_data",
            reason="signal_engine_data:missing",
            context=context,
        )
        opp = EvaluatedOpportunity(
            id="opp-signal-data-not-ready",
            evaluated_at=iso(),
            symbol="EURUSD",
            final_decision="rejected",
            decision_reason="signal_stack_data_not_ready",
            direction="BUY",
            criteria=[cr],
        )

        recorded = record_opportunity(opp, db)
        exported = get_opportunities(iso(-1), iso(1), db_path=db)[0]

        assert recorded.final_decision == "indeterminate"
        assert recorded.decision_reason == "signal_stack_data_not_ready"
        assert recorded.first_blocker == "signal_engine_data:missing"
        assert recorded.all_blockers == ["signal_engine_data:missing"]
        assert recorded.blocking_layer == "data_quality"
        assert recorded.criteria[0].blocked_signal is True
        assert exported["criteria"][0]["context"]["error_type"] == "DataNotReady"
        assert exported["criteria"][0]["context"]["available_indicator_window"] == 0
        assert exported["criteria"][0]["context"]["missing_input"] == "last_closed_candle_or_indicator_window"

    def test_oanda_failure_metrics_preserve_diagnostic_context(self):
        db = temp_db()
        context = {
            "stage": "signal_stack",
            "provider": "oanda",
            "error_type": "oanda_gateway_timeout",
            "method": "GET",
            "path": "/v3/instruments/EUR_USD/candles",
            "status_code": 504,
            "instrument": "EUR_USD",
            "granularity": "M5",
            "attempts": 3,
            "max_attempts": 3,
            "retryable": True,
            "message": "Oanda candle fetch failed with HTTP 504",
        }
        cr = CriterionResult(
            criterion_name="signal_engine_data",
            layer="data_quality",
            measured_value=dict(context),
            threshold_value="complete candles and indicators",
            passed=None,
            required=True,
            data_quality="missing",
            diagnostic_state="missing_data",
            reason="signal_engine_data:missing",
            context=dict(context),
        )

        recorded = record_opportunity(
            EvaluatedOpportunity(
                id="opp-oanda-timeout",
                evaluated_at=iso(),
                symbol="EURUSD",
                final_decision="rejected",
                decision_reason="oanda_gateway_timeout",
                criteria=[cr],
            ),
            db,
        )
        exported = get_opportunities(iso(-1), iso(1), db_path=db)[0]

        assert recorded.final_decision == "indeterminate"
        assert recorded.blocking_layer == "data_quality"
        assert exported["criteria"][0]["context"] == context

    def test_candle_close_waiting_is_not_near_miss_or_rejection(self):
        db = temp_db()
        cr = CriterionResult(
            criterion_name="candle_close_gate",
            layer="timing",
            measured_value=31.27,
            threshold_value="0 seconds until close",
            threshold_operator="lte",
            passed=False,
            required=True,
            diagnostic_state="waiting",
            reason="candle_close_gate:waiting_for_close",
            context={
                "current_time": "2026-05-06T12:04:28+00:00",
                "candle_open_time": "2026-05-06T12:00:00+00:00",
                "candle_close_time": "2026-05-06T12:05:00+00:00",
                "seconds_until_close": 31.27,
                "seconds_since_close": 0,
                "timeframe": "M5",
                "gate_rule": "pass_after_candle_close",
                "margin_units": "seconds",
            },
        )
        opp = EvaluatedOpportunity(
            id="opp-waiting",
            evaluated_at=iso(),
            symbol="EURUSD",
            final_decision="skipped",
            decision_reason="candle_close_gate:waiting_for_close",
            direction="BUY",
            criteria=[cr],
        )
        recorded = record_opportunity(opp, db)
        summary = get_summary(iso(-1), iso(1), db_path=db)

        assert recorded.near_miss is False
        assert recorded.pipeline_state == "trend_candidate_candle_close_waiting"
        assert summary["near_miss_count"] == 0
        assert summary["rejected_count"] == 0
        assert summary["pipeline_funnel"]["candle_close_gate_waiting_or_failed"] == 1

    def test_candle_close_after_close_pass_context_is_exported(self):
        db = temp_db()
        cr = CriterionResult(
            criterion_name="candle_close_gate",
            layer="timing",
            measured_value=2.0,
            threshold_value=">=0 seconds since close",
            threshold_operator="gte",
            passed=True,
            required=True,
            diagnostic_state="evaluated",
            reason="candle_close_gate:passed",
            context={
                "current_time": "2026-05-06T12:05:02+00:00",
                "candle_open_time": "2026-05-06T12:00:00+00:00",
                "candle_close_time": "2026-05-06T12:05:00+00:00",
                "seconds_until_close": 0,
                "seconds_since_close": 2.0,
                "timeframe": "M5",
                "gate_rule": "pass_after_candle_close",
                "margin_units": "seconds",
            },
        )
        record_opportunity(
            EvaluatedOpportunity(
                id="opp-after-close",
                evaluated_at=iso(),
                symbol="EURUSD",
                final_decision="emitted",
                decision_reason="emitted",
                criteria=[cr],
            ),
            db,
        )

        exported = get_opportunities(iso(-1), iso(1), db_path=db)[0]
        summary = get_summary(iso(-1), iso(1), db_path=db)

        assert exported["criteria"][0]["context"]["seconds_since_close"] == 2.0
        assert exported["criteria"][0]["context"]["margin_units"] == "seconds"
        assert summary["pipeline_funnel"]["candle_close_gate_passed"] == 1

    def test_near_miss_reason_counts_explain_count(self):
        db = temp_db()
        record_opportunity(opportunity(1, failed=1), db)
        summary = get_summary(iso(-1), iso(1), db_path=db)

        assert summary["near_miss_count"] == 1
        assert sum(summary["near_miss_reason_counts"].values()) == 1
        assert "stoch_rsi" in summary["near_miss_reason_counts"]

    def test_summary_funnel_counts_pipeline_stages(self):
        db = temp_db()
        trend_skip = EvaluatedOpportunity(
            id="funnel-trend",
            evaluated_at=iso(),
            symbol="EURUSD",
            final_decision="skipped",
            decision_reason="no_trend",
            trend_decision=classify_trend_decision(0.001, 0.004, 0.003, 0.005, 0.008, 0.002),
        )
        missing = EvaluatedOpportunity(
            id="funnel-missing",
            evaluated_at=iso(),
            symbol="EURUSD",
            final_decision="indeterminate",
            decision_reason="missing_signal_engine_data",
            criteria=[
                CriterionResult(
                    criterion_name="signal_engine_data",
                    layer="data_quality",
                    measured_value={"missing_input": "candles"},
                    threshold_value="complete",
                    passed=None,
                    data_quality="missing",
                    diagnostic_state="missing_data",
                    reason="signal_engine_data:missing",
                )
            ],
        )
        record_opportunity(trend_skip, db)
        record_opportunity(missing, db)
        record_opportunity(opportunity(3, decision="emitted", failed=0), db)
        record_opportunity(opportunity(4, decision="rejected", failed=1), db)

        funnel = get_summary(iso(-1), iso(1), db_path=db)["pipeline_funnel"]

        assert funnel["total_evaluated"] == 4
        assert funnel["trend_skipped"] == 1
        assert funnel["trend_candidate_found"] == 3
        assert funnel["signal_data_missing"] == 1
        assert funnel["signal_rejected"] == 1
        assert funnel["signal_emitted"] == 1
        assert funnel["indeterminate"] == 1

    def test_threshold_version_unknown_reason_is_summarized(self):
        db = temp_db()
        record_opportunity(opportunity(1, threshold_version="unknown"), db)

        summary = get_summary(iso(-1), iso(1), db_path=db)

        assert summary["threshold_version_counts"]["unknown"] == 1
        assert summary["threshold_version_unknown_reasons"]["legacy_or_missing_threshold_version"] == 1


class TestTrendDecisionDiagnostics:
    def test_all_strengths_pass_but_directions_conflict(self):
        decision = classify_trend_decision(0.009, 0.011, -0.003, 0.005, 0.008, 0.002)

        assert decision["strength_passed_1h"] is True
        assert decision["strength_passed_15m"] is True
        assert decision["strength_passed_5m"] is True
        assert decision["direction_1h"] == "up"
        assert decision["direction_15m"] == "up"
        assert decision["direction_5m"] == "down"
        assert decision["directions_agree"] is False
        assert decision["trend_result"] == "flat"
        assert decision["final_direction"] == "none"
        assert decision["no_trend_reason"] == "direction_conflict"

    def test_15m_strength_failure_is_named(self):
        decision = classify_trend_decision(0.009, 0.004, 0.003, 0.005, 0.008, 0.002)

        assert decision["strength_passed_15m"] is False
        assert decision["no_trend_reason"] == "insufficient_strength_15m"

    def test_multiple_strength_failures_are_grouped(self):
        decision = classify_trend_decision(0.001, 0.004, 0.003, 0.005, 0.008, 0.002)

        assert decision["no_trend_reason"] == "multiple_insufficient_strength"

    def test_engine_error_reason_forces_indeterminate(self):
        db = temp_db()
        record_opportunity(
            EvaluatedOpportunity(
                id="engine-error",
                evaluated_at=iso(),
                symbol="EURUSD",
                final_decision="skipped",
                decision_reason="engine_error",
                data_complete=False,
            ),
            db,
        )

        summary = get_summary(iso(-1), iso(1), db_path=db)
        assert summary["indeterminate_count"] == 1
        assert summary["skipped_count"] == 0

class TestShockAndFilteredLRFields:
    """Bug 4: Persist shock and filtered LR diagnostic fields."""

    def _make_opportunity(self, **overrides) -> EvaluatedOpportunity:
        defaults = dict(
            id="opp-shock-test",
            evaluated_at=iso(),
            symbol="EURUSD",
            timeframe="H1",
            mode="production",
            strategy="Trender",
            direction="LONG",
            trend="Uptrend",
            final_decision="rejected",
            decision_reason="market_invalid:volatility_shock",
            confidence=0.0,
            failed_criteria_count=1,
            near_miss=False,
            data_complete=True,
            data_quality_notes=[],
            threshold_version="v1",
            created_at=iso(),
            criteria=[],
            first_blocker="volatility_shock",
            all_blockers=["volatility_shock"],
            blocking_layer="data_quality",
            trend_decision=None,
            pipeline_state="complete",
            near_miss_reason=None,
            threshold_version_unknown_reason=None,
            usable_for_strategy_stats=True,
            stats_exclusion_reason=None,
            # Shock/LR fields
            volatility_shock_detected=True,
            shock_timeframe="M5",
            shock_candle_time=iso(),
            shock_true_range=0.500,
            shock_atr=0.070,
            shock_atr_multiple=7.14,
            shock_lookback_bars=1,
            shock_direction="down",
            shock_suppression_until=iso(),
            shock_suppression_candles_remaining=3,
            raw_lr_1h=0.002,
            raw_lr_15m=0.003,
            raw_lr_5m=0.001,
            filtered_lr_1h=0.001,
            filtered_lr_15m=0.002,
            filtered_lr_5m=0.0005,
            trend_changed_after_filter=True,
            market_validity_state="invalid",
            market_validity_reason="market_invalid:volatility_shock",
        )
        defaults.update(overrides)
        return EvaluatedOpportunity(**defaults)

    def test_shock_fields_round_trip(self):
        db = temp_db()
        opp = self._make_opportunity()
        recorded = record_opportunity(opp, db)
        assert recorded.volatility_shock_detected is True
        assert recorded.shock_timeframe == "M5"
        assert recorded.shock_atr_multiple == 7.14

        exported = get_opportunities(iso(-1), iso(1), db_path=db)[0]
        assert exported["volatility_shock_detected"] is True
        assert exported["shock_timeframe"] == "M5"
        assert exported["shock_atr_multiple"] == 7.14
        assert exported["shock_suppression_candles_remaining"] == 3

    def test_no_shock_fields_are_persisted_false(self):
        db = temp_db()
        opp = self._make_opportunity(
            volatility_shock_detected=False,
            shock_timeframe=None,
            shock_atr_multiple=None,
            market_validity_state="valid",
            market_validity_reason=None,
        )
        recorded = record_opportunity(opp, db)
        assert recorded.volatility_shock_detected is False
        assert recorded.market_validity_state == "valid"

        exported = get_opportunities(iso(-1), iso(1), db_path=db)[0]
        assert exported["volatility_shock_detected"] is False
        assert exported["market_validity_state"] == "valid"
        assert exported["market_validity_reason"] is None

    def test_raw_and_filtered_lr_round_trip(self):
        db = temp_db()
        opp = self._make_opportunity()
        recorded = record_opportunity(opp, db)
        assert recorded.raw_lr_1h == 0.002
        assert recorded.filtered_lr_1h == 0.001
        assert recorded.trend_changed_after_filter is True

        exported = get_opportunities(iso(-1), iso(1), db_path=db)[0]
        assert exported["raw_lr_1h"] == 0.002
        assert exported["filtered_lr_1h"] == 0.001
        assert exported["trend_changed_after_filter"] is True
        assert exported["raw_lr_5m"] == 0.001
        assert exported["filtered_lr_5m"] == 0.0005


def test_strategy_and_signal_type_counts_are_summarized():
    db = temp_db()
    record_opportunity(
        EvaluatedOpportunity(
            id="continuation",
            evaluated_at=iso(),
            symbol="EURUSD",
            strategy="CTI-v1.1-continuation-test",
            signal_type="continuation",
            final_decision="emitted",
            decision_reason="emitted",
            threshold_version="v1",
        ),
        db,
    )
    record_opportunity(
        EvaluatedOpportunity(
            id="pullback",
            evaluated_at=iso(),
            symbol="EURUSD",
            strategy="CTI-v1.2-pullback",
            signal_type="pullback",
            final_decision="emitted",
            decision_reason="emitted",
            threshold_version="v1",
        ),
        db,
    )

    summary = get_summary(iso(-1), iso(1), db_path=db)

    assert summary["strategy_counts"]["CTI-v1.1-continuation-test"] == 1
    assert summary["strategy_counts"]["CTI-v1.2-pullback"] == 1
    assert summary["signal_type_counts"]["continuation"] == 1
    assert summary["signal_type_counts"]["pullback"] == 1


def test_pullback_summary_counts_outcomes_blockers_and_journal_visibility(tmp_path, monkeypatch):
    db = temp_db()
    journal_file = tmp_path / "signal_journal.jsonl"
    monkeypatch.setattr(journal, "JOURNAL_FILE", journal_file)
    journal_file.write_text(
        "\n".join(
            [
                (
                    '{"signal_id":"journaled-pullback","symbol":"EURUSD","strategy":"CTI-v1.2-pullback",'
                    '"signal_type":"pullback","signal_timestamp":"2026-06-03T12:00:00+00:00"}'
                ),
                (
                    '{"signal_id":"prime","symbol":"EURUSD","strategy":"CTI-v1.2-pullback","signal_type":"pullback",'
                    '"signal_timestamp":"2026-06-03T12:05:00+00:00","prime_suppressed_signal_count":1,'
                    '"prime_suppressed_signal_outcomes":[{"signal_id":"suppressed-pullback","symbol":"EURUSD",'
                    '"strategy":"CTI-v1.2-pullback","signal_type":"pullback","outcome":"invalidated_by_prime"}]}'
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    record_opportunity(
        EvaluatedOpportunity(
            id="pullback-rejected",
            evaluated_at="2026-06-03T12:00:00+00:00",
            symbol="EURUSD",
            strategy="CTI-v1.2-pullback",
            signal_type="pullback",
            final_decision="rejected",
            decision_reason="criteria_failed",
            threshold_version="pullback-v1",
            criteria=[
                CriterionResult(
                    criterion_name="pullback_trigger_candle",
                    layer="signal_stack",
                    measured_value={"body_to_range": 0.72},
                    threshold_value={"max_body_to_range": 0.55},
                    passed=False,
                    required=True,
                    reason="pullback_trigger_candle_failed",
                    context={"pattern": "hammer", "rejection_wick_ratio": 0.18},
                )
            ],
        ),
        db,
    )
    record_opportunity(
        EvaluatedOpportunity(
            id="pullback-emitted",
            evaluated_at="2026-06-03T12:10:00+00:00",
            symbol="EURUSD",
            strategy="CTI-v1.2-pullback",
            signal_type="pullback",
            final_decision="emitted",
            decision_reason="emitted",
            threshold_version="pullback-v1",
            criteria=[
                CriterionResult(
                    criterion_name="pullback_trigger_candle",
                    layer="signal_stack",
                    measured_value={"body_to_range": 0.2},
                    threshold_value={"max_body_to_range": 0.55},
                    passed=True,
                    required=True,
                    context={"pattern": "hammer", "rejection_wick_ratio": 0.72},
                )
            ],
        ),
        db,
    )

    summary = get_summary("2026-06-01", "2026-06-05", db_path=db)

    assert summary["pullback_summary"]["evaluated_count"] == 2
    assert summary["pullback_summary"]["rejected_count"] == 1
    assert summary["pullback_summary"]["near_miss_count"] == 1
    assert summary["pullback_summary"]["emitted_count"] == 1
    assert summary["pullback_summary"]["journaled_count"] == 2
    assert summary["pullback_summary"]["prime_suppressed_count"] == 1
    assert summary["pullback_summary"]["rejected_by_gate"] == {"pullback_trigger_candle_failed": 1}


def test_pullback_opportunity_rows_preserve_context_and_blockers():
    db = temp_db()
    record_opportunity(
        EvaluatedOpportunity(
            id="pullback-context",
            evaluated_at=iso(),
            symbol="EURUSD",
            strategy="CTI-v1.2-pullback",
            signal_type="pullback",
            final_decision="rejected",
            decision_reason="criteria_failed",
            threshold_version="pullback-v2",
            criteria=[
                CriterionResult(
                    criterion_name="pullback_trigger_candle",
                    layer="signal_stack",
                    measured_value={"body_to_range": 0.61},
                    threshold_value={"max_body_to_range": 0.55},
                    passed=False,
                    required=True,
                    reason="pullback_trigger_candle_failed",
                    context={
                        "pattern": "shooting_star",
                        "body_to_range": 0.61,
                        "value_area_relation": "above_midline",
                    },
                )
            ],
        ),
        db,
    )

    row = get_opportunities(iso(-1), iso(1), db_path=db)[0]

    assert row["strategy"] == "CTI-v1.2-pullback"
    assert row["signal_type"] == "pullback"
    assert row["threshold_version"] == "pullback-v2"
    assert row["first_blocker"] == "pullback_trigger_candle_failed"
    assert row["all_blockers"] == ["pullback_trigger_candle_failed"]
    assert row["criteria"][0]["context"]["pattern"] == "shooting_star"
    assert row["criteria"][0]["context"]["value_area_relation"] == "above_midline"


def test_unlinked_db_recreates_schema_on_write():
    import gc
    import time
    db = temp_db()
    opp = EvaluatedOpportunity(
        id="recreation-test",
        evaluated_at=iso(),
        symbol="EURUSD",
        strategy="CTI-v1.2-pullback",
        signal_type="pullback",
        final_decision="emitted",
        decision_reason="emitted",
        threshold_version="pullback-v2",
    )
    # First write initializes db and writes row successfully
    record_opportunity(opp, db)
    assert db.exists()

    # Close the cached connection to release the Windows file lock
    from tradegumi.strategy_metrics import _write_connections_by_db_path
    db_key = str(db.resolve())
    conn = _write_connections_by_db_path.pop(db_key, None)
    if conn is not None:
        conn.close()

    # Force garbage collection to release any remaining SQLite references
    gc.collect()

    # Simulate DB unlinking/deletion (e.g. from a purge) with Windows retry tolerance
    deleted = False
    for _ in range(50):
        try:
            db.unlink()
            deleted = True
            break
        except PermissionError:
            gc.collect()
            time.sleep(0.05)
    
    assert deleted, "Could not delete DB file due to lock"
    assert not db.exists()

    # The second write should automatically detect deletion, recreate schema, and succeed
    record_opportunity(opp, db)
    assert db.exists()

    # Verify the row can be read from the recreated DB
    row = get_opportunities(iso(-1), iso(1), db_path=db)[0]
    assert row["id"] == "recreation-test"

