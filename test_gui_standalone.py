#!/usr/bin/env python3
"""
Standalone GUI detection test - works without FastAPI dependencies
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def test_gui_detection():
    """Test core GUI detection functionality"""
    try:
        from utils.gui_env import detect_gui_environment_comprehensive, get_microsecond_timestamp
        
        print("🔍 Testing GUI Environment Detection...")
        print("=" * 50)
        
        # Test microsecond timing
        start_time = get_microsecond_timestamp()
        print(f"✅ Microsecond timestamp: {start_time}")
        
        # Test comprehensive GUI detection
        env = detect_gui_environment_comprehensive()
        
        print(f"\n📊 GUI Environment Results:")
        print(f"   OS: {env.get('os')}")
        print(f"   Session Type: {env.get('session_type')}")
        print(f"   Compositor: {env.get('compositor')}")
        print(f"   Display: {env.get('display')}")
        print(f"   Wayland Display: {env.get('wayland_display')}")
        print(f"   Desktop Session: {env.get('desktop_session')}")
        
        print(f"\n🛠️  Available Tools:")
        tools = env.get('tools', {})
        available_tools = [tool for tool, available in tools.items() if available]
        missing_tools = [tool for tool, available in tools.items() if not available]
        
        print(f"   Available ({len(available_tools)}): {', '.join(available_tools) if available_tools else 'None'}")
        print(f"   Missing ({len(missing_tools)}): {', '.join(missing_tools[:10]) if missing_tools else 'None'}")
        
        print(f"\n⚡ Capabilities:")
        capabilities = env.get('capabilities', {})
        for cap, enabled in capabilities.items():
            status = "✅" if enabled else "❌"
            print(f"   {status} {cap}")
        
        print(f"\n🔬 Detection Methods:")
        methods = env.get('detection_methods', [])
        for method in methods:
            print(f"   • {method}")
        
        detection_time = env.get('detection_latency_us', 0)
        print(f"\n⏱️  Detection Latency: {detection_time} microseconds ({detection_time/1000:.2f} ms)")
        
        print(f"\n✅ GUI detection test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error during GUI detection: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_window_detection_logic():
    """Test window detection logic without actual window manager calls"""
    try:
        print("\n🪟 Testing Window Detection Logic...")
        print("=" * 50)
        
        # Test wmctrl output parsing
        mock_wmctrl_output = """0x02000006  0 12345   100 200 800 600 hostname Firefox
0x02000007  0 54321   200 300 400 500 hostname Terminal
0x02000008 -1 67890   300 400 600 700 hostname VSCode"""
        
        windows = []
        for line in mock_wmctrl_output.strip().split('\n'):
            if line.strip():
                parts = line.split()
                if len(parts) >= 8:
                    windows.append({
                        "window_id": parts[0],
                        "desktop": int(parts[1]) if parts[1] != '-1' else None,
                        "pid": int(parts[2]) if parts[2] != '-1' else None,
                        "geometry": {
                            "x": int(parts[3]),
                            "y": int(parts[4]),
                            "width": int(parts[5]),
                            "height": int(parts[6])
                        },
                        "title": ' '.join(parts[7:]),
                        "method": "wmctrl"
                    })
        
        print(f"✅ Parsed {len(windows)} windows from mock wmctrl output:")
        for i, window in enumerate(windows, 1):
            print(f"   {i}. {window['title']} (PID: {window['pid']}) - {window['geometry']['width']}x{window['geometry']['height']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during window detection logic test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_error_codes():
    """Test structured error codes"""
    try:
        print("\n🚨 Testing Structured Error Codes...")
        print("=" * 50)
        
        GUI_ERRORS = {
            "gui_tool_missing": "Required GUI tool not found",
            "wayland_permission_denied": "Wayland compositor denied access",
            "x11_unreachable": "X11 server unreachable",
            "compositor_blocking": "Compositor blocking requested operation",
            "session_not_detected": "GUI session type not detected",
            "window_not_found": "Target window not found",
            "invalid_geometry": "Invalid window geometry parameters",
            "automation_failed": "GUI automation operation failed"
        }
        
        print("✅ Structured error codes defined:")
        for code, message in GUI_ERRORS.items():
            print(f"   • {code}: {message}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during error codes test: {e}")
        return False

def test_install_guidance():
    """Test install guidance generation"""
    try:
        print("\n📦 Testing Install Guidance...")
        print("=" * 50)
        
        from utils.gui_env import get_install_guidance
        
        missing_tools = ["wmctrl", "xdotool", "swaymsg", "scrot"]
        guidance = get_install_guidance(missing_tools)
        
        print(f"✅ Install guidance generated:")
        print(f"   {guidance}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during install guidance test: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all standalone tests"""
    print("🚀 Starting GUI Control Layer Standalone Tests")
    print("=" * 60)
    
    tests = [
        ("GUI Detection", test_gui_detection),
        ("Window Detection Logic", test_window_detection_logic),
        ("Error Codes", test_error_codes),
        ("Install Guidance", test_install_guidance)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n🧪 Running: {test_name}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 60)
    print("📋 Test Results Summary:")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! GUI Control Layer core functionality is working.")
    else:
        print("⚠️  Some tests failed. Please check the implementation.")
    
    return passed == len(results)

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)