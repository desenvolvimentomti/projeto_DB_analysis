# Earth Engine Authentication Setup

This guide explains how to properly configure Earth Engine authentication for the climate ETL module.

## Why Service Account Authentication?

The code uses **service account keys** instead of interactive authentication (`ee.Authenticate()`) because:
- ✅ Works in production/headless environments (servers, Docker, CI/CD)
- ✅ No interactive browser login required
- ✅ Secure credential management via environment variables
- ✅ Suitable for automated scripts and APIs

❌ Interactive `ee.Authenticate()` will NOT work in:
- Automated servers/CI pipelines
- Docker containers
- Headless environments
- Production deployments

## Setup Instructions

### 1. Create a Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Select or create a project
3. Go to **IAM & Admin** → **Service Accounts**
4. Click **Create Service Account**
   - Service account name: `earth-engine-cli` (or similar)
   - Grant roles:
     - **Earth Engine Admin** (or **Viewer**)
     - **Compute Admin** (if using Compute resources)
5. Create a JSON key:
   - Click the service account
   - Go to **Keys** tab
   - **Create new key** → **JSON**
   - Save the file securely

### 2. Register for Earth Engine

1. Go to [Google Earth Engine](https://earthengine.google.com/)
2. Click **Sign Up**
3. Enter your **Google Cloud project ID** (NOT the service account email)
4. Earth Engine will send a confirmation email
5. Wait for approval (usually 1-2 hours)

### 3. Configure .env File

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Edit `.env` and add the path to your service account JSON:

```env
GEE_SERVICE_ACCOUNT_JSON_PATH=/path/to/service-account-key.json
```

Or paste the JSON directly (less secure):

```env
GEE_SERVICE_ACCOUNT_JSON={"type":"service_account","project_id":"...","..."}
```

### 4. Add .env to .gitignore

Make sure `.env` is in `.gitignore` (already done):

```bash
cat .gitignore | grep .env
# Output: .env
```

Never commit `.env` files with credentials!

## Verification

Test the authentication:

```bash
python -c "from climate_etl import initialize_earth_engine; initialize_earth_engine()"
```

Expected output:
```
✅ Earth Engine initialized with service account: /path/to/service-account-key.json
```

## Using in Code

The `initialize_earth_engine()` function is called automatically in `extract_era5_data()`:

```python
from climate_etl import extract_era5_data
# Function will handle authentication automatically
```

Or manually:

```python
from climate_etl import initialize_earth_engine

if initialize_earth_engine():
    # Ready to use Earth Engine
    import ee
    data = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR").first()
else:
    print("Failed to initialize Earth Engine")
```

## Troubleshooting

### "Failed to initialize with service account file"

- Check file path is correct and accessible
- Verify JSON file is valid: `python -m json.tool service-account-key.json`
- Ensure service account has Earth Engine access

### "Earth Engine initialization failed"

- Verify service account is enabled in Google Cloud Console
- Check that project is registered with Earth Engine
- Try running: `earthengine authenticate` in terminal (if available)

### "Module 'ee' has no attribute '_credentials'"

- Earth Engine not installed: `pip install earthengine-api`
- Credentials not valid

## Security Best Practices

1. **Never commit `.env` files** - Add to `.gitignore`
2. **Use environment variables** - Not hardcoded paths
3. **Rotate keys regularly** - Delete old service account keys
4. **Limit permissions** - Use "Viewer" role if only reading data
5. **Use separate accounts** - Dev, staging, production accounts
6. **Store securely** - Use CI/CD secret management (GitHub Secrets, etc.)

## Environment Variables Summary

```env
# Required
GEE_SERVICE_ACCOUNT_JSON_PATH=/path/to/key.json

# Optional
GEE_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
OPENMETEO_API_URL=https://api.open-meteo.com/v1/forecast
LOG_LEVEL=INFO
```

## References

- [Google Earth Engine Authentication](https://developers.google.com/earth-engine/guides/service_accounts)
- [Earth Engine Python Setup](https://earthengine.readthedocs.io/en/latest/installation.html)
- [Google Cloud Service Accounts](https://cloud.google.com/docs/authentication/service-accounts)
- [Earth Engine Registration](https://earthengine.google.com/signup/)
