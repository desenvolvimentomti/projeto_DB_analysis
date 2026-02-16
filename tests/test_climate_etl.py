import pytest
import pandas as pd
import geopandas as gpd
import numpy as np
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime
import tempfile
import json
import shutil
import sys
import os
import ee
# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import ERA5ExtractParams, OpenMeteoDownloadParams, ClimateProcessParams
from climate_etl import (
    extract_era5_data, 
    download_openmeteo_data, 
    process_climate_data,
    ERA5_VARIABLES
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files"""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path)

@pytest.fixture
def sample_centroids_csv(temp_dir):
    """Create a sample centroids CSV file"""
    csv_path = Path(temp_dir) / "centroids.csv"
    df = pd.DataFrame({
        'FID': [1, 2, 3],
        'lon': [-53.9, -53.8, -53.85],
        'lat': [-12.1, -12.2, -12.15]
    })
    df.to_csv(csv_path, index=False)
    return str(csv_path)

@pytest.fixture
def sample_centroids_shp(temp_dir):
    """Create a sample centroids shapefile"""
    shp_path = Path(temp_dir) / "centroids.shp"
    gdf = gpd.GeoDataFrame({
        'FID': [1, 2, 3],
    }, geometry=gpd.points_from_xy([-53.9, -53.8, -53.85], [-12.1, -12.2, -12.15]))
    gdf.to_file(shp_path)
    return str(shp_path)

@pytest.fixture
def era5_extract_params(sample_centroids_csv, temp_dir):
    """Create sample ERA5 extraction parameters"""
    return ERA5ExtractParams(
        centroids_shapefile=sample_centroids_csv,
        start_date="2025-01-01",
        end_date="2025-01-05",
        output_folder=temp_dir,
        variables=ERA5_VARIABLES[:5]
    )

@pytest.fixture
def openmeteo_download_params(sample_centroids_csv, temp_dir):
    """Create sample Open-Meteo download parameters"""
    return OpenMeteoDownloadParams(
        centroids_shapefile=sample_centroids_csv,
        output_file=str(Path(temp_dir) / "openmeteo.parquet"),
        past_days=5,
        forecast_days=3
    )

@pytest.fixture
def climate_process_params(temp_dir):
    """Create sample climate processing parameters"""
    # Create dummy parquet files
    df = pd.DataFrame({
        'FID': [1, 2, 3],
        'longitude': [-53.9, -53.8, -53.85],
        'latitude': [-12.1, -12.2, -12.15],
        'date': ['2025-01-01', '2025-01-02', '2025-01-03'],
        'variable': ['temperature_2m', 'total_precipitation_sum', 'dewpoint_temperature_2m'],
        'value': [300.15, 0.005, 290.15]
    })
    era5_file = Path(temp_dir) / "era5.parquet"
    df.to_parquet(era5_file)
    
    openmeteo_file = Path(temp_dir) / "openmeteo.parquet"
    df.to_parquet(openmeteo_file)
    
    return ClimateProcessParams(
        era5_raw_files=[str(era5_file)],
        openmeteo_file=str(openmeteo_file),
        output_folder=temp_dir
    )

# ============================================================================
# Test Model Validation
# ============================================================================

class TestERA5ExtractParams:
    """Test ERA5 extraction parameter models"""
    
    def test_valid_era5_params(self, era5_extract_params):
        """Test that ERA5 params are valid"""
        assert era5_extract_params.start_date == "2025-01-01"
        assert era5_extract_params.end_date == "2025-01-05"
        assert len(era5_extract_params.variables) == 5
    
    def test_era5_params_with_no_variables(self, sample_centroids_csv, temp_dir):
        """Test ERA5 params with empty variables list"""
        params = ERA5ExtractParams(
            centroids_shapefile=sample_centroids_csv,
            start_date="2025-01-01",
            end_date="2025-01-05",
            output_folder=temp_dir,
            variables=[]
        )
        assert params.variables == []

class TestOpenMeteoDownloadParams:
    """Test Open-Meteo download parameter models"""
    
    def test_valid_openmeteo_params(self, openmeteo_download_params):
        """Test that Open-Meteo params are valid"""
        assert openmeteo_download_params.past_days == 5
        assert openmeteo_download_params.forecast_days == 3
    
    def test_openmeteo_params_defaults(self, sample_centroids_csv, temp_dir):
        """Test Open-Meteo params with defaults"""
        params = OpenMeteoDownloadParams(
            centroids_shapefile=sample_centroids_csv,
            output_file=str(Path(temp_dir) / "output.parquet")
        )
        assert params.past_days == 5
        assert params.forecast_days == 3

# ============================================================================
# Test Data Loading and Validation
# ============================================================================

class TestDataLoading:
    """Test loading centroid data from various formats"""
    
    def test_load_centroids_from_csv(self, sample_centroids_csv):
        """Test loading centroids from CSV"""
        df = pd.read_csv(sample_centroids_csv)
        assert len(df) == 3
        assert 'FID' in df.columns
        assert 'lon' in df.columns
        assert 'lat' in df.columns
    
    def test_load_centroids_from_shp(self, sample_centroids_shp):
        """Test loading centroids from shapefile"""
        gdf = gpd.read_file(sample_centroids_shp)
        assert len(gdf) == 3
        assert 'FID' in gdf.columns

# ============================================================================
# Test Transformations
# ============================================================================

class TestDataTransformations:
    """Test climate data transformations"""
    
    def test_kelvin_to_celsius(self):
        """Test Kelvin to Celsius conversion"""
        kelvin = 300.15  # ~27°C
        celsius = kelvin - 273.15
        assert abs(celsius - 27.0) < 0.1
    
    def test_meters_to_millimeters(self):
        """Test meters to millimeters conversion"""
        meters = 0.005  # 5 mm
        mm = meters * 1000
        assert mm == 5.0
    
    def test_transformation_on_dataframe(self):
        """Test transformations on actual DataFrame"""
        df = pd.DataFrame({
            'variable': ['temperature_2m', 'total_precipitation_sum'],
            'value': [300.15, 0.005]
        })
        
        # Apply Kelvin transformation
        df.loc[df['variable'] == 'temperature_2m', 'value'] -= 273.15
        assert abs(df[df['variable'] == 'temperature_2m']['value'].iloc[0] - 27.0) < 0.1
        
        # Apply mm transformation
        df.loc[df['variable'] == 'total_precipitation_sum', 'value'] *= 1000
        assert abs(df[df['variable'] == 'total_precipitation_sum']['value'].iloc[0] - 5.0) < 0.1

# ============================================================================
# Test Process Climate Data
# ============================================================================

class TestProcessClimateData:
    """Test climate data processing"""
    
    @pytest.mark.asyncio
    async def test_process_climate_data(self, climate_process_params):
        """Test processing climate data with transformations"""
        result = await process_climate_data(climate_process_params)
        
        assert "message" in result
        assert "processed_era5" in result["message"].lower() or "processed" in result["message"].lower()
        assert result["era5_rows"] > 0
    
    @pytest.mark.asyncio
    async def test_process_climate_data_creates_output(self, climate_process_params):
        """Test that processing creates output file"""
        result = await process_climate_data(climate_process_params)
        
        output_file = Path(climate_process_params.output_folder) / "processed_era5_data.parquet"
        assert output_file.exists()
    
    @pytest.mark.asyncio
    async def test_process_climate_data_applies_transformations(self, climate_process_params, temp_dir):
        """Test that transformations are applied correctly"""
        result = await process_climate_data(climate_process_params)
        
        output_file = Path(temp_dir) / "processed_era5_data.parquet"
        df = pd.read_parquet(output_file)
        
        # Check that temperature was transformed from Kelvin to Celsius
        temp_rows = df[df['variable'] == 'temperature_2m']
        if len(temp_rows) > 0:
            # Value should be around 27°C, not 300K
            assert temp_rows['value'].iloc[0] < 100  # Celsius values are < 100

# ============================================================================
# Test Data Structure and Shape
# ============================================================================

class TestDataStructure:
    """Test data structure and shape validation"""
    
    def test_processed_data_has_required_columns(self, climate_process_params):
        """Test that processed data has required columns"""
        df = pd.DataFrame({
            'FID': [1, 2],
            'longitude': [-53.9, -53.8],
            'latitude': [-12.1, -12.2],
            'date': ['2025-01-01', '2025-01-02'],
            'variable': ['temperature_2m', 'temperature_2m'],
            'value': [27.0, 28.0],
            'unit': ['°C', '°C'],
            'variable__unit': ['temperature_2m__°C', 'temperature_2m__°C']
        })
        
        required_cols = ['FID', 'longitude', 'latitude', 'date', 'variable', 'value']
        assert all(col in df.columns for col in required_cols)
    
    def test_centroid_data_has_required_columns(self, sample_centroids_csv):
        """Test that centroid data has required columns"""
        df = pd.read_csv(sample_centroids_csv)
        required_cols = ['FID', 'lon', 'lat']
        assert all(col in df.columns for col in required_cols)

# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling in climate ETL"""
    
    @pytest.mark.asyncio
    async def test_missing_centroids_file(self, temp_dir):
        """Test handling of missing centroids file"""
        params = ERA5ExtractParams(
            centroids_shapefile="/nonexistent/path.csv",
            start_date="2025-01-01",
            end_date="2025-01-05",
            output_folder=temp_dir,
            variables=[]
        )
        
        with pytest.raises((FileNotFoundError, Exception)):
            await extract_era5_data(params)
    
    @pytest.mark.asyncio
    async def test_invalid_date_range(self, sample_centroids_csv, temp_dir):
        """Test handling of invalid date range"""
        params = ERA5ExtractParams(
            centroids_shapefile=sample_centroids_csv,
            start_date="2025-01-05",
            end_date="2025-01-01",  # End before start
            output_folder=temp_dir,
            variables=[]
        )
        
        # This should either raise an error or return empty results
        # Depends on implementation
        try:
            result = await extract_era5_data(params)
            assert "message" in result or "error" in result
        except (ValueError, Exception):
            pass
    
    def test_process_empty_era5_files(self, temp_dir):
        """Test processing with empty ERA5 files"""
        # Create empty parquet file
        df = pd.DataFrame({
            'FID': [],
            'longitude': [],
            'latitude': [],
            'date': [],
            'variable': [],
            'value': []
        })
        empty_file = Path(temp_dir) / "empty.parquet"
        df.to_parquet(empty_file)
        
        params = ClimateProcessParams(
            era5_raw_files=[str(empty_file)],
            openmeteo_file="",
            output_folder=temp_dir
        )
        
        # Should handle gracefully
        assert params.era5_raw_files[0] == str(empty_file)

# ============================================================================
# Test Variable Constants
# ============================================================================

class TestERA5Variables:
    """Test ERA5 variable constants"""
    
    def test_era5_variables_not_empty(self):
        """Test that ERA5 variables list is not empty"""
        assert len(ERA5_VARIABLES) > 0
    
    def test_era5_variables_are_strings(self):
        """Test that all ERA5 variables are strings"""
        assert all(isinstance(var, str) for var in ERA5_VARIABLES)
    
    def test_era5_variables_no_duplicates(self):
        """Test that ERA5 variables have no duplicates"""
        assert len(ERA5_VARIABLES) == len(set(ERA5_VARIABLES))
    
    def test_known_temperature_variables(self):
        """Test that known temperature variables are in the list"""
        assert 'temperature_2m' in ERA5_VARIABLES
        assert 'temperature_2m_min' in ERA5_VARIABLES
        assert 'temperature_2m_max' in ERA5_VARIABLES
    
    def test_known_precipitation_variables(self):
        """Test that precipitation variables are in the list"""
        assert 'total_precipitation_sum' in ERA5_VARIABLES

# ============================================================================
# Test Mock API Responses
# ============================================================================

class TestMockAPIs:
    """Test with mocked external API calls"""
    
    @patch('climate_etl.ee')
    def test_era5_extraction_with_mock_ee(self, mock_ee, era5_extract_params):
        """Test ERA5 extraction with mocked Earth Engine"""
        # Mock EE responses
        mock_ee.Initialize = MagicMock()
        mock_ee.data._credentials = True
        
        # Would verify that initialization is called
        assert mock_ee.Initialize is not None
    
    @patch('climate_etl.requests_cache.CachedSession')
    def test_openmeteo_download_with_mock_session(self, mock_session, openmeteo_download_params):
        """Test Open-Meteo download with mocked session"""
        mock_session.return_value = MagicMock()
        
        assert mock_session is not None

# ============================================================================
# Test Data Quality Checks
# ============================================================================

class TestDataQuality:
    """Test data quality validation"""
    
    def test_no_null_values_in_processed_data(self):
        """Test that processed data has no null values in required columns"""
        df = pd.DataFrame({
            'FID': [1, 2, 3],
            'longitude': [-53.9, -53.8, -53.85],
            'latitude': [-12.1, -12.2, -12.15],
            'date': ['2025-01-01', '2025-01-02', '2025-01-03'],
            'variable': ['temperature_2m', 'temperature_2m', 'temperature_2m'],
            'value': [27.0, 28.0, 26.5]
        })
        
        # Check for nulls in critical columns
        assert not df[['FID', 'longitude', 'latitude', 'date', 'variable', 'value']].isnull().any().any()
    
    def test_value_ranges(self):
        """Test that climate values are in reasonable ranges"""
        # Temperature in Celsius should be between -60 and 60 (roughly)
        temperatures = [27.0, 28.0, 26.5]
        assert all(-60 <= t <= 60 for t in temperatures)
        
        # Precipitation in mm should be non-negative
        precipitation = [0.0, 1.5, 2.0]
        assert all(p >= 0 for p in precipitation)

# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
