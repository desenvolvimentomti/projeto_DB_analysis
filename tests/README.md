# Test Suite for Climate ETL

This folder contains all unit tests and integration tests for the climate ETL module.

## Structure

- **test_climate_etl.py**: Main test file for climate ETL functions
- **conftest.py**: Shared pytest fixtures and configuration
- **__init__.py**: Package initialization file

## Running Tests

### Run all tests
```bash
pytest
```

### Run with verbose output
```bash
pytest -v
```

### Run specific test file
```bash
pytest tests/test_climate_etl.py
```

### Run specific test class
```bash
pytest tests/test_climate_etl.py::TestProcessClimateData
```

### Run specific test function
```bash
pytest tests/test_climate_etl.py::TestProcessClimateData::test_process_climate_data
```

### Run tests with coverage
```bash
pytest --cov=climate_etl --cov-report=html
```

### Run only async tests
```bash
pytest -m asyncio
```

### Run tests excluding slow tests
```bash
pytest -m "not slow"
```

### Run without Earth Engine API calls (mocked)
```bash
pytest -k "not era5"  # Skip ERA5 tests that call real API
```

## Note on Earth Engine Tests

Tests that call Earth Engine API (like `test_process_climate_data`) will be skipped or mocked if:
- `.env` file is not configured
- `GEE_SERVICE_ACCOUNT_JSON_PATH` is not set
- Earth Engine cannot be initialized

See [Earth Engine Authentication Guide](../EARTH_ENGINE_AUTH.md) to enable full testing with real Earth Engine API.

## Test Categories

### 1. Model Validation Tests (`TestERA5ExtractParams`, `TestOpenMeteoDownloadParams`)
- Validate Pydantic models for parameter validation
- Test default values and required fields

### 2. Data Loading Tests (`TestDataLoading`)
- Test loading centroid data from CSV and Shapefile formats
- Validate data structure and required columns

### 3. Transformation Tests (`TestDataTransformations`)
- Test Kelvin to Celsius conversions
- Test meters to millimeters conversions
- Verify transformations on DataFrames

### 4. Climate Data Processing Tests (`TestProcessClimateData`)
- Test ERA5 data processing with transformations
- Verify output file creation
- Validate that transformations are applied correctly

### 5. Data Structure Tests (`TestDataStructure`)
- Test that processed data has required columns
- Validate centroid data structure

### 6. Error Handling Tests (`TestErrorHandling`)
- Test handling of missing files
- Test handling of invalid date ranges
- Test processing of empty files

### 7. Variable Constant Tests (`TestERA5Variables`)
- Verify ERA5 variables list integrity
- Check for known variables (temperature, precipitation)
- Ensure no duplicates

### 8. Mock API Tests (`TestMockAPIs`)
- Test with mocked Earth Engine API
- Test with mocked HTTP sessions

### 9. Data Quality Tests (`TestDataQuality`)
- Validate no null values in required columns
- Check value ranges are reasonable
- Verify data integrity

## Fixtures

### `temp_dir`
Creates a temporary directory for test files and cleans up after the test.

### `sample_centroids_csv`
Creates a sample CSV file with centroid coordinates (3 points in Brazil).

### `sample_centroids_shp`
Creates a sample shapefile with centroid coordinates.

### `era5_extract_params`
Creates sample ERA5 extraction parameters.

### `openmeteo_download_params`
Creates sample Open-Meteo download parameters.

### `climate_process_params`
Creates sample climate processing parameters with dummy parquet files.

## Dependencies

Tests require the following packages (already in requirements.txt):
- `pytest`
- `pytest-asyncio`
- `pandas`
- `geopandas`
- `numpy`

## Configuration

The `pytest.ini` file configures:
- Test discovery paths (tests folder)
- Asyncio mode for async tests
- Custom markers for test categorization
- Default output format

## Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Fixtures**: Use pytest fixtures for setup and teardown
3. **Mocking**: Mock external APIs to avoid network calls
4. **Assertions**: Use clear, specific assertions
5. **Documentation**: Document complex test logic with comments
6. **Naming**: Use descriptive test names that explain what is being tested

## Continuous Integration

This test suite is designed to work with CI/CD pipelines. Tests can be run automatically when code is pushed to the repository.

Example GitHub Actions workflow:
```yaml
- name: Run tests
  run: pytest --cov=climate_etl
```
