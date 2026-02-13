from fastapi import FastAPI
from routers.input_router import router as input_router
from routers.preprocessing_router import router as preprocessing_router
from routers.etl_router import router as etl_router
from routers.analysis_router import router as analysis_router
from routers.output_router import router as output_router

app = FastAPI(
    title="Geospatial Data Analysis API",
    description="FastAPI app for geospatial data processing, analysis, and reporting based on environmental monitoring workflow.",
    version="1.0.0"
)

app.include_router(input_router)
app.include_router(preprocessing_router)
app.include_router(etl_router)
app.include_router(analysis_router)
app.include_router(output_router)

@app.get("/")
async def root():
    return {"message": "Welcome to the Geospatial Data Analysis API"}