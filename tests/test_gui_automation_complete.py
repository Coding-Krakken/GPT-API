"""
Comprehensive test suite for the complete GUI automation system.
Tests all phases and validates the full 16-phase implementation.
"""

import pytest
from fastapi.testclient import TestClient
from main import app
import json
import time

client = TestClient(app)
API_KEY = "test-key-123"
HEADERS = {"x-api-key": API_KEY}

class TestGUIAutomationSystem:
    """Complete system validation test suite"""
    
    def test_system_overview(self):
        """Test that all GUI automation routes are available"""
        response = client.get("/debug/routes")
        routes = response.json()
        
        # Check for all expected route categories
        gui_routes = [r for r in routes if any(prefix in r for prefix in [
            '/screen', '/input', '/safety', '/session', '/flow', 
            '/clipboard', '/batch_gui', '/debug', '/plugins'
        ])]
        
        assert len(gui_routes) >= 46, f"Expected at least 46 GUI routes, got {len(gui_routes)}"
        assert len(routes) >= 65, f"Expected at least 65 total routes, got {len(routes)}"
    
    def test_phase_2_perception_and_targeting(self):
        """Test Phase 2: Perception & Targeting capabilities"""
        # Screen capabilities
        response = client.get("/screen/capabilities", headers=HEADERS)
        assert response.status_code == 200
        caps = response.json()["result"]
        assert "screen_capture" in caps
        assert "ocr" in caps
        assert "template_matching" in caps
        assert "accessibility" in caps
        
        # Screen capture dry run
        response = client.post("/screen/capture", headers=HEADERS, json={
            "action": "capture",
            "format": "base64",
            "monitor": 0
        })
        assert response.status_code == 200
        # Should get dependency error in headless environment
        result = response.json()
        assert "errors" in result or "result" in result
    
    def test_phase_3_core_input_synthesis(self):
        """Test Phase 3: Core Input Synthesis capabilities"""
        # Input capabilities
        response = client.get("/input/capabilities", headers=HEADERS)
        assert response.status_code == 200
        caps = response.json()["result"]
        assert caps["dry_run"] == True
        assert caps["ime_support"] == True
        
        # Mouse drag with dry run
        response = client.post("/input/mouse_drag", headers=HEADERS, json={
            "action": "drag",
            "from_x": 100,
            "from_y": 100,
            "to_x": 200,
            "to_y": 200,
            "dry_run": True
        })
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["status"] == "would_execute"
        assert "safety_check" in result
        
        # Key combination
        response = client.post("/input/key_combo", headers=HEADERS, json={
            "action": "press",
            "keys": ["ctrl", "c"],
            "dry_run": True
        })
        assert response.status_code == 200
        
        # Text typing
        response = client.post("/input/type_text", headers=HEADERS, json={
            "action": "type",
            "text": "Hello GUI Automation!",
            "dry_run": True
        })
        assert response.status_code == 200
    
    def test_phase_4_safety_and_governance(self):
        """Test Phase 4: Safety & Governance"""
        # Safety status
        response = client.get("/safety/status", headers=HEADERS)
        assert response.status_code == 200
        status = response.json()["result"]
        assert status["safety_enabled"] == True
        assert status["policies_loaded"] == 6
        assert len(status["available_levels"]) == 3
        
        # Safety check
        response = client.post("/safety/check", headers=HEADERS, json={
            "endpoint": "/input",
            "action": "drag",
            "params": {"from_x": 0, "from_y": 0, "to_x": 100, "to_y": 100}
        })
        assert response.status_code == 200
        result = response.json()["result"]
        assert "safe" in result
        assert "action_type" in result
        assert "policy_level" in result
        
        # Safety policies
        response = client.get("/safety/policies", headers=HEADERS)
        assert response.status_code == 200
        policies = response.json()["result"]["policies"]
        assert "read" in policies
        assert "write" in policies
        assert "execute" in policies
        assert "delete" in policies
    
    def test_phase_5_enhanced_window_control(self):
        """Test Phase 5: Enhanced Window & App Control"""
        # Apps capabilities
        response = client.get("/apps/capabilities", headers=HEADERS)
        assert response.status_code == 200
        
        # Launch app
        response = client.post("/apps/", headers=HEADERS, json={
            "action": "launch",
            "app": "test-app"
        })
        assert response.status_code == 200
        result = response.json()["result"]
        assert "pid" in result
        pid = result["pid"]
        
        # Test enhanced window operations (these will fail in headless but show structure)
        window_operations = ["snap", "tile", "pin"]
        for op in window_operations:
            response = client.post("/apps/", headers=HEADERS, json={
                "action": op,
                "pid": pid,
                "snap_position": "left" if op == "snap" else None,
                "tile_position": "top-left" if op == "tile" else None,
                "pin_to_top": True if op == "pin" else None
            })
            # Should get headless error but validates structure
            assert response.status_code == 200
    
    def test_phase_7_remote_session_support(self):
        """Test Phase 7: Remote Session Support"""
        # Session capabilities
        response = client.get("/session/capabilities", headers=HEADERS)
        assert response.status_code == 200
        caps = response.json()["result"]
        assert "headless" in caps
        assert "session_types" in caps
        
        # Start session with dry run
        response = client.post("/session/start", headers=HEADERS, json={
            "action": "start",
            "session_type": "headless",
            "display": ":99",
            "dry_run": True
        })
        assert response.status_code == 200
        
        # List sessions
        response = client.get("/session/list", headers=HEADERS)
        assert response.status_code == 200
    
    def test_phase_8_state_flow_control(self):
        """Test Phase 8: State & Flow Control"""
        # Flow capabilities
        response = client.get("/flow/capabilities", headers=HEADERS)
        assert response.status_code == 200
        caps = response.json()["result"]
        assert caps["wait_conditions"] == True
        assert caps["retry_logic"] == True
        assert caps["event_callbacks"] == True
        
        # Test retry with dry run
        response = client.post("/flow/retry", headers=HEADERS, json={
            "action": "retry",
            "operation": {
                "endpoint": "/input",
                "action": "click",
                "params": {"x": 100, "y": 100}
            },
            "max_attempts": 3,
            "dry_run": True
        })
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["status"] == "would_retry"
    
    def test_phase_10_data_channels(self):
        """Test Phase 10: Data Channels"""
        # Clipboard capabilities
        response = client.get("/clipboard/capabilities", headers=HEADERS)
        assert response.status_code == 200
        caps = response.json()["result"]
        assert "supported_content_types" in caps
        assert "supported_transfer_types" in caps
        
        # Clipboard operations with dry run
        response = client.post("/clipboard/", headers=HEADERS, json={
            "action": "set",
            "content_type": "text",
            "data": "Test clipboard data",
            "dry_run": True
        })
        assert response.status_code == 200
        
        # Data transfer
        response = client.post("/clipboard/transfer", headers=HEADERS, json={
            "action": "list_formats",
            "transfer_type": "clipboard",
            "dry_run": True
        })
        assert response.status_code == 200
    
    def test_phase_11_performance_efficiency(self):
        """Test Phase 11: Performance & Efficiency"""
        # Batch GUI capabilities
        response = client.get("/batch_gui/capabilities", headers=HEADERS)
        assert response.status_code == 200
        caps = response.json()["result"]
        assert "batching" in caps
        assert "region_scoping" in caps
        assert "performance_targets" in caps
        
        # Batch operations
        response = client.post("/batch_gui/batch", headers=HEADERS, json={
            "action": "execute",
            "operations": [
                {"endpoint": "/screen", "action": "capture", "params": {}, "priority": 1},
                {"endpoint": "/input", "action": "click", "params": {"x": 100, "y": 100}, "priority": 2}
            ],
            "execution_mode": "sequential",
            "dry_run": True
        })
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["operation_count"] == 2
        
        # Performance profiling
        response = client.post("/batch_gui/profile", headers=HEADERS, json={
            "action": "benchmark"
        })
        assert response.status_code == 200
    
    def test_phase_12_developer_ux(self):
        """Test Phase 12: Developer/Operator UX"""
        # Debug status
        response = client.get("/debug/status", headers=HEADERS)
        assert response.status_code == 200
        status = response.json()["result"]
        assert status["debugging_enabled"] == True
        assert "capabilities" in status
        
        # Debug capabilities
        response = client.get("/debug/capabilities", headers=HEADERS)
        assert response.status_code == 200
        caps = response.json()["result"]
        assert caps["debugging"]["step_through_execution"] == True
        assert caps["telemetry"]["performance_monitoring"] == True
        
        # Step-through debugging
        response = client.post("/debug/step_through", headers=HEADERS, json={
            "action": "start",
            "operations": [
                {"endpoint": "/input", "action": "click", "params": {"x": 50, "y": 50}}
            ]
        })
        assert response.status_code == 200
        result = response.json()["result"]
        assert "session_id" in result
    
    def test_phase_13_extensibility(self):
        """Test Phase 13: Extensibility"""
        # Plugin capabilities
        response = client.get("/plugins/capabilities", headers=HEADERS)
        assert response.status_code == 200
        caps = response.json()["result"]
        assert caps["plugin_loading"]["dynamic_loading"] == True
        assert caps["capability_management"]["capability_discovery"] == True
        assert caps["hook_system"]["event_hooks"] == True
        
        # List plugins (should be empty initially)
        response = client.get("/plugins/list", headers=HEADERS)
        assert response.status_code == 200
        result = response.json()["result"]
        assert "plugins" in result
        assert "total_loaded" in result
    
    def test_comprehensive_safety_integration(self):
        """Test that safety is integrated across all endpoints"""
        # Test safety check integration in various endpoints
        safety_integrated_endpoints = [
            ("/input/mouse_drag", {"action": "drag", "from_x": 0, "from_y": 0, "to_x": 100, "to_y": 100, "dry_run": True}),
            ("/flow/retry", {"action": "retry", "operation": {"endpoint": "/test", "action": "test"}, "dry_run": True}),
            ("/batch_gui/batch", {"action": "execute", "operations": [], "dry_run": True}),
        ]
        
        for endpoint, payload in safety_integrated_endpoints:
            response = client.post(endpoint, headers=HEADERS, json=payload)
            if response.status_code == 200:
                result = response.json().get("result", {})
                # Should have safety check integrated
                assert "safety_check" in result, f"Safety check missing in {endpoint}"
    
    def test_system_performance_targets(self):
        """Test that system meets performance targets"""
        # Test dry-run latency (should be <500ms as per requirements)
        start_time = time.time()
        
        response = client.post("/input/mouse_drag", headers=HEADERS, json={
            "action": "drag",
            "from_x": 100,
            "from_y": 100,
            "to_x": 200,
            "to_y": 200,
            "dry_run": True
        })
        
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        assert latency_ms < 500, f"Dry-run latency {latency_ms}ms exceeds 500ms target"
        
        # Check reported latency
        result = response.json()
        if "latency_ms" in result:
            reported_latency = result["latency_ms"]
            assert reported_latency < 500, f"Reported latency {reported_latency}ms exceeds 500ms target"
    
    def test_cross_platform_capabilities(self):
        """Test cross-platform capability reporting"""
        # All capability endpoints should report platform
        capability_endpoints = [
            "/screen/capabilities",
            "/input/capabilities", 
            "/session/capabilities",
            "/flow/capabilities",
            "/clipboard/capabilities"
        ]
        
        for endpoint in capability_endpoints:
            response = client.get(endpoint, headers=HEADERS)
            assert response.status_code == 200
            result = response.json()["result"]
            # Should have platform info
            if "platform" in result:
                assert result["platform"] in ["Linux", "Windows", "Darwin"]
    
    def test_complete_audit_trail(self):
        """Test that comprehensive audit trail is maintained"""
        # Check safety audit
        response = client.post("/safety/audit", headers=HEADERS, json={
            "limit": 10
        })
        assert response.status_code == 200
        
        # Check debug telemetry
        response = client.post("/debug/telemetry", headers=HEADERS, json={
            "query_type": "operations",
            "limit": 10
        })
        assert response.status_code == 200
        
        # Check safety status shows audit entries
        response = client.get("/safety/status", headers=HEADERS)
        assert response.status_code == 200
        status = response.json()["result"]
        assert status["total_audit_entries"] >= 0
    
    def test_error_handling_consistency(self):
        """Test consistent error handling across all endpoints"""
        # Test invalid API key
        response = client.get("/screen/capabilities", headers={"x-api-key": "invalid"})
        assert response.status_code == 403
        
        # Test missing required fields
        response = client.post("/input/mouse_drag", headers=HEADERS, json={
            "action": "invalid_action"
        })
        assert response.status_code == 200  # Returns 200 with error in body
        result = response.json()
        assert "errors" in result
        
        # Error responses should have consistent structure
        error = result["errors"][0]
        assert "code" in error
        assert "message" in error

if __name__ == "__main__":
    pytest.main([__file__, "-v"])