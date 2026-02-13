from fastapi import APIRouter, HTTPException
from models import SentinelETLParams, LULCExtractParams, IBGEPAMProcessParams, ERA5ExtractParams, OpenMeteoDownloadParams, ClimateProcessParams
from climate_etl import extract_era5_data, download_openmeteo_data, process_climate_data

router = APIRouter(prefix="/etl", tags=["ETL Module"])

@router.post("/sentinel/process")
async def process_sentinel_etl(params: SentinelETLParams):
    # Placeholder: ETL for Sentinel-2
    return {"message": "Sentinel data processed"}

@router.post("/lulc/extract-percentage")
async def extract_lulc_percentage(params: LULCExtractParams):
    # Placeholder: Extract LULC percentages
    return {"message": "LULC percentages extracted"}

@router.post("/ibge/process-pam")
async def process_ibge_pam(params: IBGEPAMProcessParams):
    # Placeholder: Process IBGE PAM data
    return {"message": "PAM data processed"}

@router.post("/climate/era5/extract")
async def extract_era5_etl(params: ERA5ExtractParams):
    try:
        result = await extract_era5_data(params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/climate/openmeteo/download")
async def download_openmeteo_etl(params: OpenMeteoDownloadParams):
    try:
        result = await download_openmeteo_data(params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/climate/process")
async def process_climate_etl(params: ClimateProcessParams):
    try:
        result = await process_climate_data(params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))