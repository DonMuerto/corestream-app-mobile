from copy import deepcopy
from datetime import datetime, timezone

import pytest
from sqlalchemy.engine import make_url

from scripts.import_supabase_demo import TABLES, prepare, ticket_values, validate_destination


def snapshot_fixture():
    tables = {t: [] for t in TABLES}
    tables["demo_users"] = [{"id": "u1", "full_name": "Migration fixture", "role": "DEVELOPER",
                            "is_active": True, "specialty": None, "avatar_color_hex": "#4C8DFF"}]
    tables["applications"] = [{"id": "a1", "name": "Migration fixture", "color_hex": "#4C8DFF"}]
    tables["epics"] = [{"id": "e1", "name": "Migration fixture", "order_index": 0, "application_id": "a1"}]
    ticket = dict(id="t1", title="Migration fixture", description="", number=1, epic_id="e1",
                  status="IN_PROGRESS", priority="HIGH", assignee_id="u1", created_by_id="u1",
                  due_date=None, pr_link=None, spent_seconds=42, blocked_seconds=5,
                  running_since="2026-09-01T00:00:00+00:00", blocked_since=None, deleted_at=None)
    tables["tickets"] = [ticket, dict(ticket, id="t2", number=2, deleted_at="2026-09-02T00:00:00+00:00")]
    tables["ticket_events"] = [dict(id=1, ticket_id="t1", type="CREATED", user_id="u1", to_user_id=None,
                                    text=None, from_status=None, to_status=None, created_at="2026-09-01T00:00:00+00:00"),
                               dict(id=2, ticket_id="t2", type="DELETED", user_id="u1", to_user_id=None,
                                    text=None, from_status=None, to_status=None, created_at="2026-09-02T00:00:00+00:00")]
    return {"source_project": "frxqettffjbnuncugtuu", "exported_at": "2026-10-06T00:00:00+00:00", "tables": tables}


def test_archive_not_resurrected_and_uuid_v4_mapping():
    tables, _, mapping, plan, _ = prepare(snapshot_fixture())
    assert sum(map(len, tables.values())) == len(plan) == len(mapping)
    assert all(value.version == 4 for value in mapping.values())
    assert plan[("tickets", "t1")] == "tickets"
    assert plan[("tickets", "t2")] is None
    assert plan[("ticket_events", "2")] is None


def test_dangling_reference_rejected():
    snapshot = snapshot_fixture()
    snapshot["tables"]["tickets"][0]["assignee_id"] = "unknown"
    with pytest.raises(ValueError, match="Dangling"):
        prepare(snapshot)


def test_missing_table_and_duplicate_identity_rejected():
    snapshot = snapshot_fixture()
    del snapshot["tables"]["demo_notifications"]
    with pytest.raises(ValueError, match="every expected"):
        prepare(snapshot)
    snapshot = snapshot_fixture()
    snapshot["tables"]["demo_users"].append(deepcopy(snapshot["tables"]["demo_users"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        prepare(snapshot)


def test_import_pauses_timer_without_inventing_work():
    row = snapshot_fixture()["tables"]["tickets"][0]
    values = ticket_values(row, [], datetime.now(timezone.utc))
    assert values["time_spent_seconds"] == 42
    assert values["blocked_time_seconds"] == 5
    assert values["timer_started_at"] is None


def test_question_and_completion_mapping():
    row = snapshot_fixture()["tables"]["tickets"][0]
    row["status"] = "BLOCKED"
    now = datetime.now(timezone.utc)
    event = {"type": "QUESTION", "text": "Question preserved", "created_at": now.isoformat()}
    assert ticket_values(row, [event], now)["blocked_question"] == "Question preserved"
    assert ticket_values(row, [event], now)["status"] == "BLOCKED_QUESTION"
    row["status"] = "DONE"
    event["type"] = "COMPLETED"
    assert ticket_values(row, [event], now)["completed_at"] == now


def test_changed_data_changes_digest():
    snapshot = snapshot_fixture()
    digest = prepare(snapshot)[-1]
    snapshot["tables"]["tickets"][0]["spent_seconds"] += 1
    assert prepare(snapshot)[-1] != digest


def test_destination_guard():
    validate_destination(make_url("postgresql://u:p@project.neon.tech/db"), True)
    with pytest.raises(ValueError, match="restricted"):
        validate_destination(make_url("postgresql://u:p@localhost/corestream"), True)
