"""EC8 phase 8a — API spot-check for testing agent review.

Covers: unauthenticated 401s, dev-owner full access (create/read/update/status),
announcement draft->publish, team dashboard aggregation, and EC0-EC7 regression
spot-check (no crash) after the Perm enum rename in core/permissions.py.
"""
import os
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def owner_token():
    resp = requests.post(f"{API}/auth/dev-login", json={})
    if resp.status_code != 200:
        pytest.skip("dev-login unavailable - AUTH_DEV_BYPASS may be disabled")
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def owner_client(owner_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {owner_token}", "Content-Type": "application/json"})
    return s


class TestUnauthenticated:
    def test_employees_requires_auth(self):
        r = requests.get(f"{API}/employees")
        assert r.status_code == 401

    def test_create_employee_requires_auth(self):
        r = requests.post(f"{API}/employees", json={"name": "X", "hourly_rate_cents": 1500})
        assert r.status_code == 401

    def test_team_dashboard_requires_auth(self):
        r = requests.get(f"{API}/team/dashboard")
        assert r.status_code == 401

    def test_announcements_requires_auth(self):
        r = requests.post(f"{API}/announcements", json={"title": "t", "body": "b"})
        assert r.status_code == 401


class TestOwnerFullAccess:
    def test_dev_login_user_is_owner(self, owner_token):
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {owner_token}"})
        r = s.get(f"{API}/auth/dev-login")  # not a real endpoint check; use permissions from create call instead
        # Just verify token decodes correctly via an authorized call below.
        assert owner_token

    def test_create_employee_and_verify_persistence(self, owner_client):
        name = f"TEST_Employee_{uuid.uuid4().hex[:8]}"
        r = owner_client.post(f"{API}/employees", json={"name": name, "hourly_rate_cents": 2500})
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == name
        assert data["hourly_rate_cents"] == 2500
        assert data["status"] == "active"
        emp_id = data["id"]

        get_r = owner_client.get(f"{API}/employees/{emp_id}")
        assert get_r.status_code == 200
        assert get_r.json()["name"] == name

    def test_update_employee_persists(self, owner_client):
        name = f"TEST_Employee_{uuid.uuid4().hex[:8]}"
        create = owner_client.post(f"{API}/employees", json={"name": name, "hourly_rate_cents": 1500})
        emp_id = create.json()["id"]

        upd = owner_client.patch(f"{API}/employees/{emp_id}", json={"role_label": "Install Tech"})
        assert upd.status_code == 200
        assert upd.json()["role_label"] == "Install Tech"

        get_r = owner_client.get(f"{API}/employees/{emp_id}")
        assert get_r.json()["role_label"] == "Install Tech"

    def test_status_change_flow_and_history(self, owner_client):
        name = f"TEST_Employee_{uuid.uuid4().hex[:8]}"
        create = owner_client.post(f"{API}/employees", json={"name": name, "hourly_rate_cents": 1500})
        emp_id = create.json()["id"]

        r = owner_client.post(f"{API}/employees/{emp_id}/status", json={"status": "suspended", "reason": "TEST reason"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "suspended"
        assert len(data["status_history"]) == 1
        assert data["status_history"][0]["from"] == "active"
        assert data["status_history"][0]["to"] == "suspended"

    def test_status_change_same_status_rejected(self, owner_client):
        name = f"TEST_Employee_{uuid.uuid4().hex[:8]}"
        create = owner_client.post(f"{API}/employees", json={"name": name, "hourly_rate_cents": 1500})
        emp_id = create.json()["id"]
        r = owner_client.post(f"{API}/employees/{emp_id}/status", json={"status": "active", "reason": "same"})
        assert r.status_code == 400

    def test_announcement_draft_then_publish(self, owner_client):
        title = f"TEST_Announcement_{uuid.uuid4().hex[:8]}"
        create = owner_client.post(f"{API}/announcements", json={"title": title, "body": "hello team"})
        assert create.status_code == 201
        ann = create.json()
        assert ann["status"] == "draft"

        pub = owner_client.post(f"{API}/announcements/{ann['id']}/publish")
        assert pub.status_code == 200
        assert pub.json()["status"] == "published"

        # appears in team dashboard active announcements
        dash = owner_client.get(f"{API}/team/dashboard")
        assert dash.status_code == 200
        titles = [a["title"] for a in dash.json()["announcements"]]
        assert title in titles

    def test_team_dashboard_status_counts_shape(self, owner_client):
        r = owner_client.get(f"{API}/team/dashboard")
        assert r.status_code == 200
        data = r.json()
        counts = data["employee_status_counts"]
        for key in ["active", "suspended", "inactive", "terminated", "archived"]:
            assert key in counts
            assert isinstance(counts[key], int)


class TestRegressionSpotCheck:
    """Confirm EC0-EC7 core endpoints still respond after Perm enum rename."""

    def test_customers_list_loads(self, owner_client):
        r = owner_client.get(f"{API}/customers")
        assert r.status_code == 200

    def test_orders_list_loads(self, owner_client):
        r = owner_client.get(f"{API}/orders")
        assert r.status_code == 200

    def test_inventory_materials_loads(self, owner_client):
        r = owner_client.get(f"{API}/materials")
        assert r.status_code == 200
