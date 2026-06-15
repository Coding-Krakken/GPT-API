from pathlib import Path

from scripts import ticket_index


ROOT = Path(__file__).resolve().parents[1]


def test_ticket_index_exists_and_tracks_imported_tickets():
    index = ROOT / "maintenance" / "TICKET_INDEX.md"
    ticket_dir = ROOT / "maintenance" / "tickets"
    assert ticket_dir.is_dir()
    assert index.exists()
    text = index.read_text(encoding="utf-8")
    assert "# Maintainer Ticket Index" in text
    assert "| Area | Severity | Status | ID | Title | File |" in text
    assert len(list(ticket_dir.glob("*.md"))) >= 1


def test_ticket_files_have_front_matter():
    tickets = list((ROOT / "maintenance" / "tickets").glob("*.md"))
    assert tickets
    sample = tickets[:10]
    for path in sample:
        text = path.read_text(encoding="utf-8", errors="replace")
        assert text.startswith("---\n"), path
        meta = ticket_index.parse_front_matter(text)
        assert meta.get("id"), path
        assert meta.get("status") in {"open", "in_progress", "fixed", "wontfix", "duplicate", "stale"}, path
        assert meta.get("severity") in {"low", "medium", "high", "critical"}, path
        assert meta.get("area"), path


def test_ticket_index_generator_is_idempotent():
    assert ticket_index.main() == 0
    index = ROOT / "maintenance" / "TICKET_INDEX.md"
    text = index.read_text(encoding="utf-8")
    assert "Ticket count:" in text
