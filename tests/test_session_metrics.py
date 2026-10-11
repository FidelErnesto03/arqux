from arqux.session_metrics import SessionLatencyRecorder


def test_latency_report_exposes_slos_and_violations():
    recorder = SessionLatencyRecorder({"speech_end_to_bus_submit": 300.0})
    recorder.mark("turn-1", "speech_end", 10.0)
    recorder.mark("turn-1", "bus_submit", 10.1)
    report = recorder.report("turn-1")

    assert report["durations_ms"]["speech_end_to_bus_submit"] == 100.0
    assert report["violations"] == []
    assert report["budgets_ms"]["speech_end_to_bus_submit"] == 300.0


def test_latency_report_flags_budget_overrun():
    recorder = SessionLatencyRecorder({"barge_in_cancel": 200.0})
    recorder.mark("turn-2", "barge_in", 1.0)
    recorder.mark("turn-2", "cancelled", 1.3)

    assert recorder.report("turn-2")["violations"] == ["barge_in_cancel"]
