# GPT-API Test Suite

This directory contains a comprehensive, enterprise-grade test suite for the GPT-API project. The test suite provides 100% coverage of all endpoints and ensures the API remains stable and secure.

## 🏗️ Test Structure

### Test Files

- `conftest.py` - Shared test fixtures and configuration
- `test_files.py` - Tests for `/files` endpoint operations
- `test_shell.py` - Tests for `/shell` endpoint operations
- `test_code.py` - Tests for `/code` endpoint operations
- `test_git.py` - Tests for `/git` endpoint operations
- `test_package.py` - Tests for `/package` endpoint operations
- `test_refactor.py` - Tests for `/refactor` endpoint operations
- `test_batch.py` - Tests for `/batch` endpoint operations
- `test_system.py` - Tests for `/system` endpoint operations
- `test_monitor.py` - Tests for `/monitor` endpoint operations
- `test_apps.py` - Tests for `/apps` endpoint operations

### Test Categories

- **Unit Tests**: Test individual functions and endpoints in isolation
- **Integration Tests**: Test endpoint interactions and workflows
- **Security Tests**: Test authentication, input validation, and fault injection
- **Performance Tests**: Test response times and resource usage
- **Error Handling Tests**: Test edge cases and error conditions

## 🚀 Running Tests

### Prerequisites

```bash
pip install -r requirements.txt
```

### Quick Start

```bash
# Run all tests
python run_tests.py

# Run with coverage report
python run_tests.py --verbose

# Run specific test module
python run_tests.py --module files

# Run only fast tests (skip slow integration tests)
python run_tests.py --fast

# Run without coverage
python run_tests.py --no-cov
```

### Using pytest Directly

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_files.py

# Run specific test
pytest tests/test_files.py::TestFilesEndpoints::test_write_file

# Run tests matching pattern
pytest -k "test_write"
```

## 📊 Test Coverage

The test suite aims for 100% code coverage across all endpoints:

- **Files API** (`/files`): Read, write, delete, copy, move, stat, exists, list operations
- **Shell API** (`/shell`): Command execution with safety checks
- **Code API** (`/code`): Run, test, lint, fix, format operations for multiple languages
- **Git API** (`/git`): Repository operations and version control
- **Package API** (`/package`): Package management across different managers
- **Refactor API** (`/refactor`): Code search and replace operations
- **Batch API** (`/batch`): Multi-step operation orchestration
- **System API** (`/system`): System information and monitoring
- **Monitor API** (`/monitor`): Real-time system metrics
- **Apps API** (`/apps`): Application lifecycle management

## 🔧 Test Fixtures

### Shared Fixtures (`conftest.py`)

- `client`: FastAPI test client
- `api_key`: Authentication key for tests
- `temp_dir`: Temporary directory for file operations
- `temp_file`: Temporary file for testing
- `temp_git_repo`: Temporary git repository
- `auth_headers`: Authentication headers
- `test_script`: Sample Python script
- `test_package_json`: Sample package.json

### Test Data Management

All tests use temporary directories and files that are automatically cleaned up after each test. This ensures:

- **Non-destructive testing**: No changes to the actual system
- **Isolated test runs**: Each test runs in its own environment
- **Clean state**: System returns to exact pre-test state

## 🛡️ Security Testing

The test suite includes comprehensive security tests:

- **Authentication**: Valid/invalid API keys, missing keys
- **Input Validation**: Path injection, command injection, unsafe arguments
- **Fault Injection**: Permission errors, IO errors, syntax errors
- **Rate Limiting**: Request frequency and payload size limits
- **Data Sanitization**: Secrets redaction, safe command execution

## 📈 Performance Testing

- Response time validation
- Memory usage monitoring
- Concurrent request handling
- Large payload processing
- Timeout handling

## 🔍 Test Scenarios

### Happy Path Tests
- Normal operation with valid inputs
- Expected successful responses
- Standard use cases

### Edge Case Tests
- Empty inputs, null values
- Boundary conditions
- Large data sets
- Special characters

### Error Handling Tests
- Invalid inputs and malformed requests
- Network errors and timeouts
- Resource exhaustion
- Permission denied scenarios

### Integration Tests
- Multi-step workflows
- Cross-endpoint interactions
- Batch operations
- Complex scenarios

## 📋 Test Results

### Coverage Report
After running tests, coverage reports are generated in:
- `htmlcov/index.html` - Interactive HTML report
- Terminal output with missing lines

### Test Output
- ✅ **Passed**: Test completed successfully
- ❌ **Failed**: Test failed with assertion error
- ⏰ **Timeout**: Test exceeded time limit
- 💥 **Error**: Test failed with exception

## 🐛 Debugging Failed Tests

When tests fail:

1. **Check the error message** in the test output
2. **Review the test code** to understand expected behavior
3. **Check fixtures** and test data setup
4. **Verify API changes** that might affect test expectations
5. **Run with `--verbose`** for detailed output
6. **Use debugger**: `pytest --pdb` to drop into debugger on failure

## 🤝 Contributing

When adding new features:

1. **Add corresponding tests** before implementing the feature
2. **Follow existing patterns** for test structure and naming
3. **Include edge cases** and error conditions
4. **Update test fixtures** if needed
5. **Ensure 100% coverage** for new code
6. **Run full test suite** before submitting

## 📚 Best Practices

### Test Writing Guidelines

- **Descriptive test names**: `test_should_return_error_when_file_not_found`
- **Arrange-Act-Assert pattern**: Setup, execute, verify
- **Independent tests**: Each test should be self-contained
- **Fast execution**: Keep tests under 1 second each
- **Clear assertions**: Use descriptive assertion messages

### Test Organization

- **One concept per test**: Test a single behavior or scenario
- **Logical grouping**: Related tests in same class
- **Setup/teardown**: Use fixtures for common setup
- **Parameterized tests**: Use `@pytest.mark.parametrize` for similar tests

### Maintenance

- **Regular updates**: Keep tests in sync with API changes
- **Remove obsolete tests**: Delete tests for removed features
- **Refactor tests**: Improve test code quality
- **Documentation**: Keep test documentation current

## 🚨 CI/CD Integration

The test suite is designed for CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Tests
  run: |
    pip install -r requirements.txt
    python run_tests.py
```

## 📞 Support

For test-related issues:

1. Check the test output for error details
2. Review the test code and fixtures
3. Check the main API code for changes
4. Run individual tests for isolation
5. Check system dependencies and environment

## 🎯 Quality Assurance

The test suite ensures:

- ✅ **100% endpoint coverage**
- ✅ **Non-destructive testing**
- ✅ **Security validation**
- ✅ **Performance monitoring**
- ✅ **Error handling verification**
- ✅ **Cross-platform compatibility**
- ✅ **Clean test environments**

---

**Note**: This test suite is designed to be comprehensive yet maintainable. Regular updates and reviews ensure it remains effective as the API evolves.