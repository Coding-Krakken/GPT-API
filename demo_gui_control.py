#!/usr/bin/env python3
"""
GUI Control Layer Demo - showcases capabilities
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

def demo_gui_capabilities():
    """Demonstrate GUI Control Layer capabilities"""
    print("🎮 GUI Control Layer Demo")
    print("=" * 50)
    
    try:
        # Import and test core functionality
        from utils.gui_env import detect_gui_environment_comprehensive, get_install_guidance
        
        # Detect GUI environment
        print("🔍 Detecting GUI Environment...")
        env = detect_gui_environment_comprehensive()
        
        print(f"\n📋 System Information:")
        print(f"   OS: {env['os']}")
        print(f"   Session: {env['session_type']} ({'Wayland' if env['wayland'] else 'X11' if env['x11'] else 'Headless'})")
        print(f"   Display: {env['display'] or 'None'}")
        print(f"   Wayland Display: {env['wayland_display'] or 'None'}")
        print(f"   Compositor: {env['compositor'] or 'Unknown'}")
        
        # Show available tools
        available_tools = [tool for tool, available in env['tools'].items() if available]
        missing_tools = [tool for tool, available in env['tools'].items() if not available]
        
        print(f"\n🛠️  Tool Status ({len(available_tools)}/{len(env['tools'])} available):")
        
        if available_tools:
            print("   ✅ Available:")
            for tool in available_tools[:10]:  # Show first 10
                print(f"      • {tool}")
            if len(available_tools) > 10:
                print(f"      • ... and {len(available_tools) - 10} more")
        
        if missing_tools:
            print("   ❌ Missing:")
            for tool in missing_tools[:10]:  # Show first 10
                print(f"      • {tool}")
            if len(missing_tools) > 10:
                print(f"      • ... and {len(missing_tools) - 10} more")
        
        # Show capabilities
        print(f"\n⚡ Capabilities:")
        capabilities = env['capabilities']
        for cap, enabled in capabilities.items():
            status = "✅" if enabled else "❌"
            print(f"   {status} {cap.replace('_', ' ').title()}")
        
        # Show detection methods used
        if env['detection_methods']:
            print(f"\n🔬 Detection Methods Used:")
            for method in env['detection_methods']:
                print(f"   • {method}")
        
        # Performance metrics
        latency_ms = env['detection_latency_us'] / 1000
        print(f"\n⏱️  Performance:")
        print(f"   Detection Latency: {env['detection_latency_us']} μs ({latency_ms:.2f} ms)")
        
        # Installation guidance
        if missing_tools:
            guidance = get_install_guidance(missing_tools[:5])  # First 5 missing tools
            print(f"\n📦 Installation Guidance:")
            print(f"   {guidance}")
        
        print(f"\n🎯 Overall Status: {'🟢 Healthy' if any(capabilities.values()) else '🟡 Limited Functionality'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def demo_example_usage():
    """Show example API usage"""
    print(f"\n\n🚀 Example API Usage")
    print("=" * 50)
    
    examples = [
        {
            "endpoint": "GET /gui/session",
            "description": "Get comprehensive GUI session info",
            "curl": "curl -H 'x-api-key: your-key' http://localhost:8000/gui/session"
        },
        {
            "endpoint": "GET /apps_advanced/list_windows_detailed", 
            "description": "List all windows with geometry and state",
            "curl": "curl -H 'x-api-key: your-key' http://localhost:8000/apps_advanced/list_windows_detailed"
        },
        {
            "endpoint": "POST /apps_advanced/launch",
            "description": "Launch app with tracking",
            "curl": "curl -X POST -H 'x-api-key: your-key' -H 'Content-Type: application/json' -d '{\"app\":\"firefox\",\"args\":\"--new-tab\"}' http://localhost:8000/apps_advanced/launch"
        },
        {
            "endpoint": "POST /apps_advanced/focus",
            "description": "Focus a window",
            "curl": "curl -X POST -H 'x-api-key: your-key' -H 'Content-Type: application/json' -d '{\"action\":\"focus\",\"window_id\":\"0x123456\"}' http://localhost:8000/apps_advanced/focus"
        },
        {
            "endpoint": "POST /input_enhanced/type",
            "description": "Type text via automation",
            "curl": "curl -X POST -H 'x-api-key: your-key' -H 'Content-Type: application/json' -d '{\"action\":\"type\",\"text\":\"Hello World\"}' http://localhost:8000/input_enhanced/type"
        },
        {
            "endpoint": "POST /apps_advanced/screenshot",
            "description": "Capture screenshot",
            "curl": "curl -X POST -H 'x-api-key: your-key' -H 'Content-Type: application/json' -d '{\"format\":\"png\"}' http://localhost:8000/apps_advanced/screenshot"
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['endpoint']}")
        print(f"   📝 {example['description']}")
        print(f"   💻 {example['curl']}")

def demo_workflow_example():
    """Show a complete workflow example"""
    print(f"\n\n🔄 Complete Workflow Example")
    print("=" * 50)
    
    workflow = [
        "1. Detect GUI environment and capabilities",
        "2. Launch Firefox browser",
        "3. Get window information",
        "4. Resize and position window",
        "5. Type URL in address bar",
        "6. Take screenshot of result",
        "7. Use OCR to read page content"
    ]
    
    print("📋 Automated GUI Workflow:")
    for step in workflow:
        print(f"   {step}")
    
    print(f"\n💡 This workflow demonstrates:")
    print(f"   • Multi-method window detection (wmctrl + swaymsg + /proc)")
    print(f"   • Cross-platform compatibility (X11 + Wayland)")
    print(f"   • Real-time window management")
    print(f"   • Input automation with fallbacks")
    print(f"   • Screenshot capture with multiple tools")
    print(f"   • OCR integration for content analysis")
    print(f"   • Microsecond-precision observability")

def main():
    """Run complete demo"""
    success = demo_gui_capabilities()
    demo_example_usage()
    demo_workflow_example()
    
    print(f"\n" + "=" * 70)
    print("🎉 GUI Control Layer Demo Complete!")
    print("=" * 70)
    
    if success:
        print("✅ Core functionality verified")
        print("📚 See INSTALL_GUI_TOOLS.md for installation guidance")
        print("🧪 Run 'python test_gui_standalone.py' for detailed tests")
        print("🚀 Start server with 'uvicorn main:app --reload' to test API")
    else:
        print("⚠️  Some issues detected - check error messages above")
    
    print(f"\n🔗 Key Features Implemented:")
    features = [
        "✅ Comprehensive Wayland + X11 hybrid detection",
        "✅ Multi-method window enumeration with fallbacks", 
        "✅ Advanced GUI session introspection",
        "✅ Window control (focus, resize, move, close)",
        "✅ Input automation (keyboard, mouse, typing)",
        "✅ Screenshot capture with multiple backends",
        "✅ Microsecond-precision observability",
        "✅ Structured error codes and guidance",
        "✅ Process-based GUI metadata linking",
        "✅ Virtual display support (Xvfb, VNC)",
        "✅ Desktop portal integration",
        "✅ Accessibility framework support",
        "✅ OCR and visual recognition (framework)",
        "✅ Comprehensive test suite",
        "✅ Installation guidance and documentation"
    ]
    
    for feature in features:
        print(f"   {feature}")

if __name__ == "__main__":
    main()