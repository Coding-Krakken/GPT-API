from pathlib import Path


def test_full_api_core_endpoint_matrix(client, auth_headers, temp_dir):
    target = Path(temp_dir) / "full_api_testfile.txt"
    matrix = [
        ("/system/", "GET", None, 200),
        ("/files", "POST", {"action": "write", "path": str(target), "content": "Hello, test!"}, 200),
        ("/files", "POST", {"action": "read", "path": str(target)}, 200),
        ("/files", "POST", {"action": "stat", "path": str(target)}, 200),
        ("/files", "POST", {"action": "exists", "path": str(target)}, 200),
        ("/shell", "POST", {"command": "echo pytest-shell"}, 200),
        ("/monitor", "POST", {"type": "cpu"}, 200),
        ("/git", "POST", {"action": "status", "path": "."}, 200),
        ("/package", "POST", {"manager": "pip", "action": "list"}, 200),
        ("/apps", "POST", {"action": "list"}, 200),
        ("/refactor", "POST", {"search": "Hello", "replace": "Hi", "files": [str(target)], "dry_run": True}, 200),
        ("/batch", "POST", {"operations": [{"endpoint": "shell", "action": "shell", "payload": {"command": "echo batch1"}}]}, 200),
    ]
    for endpoint, method, payload, expected in matrix:
        if method == "GET":
            response = client.get(endpoint, headers=auth_headers)
        else:
            response = client.post(endpoint, headers=auth_headers, json=payload)
        assert response.status_code == expected, f"{method} {endpoint}: {response.text}"

    delete = client.post("/files", headers=auth_headers, json={"action": "delete", "path": str(target), "confirm": True})
    assert delete.status_code == 200
    assert delete.json()["result"]["status"] == 200


def test_full_api_error_cases(client, auth_headers, temp_dir):
    missing = client.post("/files", headers=auth_headers, json={"action": "read", "path": str(Path(temp_dir) / "missing.txt")})
    assert missing.status_code == 200
    assert missing.json()["result"]["status"] == 404

    no_auth = client.get("/system/")
    assert no_auth.status_code == 403

    bad_auth = client.get("/system/", headers={"x-api-key": "bad-key"})
    assert bad_auth.status_code == 403


def test_full_api_bulk_file_ops(client, auth_headers, temp_dir):
    files = [Path(temp_dir) / f"bulkfile_{idx}.txt" for idx in range(3)]
    for path in files:
        response = client.post("/files", headers=auth_headers, json={"action": "write", "path": str(path), "content": "bulk"})
        assert response.status_code == 200
        assert response.json()["result"]["status"] == 200

    listed = client.post("/files", headers=auth_headers, json={"action": "list", "path": temp_dir}).json()["result"]
    for path in files:
        assert path.name in listed["items"]

    for path in files:
        response = client.post("/files", headers=auth_headers, json={"action": "delete", "path": str(path), "confirm": True})
        assert response.status_code == 200
        assert response.json()["result"]["status"] == 200


def test_full_api_shell_side_effect(client, auth_headers, temp_dir):
    target = Path(temp_dir) / "shell_created.txt"
    response = client.post("/shell", headers=auth_headers, json={"command": f"echo created > {target}"})
    assert response.status_code == 200
    assert response.json()["exit_code"] == 0

    exists = client.post("/files", headers=auth_headers, json={"action": "exists", "path": str(target)})
    assert exists.status_code == 200
    assert exists.json()["result"]["exists"] is True

    cleanup = client.post("/files", headers=auth_headers, json={"action": "delete", "path": str(target), "confirm": True})
    assert cleanup.status_code == 200
