# GPT Super-Agent Universal Control API

![Version](https://img.shields.io/badge/version-4.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.13+-green.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-red.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)

A powerful FastAPI-based system control API designed for GPT agents to perform comprehensive system operations including file management, shell execution, code operations, package management, and more.

## 🚀 Features

- **🔐 Secure Authentication** - API key-based authentication for all endpoints
- **💻 Shell Command Execution** - Execute system commands with sudo, background, and custom shell support
- **📁 File Operations** - Complete file system management (read, write, delete, copy, move, stat)
- **⚡ Code Operations** - Run, test, lint, format, and analyze code in multiple languages
- **📦 Package Management** - Universal package manager support (pip, npm, apt, brew, winget, etc.)
- **🌐 Git Integration** - Full Git repository management and operations
- **📱 Application Control** - Launch, kill, and manage desktop applications
- **🔄 Code Refactoring** - Search and replace across multiple files with dry-run support
- **📊 System Monitoring** - Real-time system metrics and resource monitoring
- **🔄 Batch Operations** - Execute multiple operations in a single request

## 📋 Prerequisites

- Python 3.13+
- pip (Python package manager)
- Operating System: Windows, macOS, or Linux
- **Optional:** PostgreSQL 12+ (for assistant management features)

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Coding-Krakken/GPT-API.git
   cd GPT-API
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   **Optional - For assistant management features:**
   ```bash
   pip install psycopg2-binary sqlalchemy
   ```

3. **Set up environment variables:**
   Create a `.env` file in the root directory:
   ```env
   API_KEY=your_secure_api_key_here
   API_HOST=127.0.0.1
   API_PORT=8000
   ```

## 🚀 Quick Start

### Start the API Server

**Using the CLI wrapper:**
```bash
python cli.py
```

**Using uvicorn directly:**
```bash
source .venv/bin/activate.fish
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://127.0.0.1:8000`

### Access API Documentation
- **Swagger UI:** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`
- **OpenAPI Spec:** `http://127.0.0.1:8000/openapi.json`

## 📚 API Endpoints

### 🔐 Authentication
All requests require the `x-api-key` header:
```bash
curl -H "x-api-key: your_api_key_here" ...
```

### 💻 Shell Operations (`/shell`)
Execute system commands with advanced options:

```json
POST /shell
{
  "command": "ls -la",
  "run_as_sudo": false,
  "background": false,
  "shell": "/bin/bash"
}
```

**Response:**
```json
{
  "stdout": "total 48\ndrwxr-xr-x...",
  "stderr": "",
  "exit_code": 0
}
```

### 📁 File Operations (`/files`)
Comprehensive file system management:

```json
POST /files
{
  "action": "read|write|delete|copy|move|stat|exists|list",
  "path": "/path/to/file",
  "target_path": "/target/path",  // for copy/move
  "content": "file content",      // for write
  "recursive": true               // for delete/copy
}
```

**Example - Read a file:**
```bash
curl -X POST "http://localhost:8000/files" \
  -H "x-api-key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"action": "read", "path": "example.txt"}'
```

### ⚡ Code Operations (`/code`)
Execute, test, and analyze code:

```json
POST /code
{
  "action": "run|test|lint|format|fix|explain",
  "path": "/path/to/code.py",
  "language": "python|javascript|bash|node",
  "args": "--verbose"
}
```

**Supported Languages:**
- **Python:** run, test (pytest), lint (flake8), format (black), fix (autopep8)
- **JavaScript:** run (node), test (npm test), lint/fix (eslint), format (prettier)
- **Bash:** run with bash interpreter

### 📊 System Monitoring (`/system`)
Get comprehensive system information:

```bash
GET /system
```

**Response includes:**
- OS information and platform details
- CPU cores, threads, and usage percentage
- Memory total and usage statistics
- Disk usage percentage
- System uptime and current user

### 📊 Real-time Monitoring (`/monitor`)
Monitor system resources in real-time:

```json
POST /monitor
{
  "type": "cpu|memory|disk|network",
  "live": false
}
```

### 🌐 Git Operations (`/git`)
Complete Git repository management:

```json
POST /git
{
  "action": "status|add|commit|push|pull|clone|diff|log",
  "path": "/repo/path",
  "args": "-m 'commit message'"
}
```

### 📦 Package Management (`/package`)
Universal package manager support:

```json
POST /package
{
  "manager": "pip|npm|apt|pacman|brew|winget",
  "action": "install|remove|update|upgrade|list",
  "package": "package-name"
}
```


### 📱 Application Control (`/apps`)
Manage desktop applications:

```json
POST /apps
{
  "action": "launch|kill|list",
  "app": "firefox|notepad|code", // required for launch/kill, optional for list
  "args": "--new-window"
}
```

**Note:** For the `list` action, the `app` field is optional and can be omitted from the request body.

### 🔄 Code Refactoring (`/refactor`)
Search and replace across multiple files:

```json
POST /refactor
{
  "search": "oldVariableName",
  "replace": "newVariableName",
  "files": ["src/main.py", "src/utils.py"],
  "dry_run": true
}
```

### 🔄 Batch Operations (`/batch`)
Execute multiple operations in sequence:

```json
POST /batch
{
  "operations": [
    {
      "action": "shell",
      "args": {"command": "echo 'Starting batch'"}
    },
    {
      "action": "shell", 
      "args": {"command": "python --version"}
    }
  ]
}
```

## 🏗️ Project Structure

```
GPT-API/
├── main.py                 # FastAPI application setup
├── cli.py                  # Command-line interface
├── requirements.txt        # Python dependencies
├── openapi.yaml           # OpenAPI specification
├── .env                   # Environment variables (create this)
├── routes/                # API route modules
│   ├── __init__.py
│   ├── shell.py          # Shell command execution
│   ├── files.py          # File operations
│   ├── code.py           # Code execution and analysis
│   ├── system.py         # System information
│   ├── monitor.py        # Real-time monitoring
│   ├── git.py            # Git operations
│   ├── package.py        # Package management
│   ├── apps.py           # Application control
│   ├── refactor.py       # Code refactoring
│   └── batch.py          # Batch operations
├── utils/                # Utility modules
│   └── auth.py          # Authentication utilities
├── database/             # Database layer for data persistence
│   ├── __init__.py      # Package initialization
│   ├── db.py            # Database connection and session management
│   ├── models.py        # SQLAlchemy data models (Assistant, Thread, etc.)
│   └── init_db.py       # Database initialization and schema setup
└── assistants/          # GPT assistant utilities (optional)
    ├── create_assistant.py
    ├── thread_ops.py
    └── ...
```

## �️ Database Layer

The `database/` directory provides data persistence for the GPT-API system, specifically designed to manage OpenAI GPT Assistants and related metadata.

### Database Components

- **`db.py`** - Database connection management using SQLAlchemy
- **`models.py`** - Data models defining the schema for assistants and threads
- **`init_db.py`** - Database initialization and schema setup utilities
- **`__init__.py`** - Package initialization and exports

### Database Schema

**Assistants Table:**
- `id` (VARCHAR) - OpenAI Assistant ID
- `name` (VARCHAR) - Assistant display name
- `instructions` (TEXT) - System instructions for the assistant
- `model` (VARCHAR) - GPT model version (e.g., gpt-4, gpt-3.5-turbo)
- `tools` (JSON) - Enabled tools and capabilities
- `file_ids` (ARRAY) - Associated file identifiers

**Threads Table:**
- `id` (VARCHAR) - OpenAI Thread ID
- `assistant_id` (VARCHAR) - Foreign key to assistants table
- `metadata` (JSON) - Thread configuration and context
- `created_at` (TIMESTAMP) - Creation timestamp
- `updated_at` (TIMESTAMP) - Last modification timestamp

### Database Configuration

The system uses PostgreSQL as the primary database:

```env
# Database Configuration (add to .env)
DB_NAME=gpt_system
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432
```

### Database Operations

The database layer supports:
- **Assistant Management** - CRUD operations for GPT assistants
- **Thread Management** - Conversation thread persistence
- **Metadata Storage** - Configuration and usage tracking
- **Relationship Management** - Assistant-thread associations

### Setup Requirements

To use the database functionality:

1. **Install PostgreSQL** (if not already installed)
2. **Create the database:**
   ```sql
   CREATE DATABASE gpt_system;
   ```
3. **Install Python dependencies:**
   ```bash
   pip install psycopg2-binary sqlalchemy
   ```
4. **Initialize the database schema:**
   ```python
   from database.init_db import initialize_database
   initialize_database()
   ```

**Note:** The database layer is optional and primarily used by the `/assistants` endpoints. The core API functionality works independently without database setup.

## �🔧 Configuration

### Environment Variables
Create a `.env` file with the following variables:

```env
# API Configuration
API_KEY=your_secure_random_api_key_here
API_HOST=127.0.0.1
API_PORT=8000

# Optional: Database Configuration (for assistant management)
DB_NAME=gpt_system
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=5432

# Optional: Additional configuration
LOG_LEVEL=INFO
CORS_ORIGINS=*
```

### Security Considerations
- **API Key**: Use a strong, randomly generated API key
- **CORS**: Configure appropriate CORS origins for production
- **Firewall**: Restrict access to necessary IP addresses
- **HTTPS**: Use HTTPS in production environments


## 🧪 Testing

Run the comprehensive test suite for full API coverage:

```bash
# Run all tests (recommended)
python -m pytest

# Run the full API coverage suite
python test_full_api.py

# Run specific test file
python test_api.py

# Run legacy comprehensive tests
python comprehensive_test.py
```

The `test_full_api.py` script provides automated, assertion-based coverage for all endpoints, HTTP methods, authentication scenarios, error cases, and system side effects. It is recommended for validating the integrity of your deployment after any change.

## 📖 Usage Examples

### Example 1: File Management
```python
import requests

headers = {"x-api-key": "your_api_key"}
base_url = "http://localhost:8000"

# Read a file
response = requests.post(f"{base_url}/files", 
    headers=headers,
    json={"action": "read", "path": "example.txt"})

# Write to a file
response = requests.post(f"{base_url}/files",
    headers=headers, 
    json={
        "action": "write", 
        "path": "output.txt", 
        "content": "Hello, World!"
    })
```

### Example 2: System Information
```python
# Get system info
response = requests.get(f"{base_url}/system", headers=headers)
system_info = response.json()
print(f"OS: {system_info['os']}")
print(f"CPU Usage: {system_info['cpu_usage_percent']}%")
```

### Example 3: Code Execution
```python
# Run a Python script
response = requests.post(f"{base_url}/code",
    headers=headers,
    json={
        "action": "run",
        "path": "script.py",
        "language": "python",
        "args": "--verbose"
    })
```

## 🔍 Debugging

### Debug Routes
Get a list of all available routes:
```bash
GET /debug/routes
```

### Common Issues

1. **403 Forbidden**: Check your API key in the `x-api-key` header
2. **500 Internal Server Error**: Check file paths and permissions
3. **Module Import Errors**: Ensure all dependencies are installed

### Logging
Enable detailed logging by setting the environment variable:
```bash
export LOG_LEVEL=DEBUG
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/Coding-Krakken/GPT-API/issues)
- **Documentation**: Check the `/docs` endpoint when running the server
- **API Reference**: Available at `/redoc` when running the server

## 🎯 Use Cases

This API is perfect for:

- **GPT Agent Integration**: Full system control for AI agents
- **DevOps Automation**: Automated deployment and system management
- **Remote System Administration**: Secure remote system control
- **Development Tools**: Code execution, testing, and analysis
- **System Monitoring**: Real-time system metrics and alerts
- **Batch Processing**: Automated multi-step operations

---

**Made with ❤️ for the GPT community**
