# Copyright (c) 2016-2026 Association of Universities for Research in Astronomy, Inc. (AURA)
# For license information see LICENSE or https://opensource.org/licenses/BSD-3-Clause

from fastapi.testclient import TestClient

from scheduler.orchestration.process_manager import ProcessManager


def test_get_operation_id_is_none_when_unset():
    pm = ProcessManager()
    assert pm.get_operation_id() is None


def test_get_operation_id_returns_the_operation_process_id():
    pm = ProcessManager()
    pm.operation_process_id = "operation"
    assert pm.get_operation_id() == "operation"


def test_get_operation_id_endpoint(monkeypatch):
    """GET /get_operation_id answers 200 with the id, or null when no
    operation process is running — never a 500."""
    from scheduler.app import app
    from scheduler.orchestration.process_manager import process_manager

    # No context manager: lifespan (DB init, process manager start) must not run.
    client = TestClient(app)

    monkeypatch.setattr(process_manager, "operation_process_id", None)
    response = client.get("/get_operation_id")
    assert response.status_code == 200
    assert response.json() == {"message": None}

    monkeypatch.setattr(process_manager, "operation_process_id", "operation")
    response = client.get("/get_operation_id")
    assert response.status_code == 200
    assert response.json() == {"message": "operation"}
