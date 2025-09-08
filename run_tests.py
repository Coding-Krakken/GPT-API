#!/usr/bin/env python3
"""
Enterprise-grade test runner for GPT-API
Runs comprehensive test suite with coverage reporting
"""

import os
import sys
import subprocess
import argparse
import time
from pathlib import Path

def run_command(cmd, description, cwd=None):
    """Run a command and return success status."""
    print(f"\n🔧 {description}")
    print(f"   Command: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        if result.returncode == 0:
            print(f"   ✅ {description} completed successfully")
            if result.stdout.strip():
                print(f"   Output: {result.stdout.strip()[:200]}...")
            return True
        else:
            print(f"   ❌ {description} failed with code {result.returncode}")
            if result.stderr:
                print(f"   Error: {result.stderr.strip()}")
            return False
    except subprocess.TimeoutExpired:
        print(f"   ⏰ {description} timed out")
        return False
    except Exception as e:
        print(f"   💥 {description} failed with exception: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="GPT-API Test Runner")
    parser.add_argument("--no-cov", action="store_true", help="Skip coverage reporting")
    parser.add_argument("--fast", action="store_true", help="Run only fast tests")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--module", help="Run specific test module")
    args = parser.parse_args()

    print("🚀 GPT-API Enterprise Test Suite")
    print("=" * 50)

    # Check if we're in the right directory
    if not Path("main.py").exists():
        print("❌ Error: main.py not found. Please run from the project root.")
        sys.exit(1)

    # Set test environment
    os.environ["API_KEY"] = "test-api-key-12345"
    os.environ["PYTHONPATH"] = str(Path.cwd())

    # Build pytest command
    cmd = [sys.executable, "-m", "pytest"]

    if args.module:
        cmd.append(f"tests/test_{args.module}.py")
    else:
        cmd.append("tests/")

    if not args.no_cov:
        cmd.extend([
            "--cov=.",
            "--cov-report=html",
            "--cov-report=term-missing",
            "--cov-fail-under=95"
        ])

    if args.fast:
        cmd.append("-m not slow")

    if args.verbose:
        cmd.append("--verbose")
    else:
        cmd.append("--tb=short")

    # Run tests
    start_time = time.time()
    success = run_command(cmd, "Running test suite")
    end_time = time.time()

    print(f"\n{'=' * 50}")
    print("📊 Test Results Summary")
    print(f"   Duration: {end_time - start_time:.2f} seconds")
    print(f"   Status: {'✅ PASSED' if success else '❌ FAILED'}")

    if not args.no_cov and success:
        print("\n📈 Coverage Report:")
        print("   HTML report: htmlcov/index.html")
    
    if success:
        print("\n🎉 All tests passed! Your API is ready for production.")
    else:
        print("\n💥 Some tests failed. Please review the output above.")
        sys.exit(1)

if __name__ == "__main__":
    main()