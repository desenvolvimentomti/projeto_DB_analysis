import os
import asyncio
import pandas as pd
import geopandas as gpd
from datetime import datetime, timedelta
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import ee
import requests_cache
import openmeteo_requests
import requests
from retry_requests import retry
from tqdm import tqdm
import numpy as np
from dotenv import load_dotenv
import json

# Load environment variables from .env file
load_dotenv()

# ERA5 Variables
ERA5_VARIABLES = [
    'dewpoint_temperature_2m', 'temperature_2m', 'temperature_2m_min', 'temperature_2m_max',
    'soil_temperature_level_1', 'soil_temperature_level_2', 'soil_temperature_level_3', 'soil_temperature_level_4',
    'volumetric_soil_water_layer_1', 'volumetric_soil_water_layer_2', 'volumetric_soil_water_layer_3', 'volumetric_soil_water_layer_4',
    'surface_net_solar_radiation_sum', 'surface_net_thermal_radiation_sum',
    'surface_solar_radiation_downwards_sum', 'surface_thermal_radiation_downwards_sum',
    'evaporation_from_bare_soil_sum', 'evaporation_from_the_top_of_canopy_sum',
    'evaporation_from_vegetation_transpiration_sum', 'potential_evaporation_sum', 'total_evaporation_sum',
    'runoff_sum', 'sub_surface_runoff_sum', 'surface_runoff_sum',
    'u_component_of_wind_10m', 'v_component_of_wind_10m',
    'total_precipitation_sum', 'leaf_area_index_high_vegetation', 'leaf_area_index_low_vegetation'
]

# ============================================================================
# Earth Engine Authentication
# ============================================================================

def initialize_earth_engine():
    """Initialize Earth Engine with service account credentials from .env"""
    try:
        # Check if already initialized
        ee.data._credentials
        print("Earth Engine already initialized")
        return True
    except:
        pass
    
    # Try to initialize with service account from .env
    service_account_path = os.getenv('GEE_SERVICE_ACCOUNT_JSON_PATH')
    
    if service_account_path and os.path.exists(service_account_path):
        try:
            credentials = ee.ServiceAccountCredentials.from_filename(service_account_path)
            ee.Initialize(credentials)
            print(f"✅ Earth Engine initialized with service account: {service_account_path}")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize with service account file: {e}")
            return False
    
    # Try to initialize with JSON string from .env
    service_account_json = os.getenv('GEE_SERVICE_ACCOUNT_JSON')
    if service_account_json:
        try:
            service_account_info = json.loads(service_account_json)
            credentials = ee.ServiceAccountCredentials.from_authorized_user_info(service_account_info)
            ee.Initialize(credentials)
            print("✅ Earth Engine initialized with service account JSON from .env")
            return True
        except Exception as e:
            print(f"❌ Failed to initialize with JSON credentials: {e}")
            return False
    
    # Last resort: try default credentials (won't work in production)
    try:
        ee.Initialize()
        print("⚠️ Earth Engine initialized with default credentials (may not work in production)")
        return True
    except Exception as e:
        print(f"❌ Earth Engine initialization failed: {e}")
        print("\nTo fix this, you need to:")
        print("1. Create a Google Cloud service account")
        print("2. Download the JSON key file")
        print("3. Set GEE_SERVICE_ACCOUNT_JSON_PATH in your .env file")
        print("4. See .env.example for configuration template")
        return False

async def extract_era5_data(params):
    """Extract ERA5-Land data from Earth Engine"""
    # Load centroids
    if params.centroids_shapefile.endswith('.csv'):
        aoi_centroids_gdf = pd.read_csv(params.centroids_shapefile)
        aoi_centroids_gdf = gpd.GeoDataFrame(aoi_centroids_gdf, geometry=gpd.points_from_xy(aoi_centroids_gdf.lon, aoi_centroids_gdf.lat))
    else:
        aoi_centroids_gdf = gpd.read_file(params.centroids_shapefile)
    if 'lon' not in aoi_centroids_gdf.columns:
        aoi_centroids_gdf['lon'] = aoi_centroids_gdf.geometry.x
    if 'lat' not in aoi_centroids_gdf.columns:
        aoi_centroids_gdf['lat'] = aoi_centroids_gdf.geometry.y

    id_col = 'FID' if 'FID' in aoi_centroids_gdf.columns else 'grid_id'

    # Initialize Earth Engine with service account
    if not initialize_earth_engine():
        raise RuntimeError("Failed to initialize Earth Engine. Check your .env configuration.")

    # Date range
    date_list = pd.date_range(start=params.start_date, end=params.end_date).strftime('%Y-%m-%d').tolist()

    # Group by date
    grouped_by_day = defaultdict(set)
    for date in date_list:
        grouped_by_day[date] = set(aoi_centroids_gdf[id_col])

    coord_lookup = {row[id_col]: (row['lon'], row['lat']) for _, row in aoi_centroids_gdf.iterrows()}

    def get_fc_from_chunk(chunk_df):
        return ee.FeatureCollection([
            ee.Feature(ee.Geometry.Point(row['lon'], row['lat']), {id_col: row[id_col]})
            for _, row in chunk_df.iterrows()
        ])

    def extract_day_chunk(task, max_retries=2):
        date_str, chunk_fids = task
        results = []
        for attempt in range(max_retries + 1):
            try:
                img = (
                    ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
                    .filterDate(date_str, pd.to_datetime(date_str) + pd.Timedelta(days=1))
                    .select(params.variables or ERA5_VARIABLES)
                    .first()
                )
                if img is None:
                    return []

                chunk_df = aoi_centroids_gdf[aoi_centroids_gdf[id_col].isin(chunk_fids)]
                fc_chunk = get_fc_from_chunk(chunk_df)

                samples = img.sampleRegions(
                    collection=fc_chunk,
                    scale=10000,
                    geometries=False,
                    tileScale=16
                )

                features = samples.getInfo().get('features', [])
                for feat in features:
                    props = feat.get('properties', {})
                    fid = props.get(id_col)
                    lon, lat = coord_lookup.get(fid, (None, None))
                    for var in params.variables or ERA5_VARIABLES:
                        if var in props:
                            results.append({
                                'FID': fid,
                                'longitude': lon,
                                'latitude': lat,
                                'date': date_str,
                                'variable': var,
                                'value': props[var]
                            })
                break
            except Exception as e:
                if attempt < max_retries:
                    continue
                return {'date': date_str, 'fids': chunk_fids}
        return results

    # Parallel execution
    chunk_size = 1000
    tasks = []
    for date, fids in grouped_by_day.items():
        for i in range(0, len(fids), chunk_size):
            tasks.append((date, list(fids)[i:i + chunk_size]))

    all_results = []
    failed_chunks = []

    def run_in_thread():
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(extract_day_chunk, task) for task in tasks]
            for future in as_completed(futures):
                result = future.result()
                if isinstance(result, dict) and 'date' in result:
                    failed_chunks.append(result)
                else:
                    all_results.extend(result)

    await asyncio.get_event_loop().run_in_executor(None, run_in_thread)

    # Save results
    if all_results:
        df = pd.DataFrame(all_results)
        os.makedirs(params.output_folder, exist_ok=True)
        output_file = os.path.join(params.output_folder, f"raw_era5_data_{params.start_date.replace('-', '')}_{params.end_date.replace('-', '')}.parquet")
        df.to_parquet(output_file, index=False, compression='snappy')
        return {"message": f"ERA5 data extracted and saved to {output_file}", "rows": len(df), "failed_chunks": len(failed_chunks)}
    else:
        return {"message": "No ERA5 data extracted", "failed_chunks": len(failed_chunks)}

async def download_openmeteo_data(params):
    """Download Open-Meteo climate data"""
    # Load centroids
    if params.centroids_shapefile.endswith('.csv'):
        aoi_centroids_gdf = pd.read_csv(params.centroids_shapefile)
        aoi_centroids_gdf = gpd.GeoDataFrame(aoi_centroids_gdf, geometry=gpd.points_from_xy(aoi_centroids_gdf.lon, aoi_centroids_gdf.lat))
    else:
        aoi_centroids_gdf = gpd.read_file(params.centroids_shapefile)
    if 'lon' not in aoi_centroids_gdf.columns:
        aoi_centroids_gdf['lon'] = aoi_centroids_gdf.geometry.x
    if 'lat' not in aoi_centroids_gdf.columns:
        aoi_centroids_gdf['lat'] = aoi_centroids_gdf.geometry.y

    id_col = 'FID' if 'FID' in aoi_centroids_gdf.columns else 'grid_id'

    # Setup cached session
    cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
    retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
    openmeteo = openmeteo_requests.Client(session=retry_session)

    url = "https://api.open-meteo.com/v1/forecast"
    params_base = {
        "daily": [
            "temperature_2m_max", "temperature_2m_mean", "temperature_2m_min", "dew_point_2m_mean",
            "relative_humidity_2m_mean", "relative_humidity_2m_max", "relative_humidity_2m_min", "uv_index_max",
            "uv_index_clear_sky_max", "shortwave_radiation_sum", "wet_bulb_temperature_2m_mean",
            "wet_bulb_temperature_2m_max", "wet_bulb_temperature_2m_min", "vapour_pressure_deficit_max",
            "et0_fao_evapotranspiration", "wind_direction_10m_dominant", "wind_gusts_10m_max", "wind_speed_10m_max",
            "precipitation_probability_mean", "precipitation_probability_min", "leaf_wetness_probability_mean",
            "growing_degree_days_base_0_limit_50", "et0_fao_evapotranspiration_sum", "precipitation_sum",
            "precipitation_hours", "precipitation_probability_max", "rain_sum"
        ],
        "timezone": "America/Sao_Paulo",
        "past_days": params.past_days,
        "forecast_days": params.forecast_days
    }

    # Load existing data
    if os.path.exists(params.output_file):
        df_existing = pd.read_parquet(params.output_file)
    else:
        df_existing = pd.DataFrame()

    all_data = []
    for idx, row in aoi_centroids_gdf.iterrows():
        fid = row[id_col]
        lat, lon = row['lat'], row['lon']

        params_req = params_base.copy()
        params_req.update({"latitude": lat, "longitude": lon})

        try:
            responses = openmeteo.weather_api(url, params=params_req)
            response = responses[0]
            daily = response.Daily()

            new_dates = pd.date_range(
                start=pd.to_datetime(daily.Time(), unit="s", utc=True),
                end=pd.to_datetime(daily.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=daily.Interval()),
                inclusive="left"
            ).tz_convert(None)

            existing_dates = set(df_existing[df_existing[id_col] == fid]['date'])
            missing_dates = [d for d in new_dates if d not in existing_dates]
            if not missing_dates:
                continue

            daily_data = {"date": new_dates, "latitude": lat, "longitude": lon, id_col: fid}
            for i, var in enumerate(params_base["daily"]):
                daily_data[var] = daily.Variables(i).ValuesAsNumpy()

            point_df = pd.DataFrame(daily_data)
            point_df = point_df[point_df['date'].isin(missing_dates)]
            all_data.append(point_df)

        except Exception as e:
            # Handle errors
            continue

    # Merge and save
    if all_data:
        df_new = pd.concat(all_data, ignore_index=True)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        df_combined.drop_duplicates(subset=[id_col, 'date'], inplace=True)
        df_combined.sort_values(by=[id_col, 'date'], inplace=True)
        df_combined.to_parquet(params.output_file, index=False, compression='snappy')
        return {"message": f"Open-Meteo data updated: {params.output_file}", "new_rows": len(df_new)}
    else:
        return {"message": "No new Open-Meteo data downloaded"}

async def process_climate_data(params):
    """Process and merge climate data"""
    # Load and merge ERA5 files
    df_list = [pd.read_parquet(fp) for fp in params.era5_raw_files]
    merged_era5 = pd.concat(df_list, ignore_index=True)
    merged_era5.drop_duplicates(subset=["FID", "variable", "date"], inplace=True)
    merged_era5.sort_values(by=["FID", "variable", "date"], inplace=True)
    merged_era5.reset_index(drop=True, inplace=True)

    # Transformations
    kelvin_vars = ['dewpoint_temperature_2m', 'temperature_2m', 'temperature_2m_min', 'temperature_2m_max',
                   'soil_temperature_level_1', 'soil_temperature_level_2', 'soil_temperature_level_3', 'soil_temperature_level_4']
    mm_vars = ['evaporation_from_bare_soil_sum', 'evaporation_from_the_top_of_canopy_sum',
               'evaporation_from_vegetation_transpiration_sum', 'potential_evaporation_sum', 'total_evaporation_sum',
               'runoff_sum', 'sub_surface_runoff_sum', 'surface_runoff_sum', 'total_precipitation_sum']

    merged_era5.loc[merged_era5['variable'].isin(kelvin_vars), 'value'] -= 273.15
    merged_era5.loc[merged_era5['variable'].isin(mm_vars), 'value'] *= 1000

    # Assign units
    merged_era5['unit'] = None
    merged_era5.loc[merged_era5['variable'].isin(kelvin_vars), 'unit'] = '°C'
    merged_era5.loc[merged_era5['variable'].isin(mm_vars), 'unit'] = 'mm'
    # Add other units...

    merged_era5['variable__unit'] = merged_era5['variable'] + "__" + merged_era5['unit']

    # Load Open-Meteo if provided
    if params.openmeteo_file and os.path.exists(params.openmeteo_file):
        df_openmeteo = pd.read_parquet(params.openmeteo_file)
        # Merge or process as needed
        # For now, just save ERA5 processed
    else:
        df_openmeteo = pd.DataFrame()

    # Save processed ERA5
    os.makedirs(params.output_folder, exist_ok=True)
    output_file = os.path.join(params.output_folder, "processed_era5_data.parquet")
    merged_era5.to_parquet(output_file, index=False, compression='snappy')

    return {"message": f"Climate data processed and saved to {output_file}", "era5_rows": len(merged_era5)}