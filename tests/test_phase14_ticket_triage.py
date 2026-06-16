from pathlib import Path

from scripts import ticket_index


ROOT = Path(__file__).resolve().parents[1]
VALID_STATUSES = {"open", "in_progress", "needs_verification", "resolved", "obsolete", "duplicate", "wontfix"}
CLOSED_STATUSES = {"resolved", "obsolete", "duplicate", "wontfix"}


def test_ticket_index_exists_and_reports_lifecycle_summary():
    index = ROOT / "maintenance" / "TICKET_INDEX.md"
    ticket_dir = ROOT / "maintenance" / "tickets"
    assert ticket_dir.is_dir()
    assert index.exists()
    text = index.read_text(encoding="utf-8")
    assert "# Maintainer Ticket Index" in text
    assert "Active count:" in text
    assert "Closed count:" in text
    assert "Invalid metadata count: 0" in text
    assert "## Active ticket detail" in text
    assert "## Closed / historical ticket detail" in text
    assert len(list(ticket_dir.glob("*.md"))) >= 1


def test_all_ticket_files_have_lifecycle_front_matter():
    tickets = list((ROOT / "maintenance" / "tickets").glob("*.md"))
    assert tickets
    for path in tickets:
        text = path.read_text(encoding="utf-8", errors="replace")
        assert text.startswith("---\n"), path
        meta = ticket_index.parse_front_matter(text)
        assert meta.get("id") == path.stem, path
        assert meta.get("status") in VALID_STATUSES, path
        assert meta.get("severity") in {"low", "medium", "high", "critical"}, path
        assert meta.get("area"), path
        assert meta.get("created"), path
        assert "resolved_at" in meta, path
        assert "resolved_by_commit" in meta, path
        assert meta.get("verification_command") is not None, path
        assert meta.get("verification_result") is not None, path
        assert meta.get("resolution_summary") is not None, path
        if meta.get("status") in CLOSED_STATUSES:
            assert meta.get("resolved_at"), path
            assert meta.get("resolution_summary"), path


def test_ticket_index_generator_is_idempotent_and_validates_metadata():
    assert ticket_index.main() == 0
    index = ROOT / "maintenance" / "TICKET_INDEX.md"
    text = index.read_text(encoding="utf-8")
    assert "Ticket count:" in text
    assert "Invalid metadata count: 0" in text


def test_ticket_rows_include_active_and_closed_backlog():
    rows = ticket_index.ticket_rows()
    assert rows
    statuses = {row["status"] for row in rows}
    assert statuses & {"open", "needs_verification"}
    assert statuses & CLOSED_STATUSES
    active = [row for row in rows if row["status"] in ticket_index.ACTIVE_STATUSES]
    assert active
    assert any(row["area"] == "codeops" for row in rows)
    assert any(row["status"] in CLOSED_STATUSES for row in rows)
    assert all(not row["validation_errors"] for row in rows)
