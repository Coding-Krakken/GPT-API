# 📊 API Reference & Endpoint Documentation

## Authentication

All API endpoints require authentication via the `x-api-key` header.

```bash
curl -H "x-api-key: your_api_key_here" ...
```

**Response on Authentication Failure:**
```json
{
  "status_code": 403,
  "detail": "Invalid API key"
}
```

## Base URL Structure

```
Production:  https://api.example.com
Development: http://127.0.0.1:8000
```

## 🐚 Shell Operations (`/shell`)

Execute system commands with full control over execution environment.

### Endpoint: `POST /shell`

**Request Model:**
```json
{
  "command": "string",
  "run_as_sudo": false,
  "background": false,
  "shell": "/bin/bash"
}
```

**Request Parameters:**
- `command` (string, required): The command to execute
- `run_as_sudo` (boolean, optional): Execute with elevated privileges
- `background` (boolean, optional): Run in background (non-blocking)
- `shell` (string, optional): Shell interpreter to use

**Response Model:**
```json
{
  "stdout": "command output",
  "stderr": "error output",
  "exit_code": 0
}
```

**Examples:**

<details>
<summary>📌 Basic Command Execution</summary>

```bash
curl -X POST "http://localhost:8000/shell" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "ls -la /home"
  }'
```

Response:
```json
{
  "stdout": "drwxr-xr-x 3 root root 4096 Jan 1 12:00 .",
  "stderr": "",
  "exit_code": 0
}
```
</details>

<details>
<summary>📌 Administrative Command</summary>

```bash
curl -X POST "http://localhost:8000/shell" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "systemctl status nginx",
    "run_as_sudo": true
  }'
```
</details>

<details>
<summary>📌 Background Process</summary>

```bash
curl -X POST "http://localhost:8000/shell" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "command": "python long_running_script.py",
    "background": true
  }'
```
</details>

---

## 📁 File Operations (`/files`)

Comprehensive file system management with support for all CRUD operations.

### Endpoint: `POST /files`

**Request Model:**
```json
{
  "action": "read|write|delete|copy|move|stat|exists|list",
  "path": "string",
  "target_path": "string (optional)",
  "content": "string (optional)",
  "recursive": false
}
```

**Request Parameters:**
- `action` (string, required): Operation to perform
- `path` (string, required): Source file/directory path
- `target_path` (string, optional): Destination for copy/move operations
- `content` (string, optional): Content for write operations
- `recursive` (boolean, optional): Recursive operation for directories

### Action: `read`

**Purpose:** Read file contents

**Example:**
```bash
curl -X POST "http://localhost:8000/files" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "read",
    "path": "/home/user/document.txt"
  }'
```

**Response:**
```json
{
  "content": "file contents here..."
}
```

### Action: `write`

**Purpose:** Create or update file with content

**Example:**
```bash
curl -X POST "http://localhost:8000/files" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "write",
    "path": "/home/user/new_file.txt",
    "content": "Hello, World!\nThis is a new file."
  }'
```

**Response:**
```json
{
  "status": "Wrote to /home/user/new_file.txt"
}
```

### Action: `delete`

**Purpose:** Delete files or directories

**Example:**
```bash
curl -X POST "http://localhost:8000/files" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "delete",
    "path": "/home/user/temp_dir",
    "recursive": true
  }'
```

### Action: `copy`

**Purpose:** Copy files or directories

**Example:**
```bash
curl -X POST "http://localhost:8000/files" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "copy",
    "path": "/home/user/source.txt",
    "target_path": "/home/user/backup.txt"
  }'
```

### Action: `move`

**Purpose:** Move/rename files or directories

### Action: `stat`

**Purpose:** Get file metadata

**Response:**
```json
{
  "size": 1024,
  "mtime": 1640995200.0,
  "ctime": 1640991600.0
}
```

### Action: `exists`

**Purpose:** Check if file/directory exists

**Response:**
```json
{
  "exists": true
}
```

### Action: `list`

**Purpose:** List directory contents

**Response:**
```json
{
  "items": ["file1.txt", "dir1", "file2.py"]
}
```

---

## ⚡ Code Operations (`/code`)

Execute, test, lint, and format code in multiple programming languages.

### Endpoint: `POST /code`

**Request Model:**
```json
{
  "action": "run|test|lint|format|fix|explain",
  "path": "string",
  "language": "python|javascript|bash|node",
  "args": "string (optional)"
}
```

### Supported Languages & Actions

| Language | Run | Test | Lint | Format | Tools Used |
|----------|-----|------|------|--------|------------|
| **Python** | ✅ | ✅ | ✅ | ✅ | python, pytest, flake8, black |
| **JavaScript** | ✅ | ✅ | ✅ | ✅ | node, npm test, eslint, prettier |
| **Bash** | ✅ | 📋 | 📋 | 📋 | bash |
| **TypeScript** | 📋 | 📋 | 📋 | 📋 | Future support |

**Examples:**

<details>
<summary>📌 Run Python Script</summary>

```bash
curl -X POST "http://localhost:8000/code" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "run",
    "path": "/home/user/script.py",
    "language": "python",
    "args": "--verbose"
  }'
```
</details>

<details>
<summary>📌 Run Tests</summary>

```bash
curl -X POST "http://localhost:8000/code" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "test",
    "path": "/home/user/tests/",
    "language": "python"
  }'
```
</details>

<details>
<summary>📌 Lint Code</summary>

```bash
curl -X POST "http://localhost:8000/code" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "lint",
    "path": "/home/user/code.py",
    "language": "python"
  }'
```
</details>

<details>
<summary>📌 Format Code</summary>

```bash
curl -X POST "http://localhost:8000/code" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "format",
    "path": "/home/user/messy_code.py",
    "language": "python"
  }'
```
</details>

---

## 📊 System Information (`/system`)

Get comprehensive system metrics and information.

### Endpoint: `GET /system`

**No request parameters required.**

**Response Model:**
```json
{
  "os": "Linux",
  "hostname": "server01",
  "architecture": "x86_64",
  "cpu": "Intel Core i7-9700K",
  "cpu_usage_percent": 15.2,
  "cpu_cores": 8,
  "memory_total_gb": 32.0,
  "memory_used_gb": 8.4,
  "memory_usage_percent": 26.3,
  "disk_usage_percent": 45.8,
  "uptime_seconds": 86400,
  "current_user": "apiuser"
}
```

**Example:**
```bash
curl -X GET "http://localhost:8000/system" \
  -H "x-api-key: your_key"
```

---

## 📊 Real-time Monitoring (`/monitor`)

Monitor system resources in real-time or get snapshots.

### Endpoint: `POST /monitor`

**Request Model:**
```json
{
  "type": "cpu|memory|disk|network|logs",
  "live": false
}
```

**Request Parameters:**
- `type` (string, optional): Type of monitoring (default: "cpu")
- `live` (boolean, optional): Real-time monitoring vs snapshot

### Monitor Types

#### CPU Monitoring
```bash
curl -X POST "http://localhost:8000/monitor" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "cpu"
  }'
```

**Response:**
```json
{
  "usage_percent": 23.5
}
```

#### Memory Monitoring
```bash
curl -X POST "http://localhost:8000/monitor" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "memory"
  }'
```

**Response:**
```json
{
  "total_gb": 32.0,
  "used_gb": 8.4,
  "percent": 26.3
}
```

#### Disk Monitoring
**Response:**
```json
{
  "total_gb": 1000.0,
  "used_gb": 458.0,
  "percent": 45.8
}
```

#### Network Monitoring
**Response:**
```json
{
  "bytes_sent": 1048576,
  "bytes_recv": 2097152
}
```

---

## 🌐 Git Operations (`/git`)

Complete Git repository management and version control operations.

### Endpoint: `POST /git`

**Request Model:**
```json
{
  "action": "status|add|commit|push|pull|clone|diff|log",
  "path": "string",
  "args": "string (optional)"
}
```

**Request Parameters:**
- `action` (string, required): Git command to execute
- `path` (string, required): Repository path
- `args` (string, optional): Additional arguments

**Supported Actions:**
- `status` - Repository status
- `add` - Stage files
- `commit` - Commit changes
- `push` - Push to remote
- `pull` - Pull from remote
- `clone` - Clone repository
- `diff` - Show differences
- `log` - Show commit history
- `branch` - Branch operations
- `merge` - Merge branches

**Examples:**

<details>
<summary>📌 Git Status</summary>

```bash
curl -X POST "http://localhost:8000/git" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "status",
    "path": "/home/user/myproject"
  }'
```
</details>

<details>
<summary>📌 Git Commit</summary>

```bash
curl -X POST "http://localhost:8000/git" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "commit",
    "path": "/home/user/myproject",
    "args": "-m \"Add new feature\""
  }'
```
</details>

<details>
<summary>📌 Git Clone</summary>

```bash
curl -X POST "http://localhost:8000/git" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "clone",
    "path": "/home/user/projects",
    "args": "https://github.com/user/repo.git"
  }'
```
</details>

---

## 📦 Package Management (`/package`)

Universal package manager support across different platforms and languages.

### Endpoint: `POST /package`

**Request Model:**
```json
{
  "manager": "pip|npm|apt|pacman|brew|winget",
  "action": "install|remove|update|upgrade|list",
  "package": "string"
}
```

**Request Parameters:**
- `manager` (string, required): Package manager to use
- `action` (string, required): Action to perform
- `package` (string, required): Package name (not required for update/upgrade/list)

### Supported Package Managers

| Manager | Platform | Actions Supported |
|---------|----------|-------------------|
| **pip** | Python | install, remove, update, list |
| **npm** | JavaScript/Node.js | install, remove, update, list |
| **apt** | Ubuntu/Debian | install, remove, update, upgrade, list |
| **pacman** | Arch Linux | install, remove, update, list |
| **brew** | macOS | install, remove, update, upgrade, list |
| **winget** | Windows | install, remove, update, upgrade, list |

**Examples:**

<details>
<summary>📌 Install Python Package</summary>

```bash
curl -X POST "http://localhost:8000/package" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "manager": "pip",
    "action": "install",
    "package": "requests"
  }'
```
</details>

<details>
<summary>📌 Install System Package</summary>

```bash
curl -X POST "http://localhost:8000/package" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "manager": "apt",
    "action": "install",
    "package": "nginx"
  }'
```
</details>

<details>
<summary>📌 Update All Packages</summary>

```bash
curl -X POST "http://localhost:8000/package" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "manager": "apt",
    "action": "update"
  }'
```
</details>

---

## 📱 Application Control (`/apps`)

Manage desktop applications and system processes.

### Endpoint: `POST /apps`

**Request Model:**
```json
{
  "action": "launch|kill|list",
  "app": "string",
  "args": "string (optional)"
}
```

**Request Parameters:**
- `action` (string, required): Action to perform
- `app` (string, required): Application name or process
- `args` (string, optional): Arguments for launch action

### Platform-Specific Commands

| Platform | Launch | Kill | List |
|----------|--------|------|------|
| **Windows** | Direct execution | `taskkill /IM app /F` | `tasklist` |
| **Linux** | Direct execution | `pkill -f app` | `ps aux` |
| **macOS** | Direct execution | `pkill -f app` | `ps aux` |

**Examples:**

<details>
<summary>📌 Launch Application</summary>

```bash
curl -X POST "http://localhost:8000/apps" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "launch",
    "app": "firefox",
    "args": "--new-window https://google.com"
  }'
```
</details>

<details>
<summary>📌 Kill Application</summary>

```bash
curl -X POST "http://localhost:8000/apps" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "kill",
    "app": "firefox"
  }'
```
</details>

<details>
<summary>📌 List Running Applications</summary>

```bash
curl -X POST "http://localhost:8000/apps" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "list"
  }'
```
</details>

---

## 🔄 Code Refactoring (`/refactor`)

Perform search and replace operations across multiple files.

### Endpoint: `POST /refactor`

**Request Model:**
```json
{
  "search": "string",
  "replace": "string",
  "files": ["string"],
  "dry_run": false
}
```

**Request Parameters:**
- `search` (string, required): Text to search for
- `replace` (string, required): Replacement text
- `files` (array, required): List of file paths to process
- `dry_run` (boolean, optional): Preview changes without applying

**Response Model:**
```json
{
  "results": [
    {
      "file": "/path/to/file.py",
      "changed": true,
      "preview": "modified content preview..."
    }
  ]
}
```

**Examples:**

<details>
<summary>📌 Dry Run Refactoring</summary>

```bash
curl -X POST "http://localhost:8000/refactor" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "search": "oldVariableName",
    "replace": "newVariableName",
    "files": ["/home/user/src/main.py", "/home/user/src/utils.py"],
    "dry_run": true
  }'
```
</details>

<details>
<summary>📌 Apply Refactoring</summary>

```bash
curl -X POST "http://localhost:8000/refactor" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "search": "oldVariableName",
    "replace": "newVariableName",
    "files": ["/home/user/src/main.py", "/home/user/src/utils.py"],
    "dry_run": false
  }'
```
</details>

---

## 🔄 Batch Operations (`/batch`)

Execute multiple operations in a single request.

### Endpoint: `POST /batch`

**Request Model:**
```json
{
  "operations": [
    {
      "action": "string",
      "args": {}
    }
  ]
}
```

**Currently Supported Actions:**
- `shell` - Execute shell commands

**Response Model:**
```json
{
  "results": [
    {
      "action": "shell",
      "stdout": "command output",
      "stderr": "",
      "exit_code": 0
    }
  ]
}
```

**Examples:**

<details>
<summary>📌 Multi-Command Batch</summary>

```bash
curl -X POST "http://localhost:8000/batch" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "operations": [
      {
        "action": "shell",
        "args": {
          "command": "echo \"Starting deployment\""
        }
      },
      {
        "action": "shell",
        "args": {
          "command": "git pull origin main"
        }
      },
      {
        "action": "shell",
        "args": {
          "command": "python manage.py migrate"
        }
      },
      {
        "action": "shell",
        "args": {
          "command": "systemctl restart myapp"
        }
      }
    ]
  }'
```
</details>

---

## 🔧 Debug & Utility Endpoints

### List All Routes: `GET /debug/routes`

Get a list of all available API routes.

**Example:**
```bash
curl -X GET "http://localhost:8000/debug/routes" \
  -H "x-api-key: your_key"
```

**Response:**
```json
[
  "/shell",
  "/files",
  "/code",
  "/system",
  "/monitor",
  "/git",
  "/package",
  "/apps",
  "/refactor",
  "/batch",
  "/debug/routes"
]
```

### API Documentation

- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **OpenAPI Spec:** `http://localhost:8000/openapi.json`

---

## Error Handling

### Standard Error Response Format

```json
{
  "status_code": 400,
  "detail": "Error description"
}
```

### Common Error Codes

| Code | Description | Common Causes |
|------|-------------|---------------|
| **400** | Bad Request | Invalid parameters, malformed JSON |
| **403** | Forbidden | Missing or invalid API key |
| **404** | Not Found | File/path does not exist |
| **500** | Internal Server Error | System errors, command failures |

### Error Examples

<details>
<summary>📌 Authentication Error</summary>

**Request without API key:**
```bash
curl -X GET "http://localhost:8000/system"
```

**Response:**
```json
{
  "status_code": 403,
  "detail": "Invalid API key"
}
```
</details>

<details>
<summary>📌 File Not Found</summary>

**Request:**
```bash
curl -X POST "http://localhost:8000/files" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "action": "read",
    "path": "/nonexistent/file.txt"
  }'
```

**Response:**
```json
{
  "status_code": 500,
  "detail": "[Errno 2] No such file or directory: '/nonexistent/file.txt'"
}
```
</details>

---

## Rate Limits & Quotas

### Current Limits (🚧 To Be Implemented)

| Endpoint Category | Requests/Minute | Requests/Hour |
|-------------------|-----------------|---------------|
| **Read Operations** | 1000 | 10000 |
| **Write Operations** | 300 | 3000 |
| **Shell Execution** | 100 | 1000 |
| **System Operations** | 500 | 5000 |

### Usage Headers (🚧 Planned)

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

---

**This comprehensive API reference provides complete documentation for all endpoints, with practical examples and detailed explanations to enable effective integration with GPT agents and other automated systems.**
