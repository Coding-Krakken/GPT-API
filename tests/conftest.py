import pytest
import tempfile
import os
import shutil
from fastapi.testclient import TestClient
from main import app
import sys

# Add the project root to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment variables
os.environ["API_KEY"] = "9e2b7c8a-4f1e-4b2a-9d3c-7f6e5a1b2c3d"

@pytest.fixture(scope="session")
def client():
    """FastAPI test client fixture."""
    return TestClient(app)

@pytest.fixture(scope="session")
def api_key():
    """API key for authentication."""
    return "9e2b7c8a-4f1e-4b2a-9d3c-7f6e5a1b2c3d"

@pytest.fixture(scope="function")
def temp_dir():
    """Temporary directory for file operations."""
    temp_path = tempfile.mkdtemp(prefix="gpt_api_test_")
    yield temp_path
    # Cleanup
    shutil.rmtree(temp_path, ignore_errors=True)

@pytest.fixture(scope="function")
def temp_file(temp_dir):
    """Temporary file for testing."""
    file_path = os.path.join(temp_dir, "test_file.txt")
    with open(file_path, "w") as f:
        f.write("test content\n")
    return file_path

@pytest.fixture(scope="function")
def temp_git_repo(temp_dir):
    """Temporary git repository for testing."""
    import subprocess
    # Don't change the global working directory - use cwd parameter instead
    subprocess.run(["git", "init"], check=True, capture_output=True, cwd=temp_dir)
    subprocess.run(["git", "config", "user.name", "Test User"], check=True, capture_output=True, cwd=temp_dir)
    subprocess.run(["git", "config", "user.email", "test@example.com"], check=True, capture_output=True, cwd=temp_dir)
    # Create a test file and commit
    test_file = os.path.join(temp_dir, "test.txt")
    with open(test_file, "w") as f:
        f.write("initial content")
    subprocess.run(["git", "add", "test.txt"], check=True, capture_output=True, cwd=temp_dir)
    subprocess.run(["git", "commit", "-m", "Initial commit"], check=True, capture_output=True, cwd=temp_dir)
    return temp_dir

@pytest.fixture(scope="function")
def auth_headers(api_key):
    """Authentication headers."""
    return {"x-api-key": api_key, "Content-Type": "application/json"}

@pytest.fixture(scope="function")
def test_script(temp_dir):
    """Create a simple test script."""
    script_path = os.path.join(temp_dir, "test_script.py")
    with open(script_path, "w") as f:
        f.write("""
def hello():
    print("Hello from test script!")
    return "success"

if __name__ == "__main__":
    hello()
""")
    return script_path

@pytest.fixture(scope="function")
def test_package_json(temp_dir):
    """Create a test package.json for npm testing."""
    package_path = os.path.join(temp_dir, "package.json")
    with open(package_path, "w") as f:
        f.write("""
{
  "name": "test-package",
  "version": "1.0.0",
  "scripts": {
    "test": "echo 'npm test passed'"
  }
}
""")
    return package_path