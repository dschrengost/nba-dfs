# Test Directory

This directory contains the comprehensive test suite for the NBA-DFS pipeline, covering unit tests, integration tests, and fixtures for all Python modules.

## Overview

- **Framework**: pytest with coverage reporting
- **Structure**: Mirror of source code structure
- **Fixtures**: Reusable test data in `tests/fixtures/`
- **Coverage**: Target >80% code coverage across modules

## Directory Structure

```
tests/
├── fixtures/           # Test data and sample files
│   └── dk/            # DraftKings sample data
├── pipeline/          # Pipeline module tests
├── processes/         # Process module tests
└── README.md          # This file
```

## Running Tests

```bash
# All tests
pytest -q

# Specific module
pytest tests/pipeline/ -v

# With coverage
pytest --cov

# Specific test file
pytest tests/pipeline/test_ingest.py -v
```

## Test Categories

### Unit Tests
- Individual function/class testing
- Mock external dependencies
- Fast execution (<1s per test)

### Integration Tests  
- End-to-end workflow testing
- Real file I/O operations
- Database and parquet interactions

### Fixtures
- Sample CSV files for ingestion testing
- Known-good parquet files for validation
- Configuration examples for process testing

## Writing Tests

Follow pytest conventions:
```python
def test_function_name():
    # Arrange
    input_data = create_test_data()
    
    # Act  
    result = function_under_test(input_data)
    
    # Assert
    assert result.success is True
    assert len(result.data) == expected_count
```