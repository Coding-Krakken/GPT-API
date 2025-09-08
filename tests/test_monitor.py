import pytest
import json

class TestMonitorEndpoints:
    """Test suite for /monitor endpoint operations."""

    def test_monitor_health_check(self, client, auth_headers):
        """Test monitor health check endpoint."""
        response = client.get("/monitor/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"] == "Monitor endpoint is live."

    def test_monitor_cpu(self, client, auth_headers):
        """Test CPU monitoring."""
        payload = {
            "type": "cpu"
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        cpu_percent = float(data["result"])
        assert isinstance(cpu_percent, float)
        assert 0 <= cpu_percent <= 100

    def test_monitor_memory(self, client, auth_headers):
        """Test memory monitoring."""
        payload = {
            "type": "memory"
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

        # Parse the JSON string result
        memory_data = json.loads(data["result"])
        assert "total_gb" in memory_data
        assert "used_gb" in memory_data
        assert "percent" in memory_data

        assert isinstance(memory_data["total_gb"], (int, float))
        assert isinstance(memory_data["used_gb"], (int, float))
        assert isinstance(memory_data["percent"], (int, float))

        assert memory_data["total_gb"] > 0
        assert memory_data["used_gb"] >= 0
        assert 0 <= memory_data["percent"] <= 100
        assert memory_data["used_gb"] <= memory_data["total_gb"]

    def test_monitor_disk(self, client, auth_headers):
        """Test disk monitoring."""
        payload = {
            "type": "disk"
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

        # Parse the JSON string result
        disk_data = json.loads(data["result"])
        assert "total_gb" in disk_data
        assert "used_gb" in disk_data
        assert "percent" in disk_data

        assert isinstance(disk_data["total_gb"], (int, float))
        assert isinstance(disk_data["used_gb"], (int, float))
        assert isinstance(disk_data["percent"], (int, float))

        assert disk_data["total_gb"] > 0
        assert disk_data["used_gb"] >= 0
        assert 0 <= disk_data["percent"] <= 100
        assert disk_data["used_gb"] <= disk_data["total_gb"]

    def test_monitor_network(self, client, auth_headers):
        """Test network monitoring."""
        payload = {
            "type": "network"
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

        # Parse the JSON string result
        network_data = json.loads(data["result"])
        assert "bytes_sent" in network_data
        assert "bytes_recv" in network_data

        assert isinstance(network_data["bytes_sent"], int)
        assert isinstance(network_data["bytes_recv"], int)

        assert network_data["bytes_sent"] >= 0
        assert network_data["bytes_recv"] >= 0

    def test_monitor_performance(self, client, auth_headers):
        """Test performance monitoring."""
        payload = {
            "type": "performance"
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

        # Parse the JSON string result
        perf_data = json.loads(data["result"])
        assert "cpu_percent" in perf_data
        assert "memory_percent" in perf_data
        assert "disk_percent" in perf_data

        assert isinstance(perf_data["cpu_percent"], (int, float))
        assert isinstance(perf_data["memory_percent"], (int, float))
        assert isinstance(perf_data["disk_percent"], (int, float))

        assert 0 <= perf_data["cpu_percent"] <= 100
        assert 0 <= perf_data["memory_percent"] <= 100
        assert 0 <= perf_data["disk_percent"] <= 100

    def test_monitor_filesystem(self, client, auth_headers):
        """Test filesystem monitoring."""
        payload = {
            "type": "filesystem"
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data

        # Parse the JSON string result
        fs_data = json.loads(data["result"])

        # Should have at least root filesystem
        assert "/" in fs_data or "C:" in fs_data or len(fs_data) > 0

        # Check structure of first filesystem
        first_fs = list(fs_data.keys())[0]
        fs_info = fs_data[first_fs]

        if fs_info != "unavailable":
            assert "total_gb" in fs_info
            assert "used_gb" in fs_info
            assert "percent" in fs_info

            assert isinstance(fs_info["total_gb"], (int, float))
            assert isinstance(fs_info["used_gb"], (int, float))
            assert isinstance(fs_info["percent"], (int, float))

    def test_monitor_logs_not_implemented(self, client, auth_headers):
        """Test logs monitoring (not implemented)."""
        payload = {
            "type": "logs"
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "Log stream not yet implemented" in data["result"]

    def test_monitor_custom_not_implemented(self, client, auth_headers):
        """Test custom monitoring (not implemented)."""
        payload = {
            "type": "custom"
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "Custom monitoring not implemented" in data["result"]

    def test_monitor_live_mode(self, client, auth_headers):
        """Test live monitoring mode."""
        payload = {
            "type": "cpu",
            "live": True
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "Live cpu monitoring not implemented" in data["result"]

    def test_monitor_unknown_type(self, client, auth_headers):
        """Test unknown monitor type."""
        payload = {
            "type": "unknown_type"
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert "Unknown monitor type" in data["error"]

    def test_monitor_default_type(self, client, auth_headers):
        """Test default monitor type (cpu)."""
        payload = {}  # No type specified
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        # Should default to cpu
        cpu_percent = float(data["result"])
        assert isinstance(cpu_percent, float)
        assert 0 <= cpu_percent <= 100

    def test_monitor_case_insensitive_type(self, client, auth_headers):
        """Test case insensitive monitor types."""
        payload = {
            "type": "CPU"  # Uppercase
        }
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        cpu_percent = float(data["result"])
        assert isinstance(cpu_percent, float)
        assert 0 <= cpu_percent <= 100

    def test_monitor_data_consistency(self, client, auth_headers):
        """Test that monitor data is consistent and reasonable."""
        # Test CPU monitoring multiple times
        cpu_values = []
        for _ in range(3):
            payload = {"type": "cpu"}
            response = client.post("/monitor", headers=auth_headers, json=payload)
            assert response.status_code == 200
            data = response.json()
            cpu_percent = float(data["result"])
            cpu_values.append(cpu_percent)
            assert 0 <= cpu_percent <= 100

        # CPU values should be similar (not wildly different)
        if len(cpu_values) > 1:
            max_diff = max(cpu_values) - min(cpu_values)
            assert max_diff < 50  # Allow some variation but not extreme

    def test_monitor_memory_consistency(self, client, auth_headers):
        """Test memory monitoring consistency."""
        payload = {"type": "memory"}
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()

        memory_data = json.loads(data["result"])

        # Memory usage should be consistent with expectations
        assert memory_data["total_gb"] > 0
        assert memory_data["used_gb"] <= memory_data["total_gb"]
        assert abs(memory_data["used_gb"] / memory_data["total_gb"] * 100 - memory_data["percent"]) < 1

    def test_monitor_disk_consistency(self, client, auth_headers):
        """Test disk monitoring consistency."""
        payload = {"type": "disk"}
        response = client.post("/monitor", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()

        disk_data = json.loads(data["result"])

        # Disk usage should be consistent
        assert disk_data["total_gb"] > 0
        assert disk_data["used_gb"] <= disk_data["total_gb"]
        assert abs(disk_data["used_gb"] / disk_data["total_gb"] * 100 - disk_data["percent"]) < 1

    def test_monitor_network_increasing(self, client, auth_headers):
        """Test that network counters are non-decreasing."""
        payload = {"type": "network"}

        # Get first reading
        response1 = client.post("/monitor", headers=auth_headers, json=payload)
        assert response1.status_code == 200
        data1 = response1.json()
        network_data1 = json.loads(data1["result"])

        # Get second reading
        response2 = client.post("/monitor", headers=auth_headers, json=payload)
        assert response2.status_code == 200
        data2 = response2.json()
        network_data2 = json.loads(data2["result"])

        # Network counters should not decrease
        assert network_data2["bytes_sent"] >= network_data1["bytes_sent"]
        assert network_data2["bytes_recv"] >= network_data1["bytes_recv"]