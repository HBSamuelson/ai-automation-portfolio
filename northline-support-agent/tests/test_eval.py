from support_agent.eval import format_report, run_eval


def test_eval_matches_labels_and_published_counts():
    report = run_eval()
    assert report.label_matches == report.cases, format_report(report)
    assert report.cases == 22
    assert report.resolved == 14
    assert report.escalated == 8
    assert report.returns_created == 2
    assert report.tickets_opened == 8
    assert report.high_priority_tickets == 2
    text = format_report(report)
    assert text.startswith("Northline support eval\n")
    assert "resolution_rate: 63.6%" in text
    assert "escalation_rate: 36.4%" in text
    assert "label_accuracy: 100.0%" in text
    assert "as_of: 2026-10-07" in text
