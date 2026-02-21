# Testing Guide - Data Explorer

Complete guide to testing the Data Explorer application.

---

## Table of Contents
1. [Quick Start](#quick-start)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Writing New Tests](#writing-new-tests)
5. [Coverage Analysis](#coverage-analysis)
6. [Continuous Integration](#continuous-integration)
7. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Install Test Dependencies
```bash
pip install -r requirements.txt
```

This installs:
- `pytest>=7.4.0` - Test framework
- `pytest-cov>=4.1.0` - Coverage reporting
- `pytest-mock>=3.12.0` - Mocking utilities

### Run All Tests
```bash
pytest
```

### Run with Coverage Report
```bash
pytest --cov=src --cov-report=html
```

View coverage: Open `htmlcov/index.html` in browser

---

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                    # Shared fixtures
├── test_pennsieve_agent.py        # Pennsieve CLI wrapper tests
├── test_openneuro_agent.py        # OpenNeuro API tests
├── test_metadata_filter.py        # Metadata filtering tests
├── test_automated_qc.py           # Automated QC tests
└── test_integration.py            # End-to-end workflow tests
```

### Test Organization

#### Unit Tests
- **File Pattern**: `test_<module_name>.py`
- **Purpose**: Test individual functions/classes in isolation
- **Location**: One file per source module
- **Mocking**: Heavy use of mocks for external dependencies

#### Integration Tests
- **File**: `test_integration.py`
- **Purpose**: Test interactions between modules
- **Scope**: Database, workflows, data pipelines
- **Mocking**: Minimal, uses real database (SQLite)

---

## Running Tests

### All Tests (Default)
```bash
pytest
```

**Output**: Verbose with coverage report

### Specific Test File
```bash
pytest tests/test_automated_qc.py
```

### Specific Test Class
```bash
pytest tests/test_automated_qc.py::TestAutomatedQC
```

### Specific Test Function
```bash
pytest tests/test_automated_qc.py::TestAutomatedQC::test_run_subject_qc_pass
```

### Quick Mode (No Coverage)
```bash
pytest -q --no-cov
```

### Verbose Output
```bash
pytest -vv
```

### Show Print Statements
```bash
pytest -s
```

### Stop on First Failure
```bash
pytest -x
```

### Run Last Failed Tests
```bash
pytest --lf
```

### Run Tests by Marker
```bash
pytest -m unit          # Run unit tests only
pytest -m integration   # Run integration tests only
pytest -m "not slow"    # Skip slow tests
```

### Parallel Execution (Future)
```bash
pip install pytest-xdist
pytest -n auto          # Auto-detect CPU cores
```

---

## Writing New Tests

### Basic Test Structure

```python
"""
Unit tests for MyModule.
"""

import pytest
from unittest.mock import Mock, patch
from src.my_module import MyClass


class TestMyClass:
    """Test suite for MyClass."""
    
    def test_basic_functionality(self):
        """Test basic feature."""
        obj = MyClass()
        result = obj.my_method()
        assert result == expected_value
    
    @patch('src.my_module.external_dependency')
    def test_with_mock(self, mock_dep):
        """Test with mocked dependency."""
        mock_dep.return_value = "mocked"
        obj = MyClass()
        result = obj.method_using_dependency()
        assert result == "expected"
        mock_dep.assert_called_once()
```

### Using Shared Fixtures

Available in `conftest.py`:

```python
def test_with_temp_dir(temp_dir):
    """Test using temporary directory."""
    file_path = temp_dir / "test.txt"
    file_path.write_text("data")
    assert file_path.exists()

def test_with_bids_structure(sample_bids_structure):
    """Test with BIDS dataset structure."""
    participants_file = sample_bids_structure / "participants.tsv"
    assert participants_file.exists()

def test_with_pennsieve_env(mock_pennsieve_env):
    """Test with Pennsieve credentials."""
    assert mock_pennsieve_env['PENNSIEVE_API_KEY'] == 'test_key_12345'
```

### Parameterized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("ds000246", True),
    ("ds123456", True),
    ("invalid", False),
    ("DS000246", False),  # Uppercase
])
def test_validate_dataset_id(input, expected):
    """Test dataset ID validation with multiple inputs."""
    from src.openneuro_agent import OpenNeuroAgent
    agent = OpenNeuroAgent()
    assert agent.validate_dataset_id(input) == expected
```

### Testing Exceptions

```python
def test_raises_error():
    """Test that function raises expected error."""
    with pytest.raises(ValueError, match="Invalid input"):
        my_function(invalid_input)
```

### Mocking External APIs

```python
@patch('requests.post')
def test_api_call(mock_post):
    """Test API interaction."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {'data': 'value'}
    mock_post.return_value = mock_response
    
    result = my_api_function()
    assert result['data'] == 'value'
```

---

## Coverage Analysis

### Generate HTML Coverage Report
```bash
pytest --cov=src --cov-report=html
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

### Terminal Coverage Report
```bash
pytest --cov=src --cov-report=term-missing
```

### Coverage by Module
```bash
pytest --cov=src.automated_qc --cov-report=term
```

### Set Minimum Coverage Threshold
```bash
pytest --cov=src --cov-fail-under=80
```

**Current Project Threshold**: 20% (configured in `pytest.ini`)

### Coverage Goals

| Module | Current | Target |
|--------|---------|--------|
| automated_qc.py | 89% | ✅ Maintain |
| metadata_filter.py | 84% | ✅ Maintain |
| openneuro_agent.py | 45% | 60% |
| pennsieve_agent.py | 20% | 40% |
| database.py | 28% | 50% |

---

## Test Markers

### Available Markers

Defined in `pytest.ini` and `conftest.py`:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.slow` - Tests taking >1 second
- `@pytest.mark.database` - Tests using database
- `@pytest.mark.api` - Tests calling external APIs

### Using Markers

```python
@pytest.mark.unit
def test_simple_function():
    """Quick unit test."""
    pass

@pytest.mark.integration
@pytest.mark.database
def test_database_workflow():
    """Integration test with database."""
    pass

@pytest.mark.slow
@pytest.mark.api
def test_external_download():
    """Slow test calling external API."""
    pass
```

### Running by Marker
```bash
pytest -m unit              # Only unit tests
pytest -m "integration"     # Only integration tests
pytest -m "not slow"        # Exclude slow tests
pytest -m "unit and not api"  # Unit tests without API calls
```

---

## Continuous Integration

### GitHub Actions Example

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.12'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run tests
      run: |
        pytest --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

### Pre-commit Hook

Create `.git/hooks/pre-commit`:

```bash
#!/bin/bash
echo "Running tests before commit..."
pytest -q --tb=no
if [ $? -ne 0 ]; then
    echo "Tests failed. Commit aborted."
    exit 1
fi
echo "All tests passed!"
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

---

## Troubleshooting

### Common Issues

#### 1. Import Errors
**Error**: `ModuleNotFoundError: No module named 'src'`

**Solution**:
```python
# Add to top of test file
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

#### 2. Mock Not Working
**Error**: `AttributeError: does not have the attribute`

**Solution**: Patch where object is used, not where it's defined
```python
# Wrong
@patch('src.pennsieve_agent.subprocess')

# Correct
@patch('subprocess.run')
```

#### 3. Database Locked
**Error**: `sqlite3.OperationalError: database is locked`

**Solution**: Use temporary database for tests
```python
@pytest.fixture
def temp_db(temp_dir):
    db_path = temp_dir / "test.db"
    db = Database(str(db_path))
    yield db
    db.close()
```

#### 4. Tests Pass Locally, Fail in CI
**Common Causes**:
- Environment variables not set
- File permissions
- OS-specific paths

**Solution**: Use `Path` from `pathlib` for cross-platform paths

#### 5. Slow Test Runs
**Solution**: Run without coverage during development
```bash
pytest --no-cov -q
```

---

## Best Practices

### 1. Test Naming
- Use descriptive names: `test_filter_by_age_range_returns_correct_subjects`
- Group related tests in classes: `TestMetadataFilter`
- Prefix with `test_` for auto-discovery

### 2. Test Independence
- Each test should be independent
- Use fixtures for setup/teardown
- Don't rely on test execution order

### 3. Assertions
- One logical assertion per test (when possible)
- Use descriptive assertion messages:
  ```python
  assert result == expected, f"Expected {expected}, got {result}"
  ```

### 4. Mocking Strategy
- Mock external dependencies (APIs, CLI, filesystem)
- Don't mock internal logic
- Use real objects when possible (e.g., SQLite database)

### 5. Test Data
- Use fixtures for reusable test data
- Keep test data minimal and focused
- Use realistic but not production data

### 6. Documentation
- Add docstrings to test functions
- Explain what behavior is being tested
- Document expected edge cases

---

## Testing Checklist

Before committing code:

- [ ] All tests pass locally
- [ ] New code has corresponding tests
- [ ] Coverage hasn't decreased significantly
- [ ] Tests are independent and don't rely on order
- [ ] Test names are descriptive
- [ ] Edge cases are covered
- [ ] Error handling is tested
- [ ] No print statements or debug code
- [ ] Fixtures are used for common setup

---

## Additional Resources

### Pytest Documentation
- Official docs: https://docs.pytest.org/
- Best practices: https://docs.pytest.org/en/latest/goodpractices.html
- Fixtures: https://docs.pytest.org/en/latest/fixture.html

### Python Testing
- unittest.mock: https://docs.python.org/3/library/unittest.mock.html
- pytest-cov: https://pytest-cov.readthedocs.io/

### Project-Specific
- See `TEST_REPORT.md` for current test status
- See `conftest.py` for available fixtures
- See `pytest.ini` for configuration

---

## Getting Help

- Check test output: `pytest -vv`
- View detailed failures: `pytest --tb=long`
- Debug specific test: Add `import pdb; pdb.set_trace()` in test
- Ask team: Post in #testing channel

---

**Last Updated**: February 5, 2026  
**Maintained by**: Data Explorer Team
