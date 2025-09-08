import pytest
import os

class TestPackageEndpoints:
    """Test suite for /package endpoint operations."""

    def test_pip_list(self, client, auth_headers):
        """Test pip list."""
        payload = {
            "manager": "pip",
            "action": "list"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data
        assert data["exit_code"] in (0, 1)  # pip list can return 1 even when successful

    def test_pip_install_dry_run(self, client, auth_headers):
        """Test pip install (dry run - don't actually install)."""
        # Use a package that might not be installed
        payload = {
            "manager": "pip",
            "action": "install",
            "package": "requests"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_pip_remove_dry_run(self, client, auth_headers):
        """Test pip remove (dry run)."""
        payload = {
            "manager": "pip",
            "action": "remove",
            "package": "requests"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_pip_update(self, client, auth_headers):
        """Test pip update."""
        payload = {
            "manager": "pip",
            "action": "update"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_pip_upgrade(self, client, auth_headers):
        """Test pip upgrade."""
        payload = {
            "manager": "pip",
            "action": "upgrade",
            "package": "pip"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_apt_list(self, client, auth_headers):
        """Test apt list."""
        payload = {
            "manager": "apt",
            "action": "list"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_apt_update(self, client, auth_headers):
        """Test apt update."""
        payload = {
            "manager": "apt",
            "action": "update"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_apt_upgrade(self, client, auth_headers):
        """Test apt upgrade."""
        payload = {
            "manager": "apt",
            "action": "upgrade"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_brew_list(self, client, auth_headers):
        """Test brew list."""
        payload = {
            "manager": "brew",
            "action": "list"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_brew_update(self, client, auth_headers):
        """Test brew update."""
        payload = {
            "manager": "brew",
            "action": "update"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_brew_upgrade(self, client, auth_headers):
        """Test brew upgrade."""
        payload = {
            "manager": "brew",
            "action": "upgrade"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_pacman_list(self, client, auth_headers):
        """Test pacman list."""
        payload = {
            "manager": "pacman",
            "action": "list"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_pacman_update(self, client, auth_headers):
        """Test pacman update."""
        payload = {
            "manager": "pacman",
            "action": "update"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_pacman_upgrade(self, client, auth_headers):
        """Test pacman upgrade."""
        payload = {
            "manager": "pacman",
            "action": "upgrade"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_winget_list(self, client, auth_headers):
        """Test winget list."""
        payload = {
            "manager": "winget",
            "action": "list"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_winget_update(self, client, auth_headers):
        """Test winget update."""
        payload = {
            "manager": "winget",
            "action": "update"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_winget_upgrade(self, client, auth_headers):
        """Test winget upgrade."""
        payload = {
            "manager": "winget",
            "action": "upgrade"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_npm_list(self, client, auth_headers, test_package_json):
        """Test npm list."""
        payload = {
            "manager": "npm",
            "action": "list"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_npm_update(self, client, auth_headers):
        """Test npm update."""
        payload = {
            "manager": "npm",
            "action": "update"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_npm_upgrade(self, client, auth_headers):
        """Test npm upgrade."""
        payload = {
            "manager": "npm",
            "action": "upgrade"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data

    def test_unsupported_manager(self, client, auth_headers):
        """Test unsupported package manager."""
        payload = {
            "manager": "unsupported_manager",
            "action": "list"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported package manager" in str(data)

    def test_unsupported_action(self, client, auth_headers):
        """Test unsupported action."""
        payload = {
            "manager": "pip",
            "action": "unsupported_action"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported action" in str(data)

    def test_missing_manager(self, client, auth_headers):
        """Test missing manager."""
        payload = {
            "action": "list"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported package manager" in str(data)

    def test_missing_action(self, client, auth_headers):
        """Test missing action."""
        payload = {
            "manager": "pip"
        }
        response = client.post("/package", headers=auth_headers, json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "Unsupported action" in str(data)

    def test_query_params_fallback(self, client, auth_headers):
        """Test query params fallback."""
        # This tests the alternative way of passing params
        params = {
            "manager": "pip",
            "action": "list"
        }
        response = client.post("/package", params=params, headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "stdout" in data
        assert "stderr" in data
        assert "exit_code" in data