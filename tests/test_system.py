import pytest
import platform
import socket
import psutil
import os

class TestSystemEndpoints:
    """Test suite for /system endpoint operations."""

    def test_get_system_info(self, client, auth_headers):
        """Test getting system information."""
        response = client.get("/system/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Check that all expected fields are present
        expected_fields = [
            "os", "platform", "hostname", "architecture", "cpu",
            "cpu_cores", "cpu_threads", "cpu_usage_percent",
            "memory_total_gb", "memory_usage_percent", "disk_usage_percent",
            "uptime_seconds", "current_user"
        ]

        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

        # Validate some field values
        assert data["os"] == platform.system()
        assert data["hostname"] == socket.gethostname()
        assert isinstance(data["cpu_cores"], int)
        assert isinstance(data["cpu_threads"], int)
        assert isinstance(data["cpu_usage_percent"], (int, float))
        assert 0 <= data["cpu_usage_percent"] <= 100
        assert isinstance(data["memory_total_gb"], (int, float))
        assert data["memory_total_gb"] > 0
        assert isinstance(data["memory_usage_percent"], (int, float))
        assert 0 <= data["memory_usage_percent"] <= 100
        assert isinstance(data["disk_usage_percent"], (int, float))
        assert 0 <= data["disk_usage_percent"] <= 100
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] > 0
        assert isinstance(data["current_user"], str)
        assert len(data["current_user"]) > 0

    def test_system_info_data_types(self, client, auth_headers):
        """Test that system info returns correct data types."""
        response = client.get("/system/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Check data types
        assert isinstance(data["os"], str)
        assert isinstance(data["platform"], str)
        assert isinstance(data["hostname"], str)
        assert isinstance(data["architecture"], str)
        assert isinstance(data["cpu"], str)
        assert isinstance(data["cpu_cores"], int)
        assert isinstance(data["cpu_threads"], int)
        assert isinstance(data["cpu_usage_percent"], (int, float))
        assert isinstance(data["memory_total_gb"], (int, float))
        assert isinstance(data["memory_usage_percent"], (int, float))
        assert isinstance(data["disk_usage_percent"], (int, float))
        assert isinstance(data["uptime_seconds"], (int, float))
        assert isinstance(data["current_user"], str)

    def test_system_info_values_reasonable(self, client, auth_headers):
        """Test that system info values are within reasonable ranges."""
        response = client.get("/system/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Check reasonable value ranges
        assert data["cpu_cores"] > 0
        assert data["cpu_threads"] >= data["cpu_cores"]
        assert 0 <= data["cpu_usage_percent"] <= 100
        assert data["memory_total_gb"] > 0  # At least some memory
        assert 0 <= data["memory_usage_percent"] <= 100
        assert 0 <= data["disk_usage_percent"] <= 100
        assert data["uptime_seconds"] >= 0  # Could be 0 if system just started

    def test_system_info_consistency(self, client, auth_headers):
        """Test that system info is consistent across multiple calls."""
        response1 = client.get("/system/", headers=auth_headers)
        response2 = client.get("/system/", headers=auth_headers)

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Static values should be identical
        static_fields = ["os", "platform", "hostname", "architecture", "cpu", "cpu_cores", "cpu_threads", "memory_total_gb"]
        for field in static_fields:
            assert data1[field] == data2[field], f"Field {field} changed between calls"

        # Dynamic values should be reasonable (not necessarily identical)
        dynamic_fields = ["cpu_usage_percent", "memory_usage_percent", "disk_usage_percent", "uptime_seconds"]
        for field in dynamic_fields:
            assert isinstance(data2[field], type(data1[field]))
            if field.endswith("_percent"):
                assert 0 <= data2[field] <= 100
            elif field == "uptime_seconds":
                assert data2[field] >= data1[field]  # Uptime should not decrease

    def test_system_info_platform_specific(self, client, auth_headers):
        """Test platform-specific system information."""
        response = client.get("/system/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        current_platform = platform.system()

        if current_platform == "Linux":
            assert "Linux" in data["platform"]
        elif current_platform == "Darwin":
            assert "macOS" in data["platform"] or "Darwin" in data["platform"]
        elif current_platform == "Windows":
            assert "Windows" in data["platform"]

        # Check that CPU info is available
        assert len(data["cpu"]) > 0

        # Check that architecture is reasonable
        valid_architectures = ["x86_64", "amd64", "arm64", "aarch64", "i386", "i686"]
        assert data["architecture"] in valid_architectures or len(data["architecture"]) > 0

    def test_system_info_user_info(self, client, auth_headers):
        """Test user information in system info."""
        response = client.get("/system/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Check current user
        current_user = data["current_user"]
        assert isinstance(current_user, str)
        assert len(current_user) > 0

        # On Unix-like systems, user should not be root for safety
        if os.name != "nt":  # Not Windows
            assert current_user != "root", "System should not be running as root"

    def test_system_info_memory_info(self, client, auth_headers):
        """Test memory information specifically."""
        response = client.get("/system/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Get actual memory info for comparison
        actual_memory = psutil.virtual_memory()

        # Check memory total (should be close to actual)
        reported_total_gb = data["memory_total_gb"]
        actual_total_gb = actual_memory.total / (1024**3)

        # Allow some tolerance for rounding differences
        assert abs(reported_total_gb - actual_total_gb) < 1.0

        # Check memory usage percentage
        reported_percent = data["memory_usage_percent"]
        actual_percent = actual_memory.percent

        # Should be very close
        assert abs(reported_percent - actual_percent) < 1.0

    def test_system_info_disk_info(self, client, auth_headers):
        """Test disk usage information."""
        response = client.get("/system/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Get actual disk info for comparison
        actual_disk = psutil.disk_usage("/")

        reported_percent = data["disk_usage_percent"]
        actual_percent = actual_disk.percent

        # Should be very close
        assert abs(reported_percent - actual_percent) < 1.0

    def test_system_info_cpu_info(self, client, auth_headers):
        """Test CPU information."""
        response = client.get("/system/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Check CPU cores
        assert data["cpu_cores"] == psutil.cpu_count(logical=False)
        assert data["cpu_threads"] == psutil.cpu_count(logical=True)

        # Check CPU usage (should be a valid percentage)
        cpu_percent = data["cpu_usage_percent"]
        assert isinstance(cpu_percent, (int, float))
        assert 0 <= cpu_percent <= 100

    def test_system_info_uptime(self, client, auth_headers):
        """Test system uptime information."""
        response = client.get("/system/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        uptime = data["uptime_seconds"]
        assert isinstance(uptime, (int, float))
        assert uptime >= 0

        # Uptime from psutil
        actual_uptime = psutil.boot_time()
        current_time = data.get("current_time", None)  # If available

        # Basic sanity check
        import time
        current_time = time.time()
        calculated_uptime = current_time - psutil.boot_time()
        assert abs(uptime - calculated_uptime) < 10  # Within 10 seconds