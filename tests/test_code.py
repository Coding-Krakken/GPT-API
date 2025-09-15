import pytest
import os

class TestCodeEndpoints:
    """Test suite for /code endpoint operations."""

    def test_run_python_script(self, client, auth_headers, test_script):
        """Test running a Python script."""
        payload = {
            "action": "run",
            "path": test_script,
            "language": "python"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "stdout" in data["result"]
        assert "stderr" in data["result"]
        assert "exit_code" in data["result"]
        assert data["result"]["exit_code"] == 0
        assert "Hello from test script!" in data["result"]["stdout"]

    def test_invalid_content_syntax(self, client, auth_headers):
        """Test handling of invalid Python syntax in content."""
        payload = {
            "action": "run",
            "content": "print('Hello' invalid syntax",  # Invalid Python syntax
            "language": "python"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "invalid_python_syntax"

    def test_run_python_with_content(self, client, auth_headers):
        """Test running Python code from content."""
        code_content = """
print("Hello from content!")
x = 42
print(f"x = {x}")
"""
        payload = {
            "action": "run",
            "language": "python",
            "content": code_content
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "Hello from content!" in data["result"]["stdout"]
        assert "x = 42" in data["result"]["stdout"]
        assert data["result"]["exit_code"] == 0

    def test_run_bash_script(self, client, auth_headers, temp_dir):
        """Test running a bash script."""
        bash_script = os.path.join(temp_dir, "test.sh")
        with open(bash_script, "w") as f:
            f.write("""#!/bin/bash
echo "Hello from bash!"
echo "Current dir: $(pwd)"
""")
        os.chmod(bash_script, 0o755)

        payload = {
            "action": "run",
            "path": bash_script,
            "language": "bash"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["exit_code"] == 0
        assert "Hello from bash!" in data["result"]["stdout"]

    def test_run_node_script(self, client, auth_headers, temp_dir):
        """Test running a Node.js script."""
        js_script = os.path.join(temp_dir, "test.js")
        with open(js_script, "w") as f:
            f.write("""
console.log("Hello from Node.js!");
const x = 42;
console.log(`x = ${x}`);
""")
        payload = {
            "action": "run",
            "path": js_script,
            "language": "node"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert data["result"]["exit_code"] == 0
        assert "Hello from Node.js!" in data["result"]["stdout"]
        assert "x = 42" in data["result"]["stdout"]

    def test_explain_python_code(self, client, auth_headers, test_script):
        """Test explaining Python code."""
        payload = {
            "action": "explain",
            "path": test_script,
            "language": "python"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "code" in data["result"]
        assert "explanation" in data["result"]
        assert "def hello():" in data["result"]["code"]

    def test_invalid_language(self, client, auth_headers, test_script):
        """Test invalid language."""
        payload = {
            "action": "run",
            "path": test_script,
            "language": "invalid_lang"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "unsupported_language"
        assert data["result"]["status"] == 400

    def test_missing_path_and_content(self, client, auth_headers):
        """Test missing path and content."""
        payload = {
            "action": "run",
            "language": "python"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "missing_path_or_content"
        assert data["result"]["status"] == 400

    def test_invalid_path(self, client, auth_headers, temp_dir):
        """Test invalid file path."""
        invalid_path = os.path.join(temp_dir, "nonexistent.py")
        payload = {
            "action": "run",
            "path": invalid_path,
            "language": "python"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "file_not_found"
        assert data["result"]["status"] == 404

    def test_invalid_args(self, client, auth_headers, test_script):
        """Test invalid arguments."""
        payload = {
            "action": "run",
            "path": test_script,
            "language": "python",
            "args": "--invalid-flag"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "invalid_args"
        assert data["result"]["status"] == 400

    def test_unsafe_args(self, client, auth_headers, test_script):
        """Test unsafe arguments."""
        payload = {
            "action": "run",
            "path": test_script,
            "language": "python",
            "args": "; rm -rf /"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "invalid_args"
        assert data["result"]["status"] == 400

    def test_invalid_content_syntax(self, client, auth_headers):
        """Test invalid Python syntax in content."""
        invalid_code = """
def hello(
    print("Invalid syntax")
"""
        payload = {
            "action": "run",
            "language": "python",
            "content": invalid_code
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "invalid_content"
        assert data["result"]["status"] == 400

    def test_content_too_large(self, client, auth_headers):
        """Test content that is too large."""
        large_content = "print('hello')\n" * 10000  # Should exceed 100KB
        payload = {
            "action": "run",
            "language": "python",
            "content": large_content
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "invalid_content"
        assert data["result"]["status"] == 400

    def test_unsupported_action_for_content(self, client, auth_headers):
        """Test unsupported action with content."""
        payload = {
            "action": "explain",
            "language": "python",
            "content": "print('hello')"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "unsupported_content"
        assert data["result"]["status"] == 400

    def test_language_extension_mismatch(self, client, auth_headers, temp_dir):
        """Test language and file extension mismatch."""
        wrong_ext_file = os.path.join(temp_dir, "test.js")
        with open(wrong_ext_file, "w") as f:
            f.write("print('hello')")  # Python code in .js file

        payload = {
            "action": "run",
            "path": wrong_ext_file,
            "language": "python"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "language_mismatch"
        assert data["result"]["status"] == 400

    def test_path_injection_attempt(self, client, auth_headers):
        """Test path injection attempt."""
        payload = {
            "action": "run",
            "path": "../../../etc/passwd",
            "language": "python"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "invalid_path"
        assert data["result"]["status"] == 400

    def test_overlong_path(self, client, auth_headers):
        """Test path that is too long."""
        long_path = "/tmp/" + "a" * 256
        payload = {
            "action": "run",
            "path": long_path,
            "language": "python"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "path_too_long"
        assert data["result"]["status"] == 400

    def test_fault_injection_syntax(self, client, auth_headers, test_script):
        """Test syntax fault injection."""
        payload = {
            "action": "run",
            "path": test_script,
            "language": "python",
            "fault": "syntax"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "syntax_error"

    def test_fault_injection_io(self, client, auth_headers, test_script):
        """Test IO fault injection."""
        payload = {
            "action": "run",
            "path": test_script,
            "language": "python",
            "fault": "io"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "io_error"

    def test_fault_injection_permission(self, client, auth_headers, test_script):
        """Test permission fault injection."""
        payload = {
            "action": "run",
            "path": test_script,
            "language": "python",
            "fault": "permission"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "permission_denied"

    def test_invalid_action(self, client, auth_headers, test_script):
        """Test invalid action."""
        payload = {
            "action": "invalid_action",
            "path": test_script,
            "language": "python"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "result" in data
        assert "error" in data["result"]
        assert data["result"]["error"]["code"] == "invalid_action"
        assert data["result"]["status"] == 400

    def test_chained_actions(self, client, auth_headers, temp_dir):
        """Test chained actions."""
        # Create a script with issues
        script_path = os.path.join(temp_dir, "chained_test.py")
        with open(script_path, "w") as f:
            f.write("""
import os
def hello():
    print("Hello!")
    return "success"
""")
        payload = {
            "actions": ["run", "explain"],
            "path": script_path,
            "language": "python"
        }
        response = client.post("/code", headers=auth_headers, json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "chained" in data
        assert data["chained"] is True
        assert "results" in data
        assert len(data["results"]) == 2