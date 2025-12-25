# Swiss Ephemeris API Integration Guide

Complete guide for integrating this astrological calculation API into an existing FastAPI project.

## Table of Contents
1. [Quick Integration (Recommended)](#quick-integration-recommended)
2. [Modular Integration (Best Practice)](#modular-integration-best-practice)
3. [Handling Conflicts](#handling-conflicts)
4. [Testing After Integration](#testing-after-integration)
5. [Configuration Options](#configuration-options)

---

## Quick Integration (Recommended)

### Scenario: Simple FastAPI project with flat structure

**Current Structure:**
```
your-project/
├── main.py           # Your existing FastAPI app
├── models.py         # Your existing models (optional)
├── routers.py        # Your existing routers (optional)
└── requirements.txt
```

**Integration Steps:**

### Step 1: Copy Required Files

Copy these 4 files from swisseph-api to your project:

```bash
# From swisseph-api directory
cp natal.py /path/to/your-project/natal.py
cp exceptions.py /path/to/your-project/swisseph_exceptions.py
cp models.py /path/to/your-project/swisseph_models.py
cp routers.py /path/to/your-project/swisseph_routers.py
```

**Why rename?**
- `exceptions.py` → `swisseph_exceptions.py` (avoid conflicts with your existing exceptions)
- `models.py` → `swisseph_models.py` (avoid conflicts with your existing models)
- `routers.py` → `swisseph_routers.py` (avoid conflicts with your existing routers)
- `natal.py` stays as-is (core calculation library)

### Step 2: Update Imports in Copied Files

**A) Update `swisseph_routers.py` imports:**

Change:
```python
from models import (...)
from exceptions import (...)
```

To:
```python
from swisseph_models import (...)
from swisseph_exceptions import (...)
```

**B) Update `swisseph_models.py` imports:**
No changes needed - it only imports from standard library and pydantic.

**C) Update `swisseph_exceptions.py` imports:**
No changes needed - only defines exception classes.

### Step 3: Install Dependencies

Add to your `requirements.txt` (or `pyproject.toml`):

```txt
pyswisseph>=2.10.3.2
pytz>=2024.1
```

Then install:
```bash
pip install pyswisseph pytz
# or with uv:
uv add pyswisseph pytz
```

### Step 4: Integrate Router into Your FastAPI App

**Option A: If you have a simple main.py**

```python
# your-project/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Import the swisseph router
from swisseph_routers import router as swisseph_router
from swisseph_exceptions import (
    ChartCalculationError,
    InvalidCoordinatesError,
    InvalidTimezoneError
)

app = FastAPI(title="Your Existing API")

# Add CORS if not already present
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add exception handlers for swisseph errors
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=422,
        content={"error": "ValidationError", "message": str(exc), "detail": None}
    )

@app.exception_handler(InvalidCoordinatesError)
async def invalid_coordinates_handler(request: Request, exc: InvalidCoordinatesError):
    return JSONResponse(
        status_code=422,
        content={"error": "InvalidCoordinatesError", "message": str(exc), "detail": None}
    )

@app.exception_handler(InvalidTimezoneError)
async def invalid_timezone_handler(request: Request, exc: InvalidTimezoneError):
    return JSONResponse(
        status_code=422,
        content={"error": "InvalidTimezoneError", "message": str(exc), "detail": None}
    )

@app.exception_handler(ChartCalculationError)
async def chart_calculation_error_handler(request: Request, exc: ChartCalculationError):
    return JSONResponse(
        status_code=500,
        content={"error": "ChartCalculationError", "message": str(exc), "detail": None}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "detail": exc.errors()
        }
    )

# Include the swisseph router with a prefix
app.include_router(
    swisseph_router,
    prefix="/api/v1/astrology",  # Custom prefix to avoid conflicts
    tags=["Astrology"]
)

# Your existing routes
@app.get("/")
async def root():
    return {"message": "Your API"}

# ... rest of your existing code ...
```

**Option B: If you already have routers organized**

```python
# your-project/main.py
from fastapi import FastAPI
from your_existing_router import router as your_router
from swisseph_routers import router as swisseph_router

app = FastAPI()

# Your existing routers
app.include_router(your_router, prefix="/api/v1")

# Add swisseph router
app.include_router(
    swisseph_router,
    prefix="/api/v1/astrology",
    tags=["Astrology"]
)
```

### Step 5: Verify Integration

```bash
# Start your server
uvicorn main:app --reload

# Visit the docs
# http://localhost:8000/docs
```

You should see:
- Your existing endpoints
- New astrology endpoints under `/api/v1/astrology/...`

### Step 6: Test Endpoints

```bash
# Test natal chart calculation
curl -X POST "http://localhost:8000/api/v1/astrology/natal/calculate" \
  -H "Content-Type: application/json" \
  -d '{
    "birth_date": "1990-06-15T14:30:00",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "timezone": "America/New_York"
  }'
```

---

## Modular Integration (Best Practice)

### Scenario: Larger project with organized structure

**Target Structure:**
```
your-project/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── endpoints/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── users.py
│   │   │   │   └── astrology.py      # NEW
│   │   └── deps.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── astrology.py               # NEW
│   ├── services/
│   │   ├── __init__.py
│   │   └── astrology/                 # NEW
│   │       ├── __init__.py
│   │       ├── natal.py               # Copy from swisseph-api
│   │       └── calculations.py
│   └── core/
│       ├── __init__.py
│       ├── config.py
│       └── exceptions.py              # Add swisseph exceptions here
└── requirements.txt
```

### Integration Steps:

### Step 1: Create Astrology Module

```bash
mkdir -p app/services/astrology
mkdir -p app/api/v1/endpoints
```

### Step 2: Copy Core Files

```bash
# Copy natal calculation library
cp swisseph-api/natal.py app/services/astrology/natal.py

# Create __init__.py
touch app/services/astrology/__init__.py
```

**app/services/astrology/__init__.py:**
```python
"""Astrology calculation services using Swiss Ephemeris."""

from .natal import NatalChart, TransitChart, ChartConfig, NodeType, ZodiacType

__all__ = [
    'NatalChart',
    'TransitChart',
    'ChartConfig',
    'NodeType',
    'ZodiacType',
]
```

### Step 3: Add Exceptions to Your Core

**app/core/exceptions.py (add to existing file):**
```python
# ... your existing exceptions ...

# Swiss Ephemeris exceptions
class SwissEphAPIException(Exception):
    """Base exception for astrology API errors."""
    pass

class ChartCalculationError(SwissEphAPIException):
    """Raised when chart calculation fails."""
    pass

class InvalidCoordinatesError(SwissEphAPIException):
    """Raised when coordinates are invalid."""
    pass

class InvalidTimezoneError(SwissEphAPIException):
    """Raised when timezone is invalid."""
    pass
```

### Step 4: Create Pydantic Models

**app/models/astrology.py (new file):**
```python
"""Pydantic models for astrology endpoints."""

# Copy content from swisseph_models.py
# But update imports to match your project structure:
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic import ConfigDict
from datetime import datetime
from typing import Optional
from enum import Enum
import pytz

# ... rest of the models from swisseph_models.py ...
```

### Step 5: Create API Endpoints

**app/api/v1/endpoints/astrology.py (new file):**
```python
"""Astrology calculation endpoints."""

from fastapi import APIRouter, HTTPException
import pytz

from app.models.astrology import (
    NatalChartRequest,
    NatalChartBatchRequest,
    TransitCalculationRequest,
    TransitBatchRequest,
    ExactTransitsRequest,
    NatalChartResponse,
    TransitResponse,
    ExactTransitsResponse,
    BatchResponse,
    BatchResultItem,
    BatchSummary,
    ErrorDetail,
    TransitEventData,
    ConfigHouseSystemsResponse,
    ConfigAspectsResponse,
    AspectDefinitionResponse,
)
from app.services.astrology import (
    NatalChart,
    TransitChart,
    ChartConfig,
    NodeType,
    ZodiacType,
    PartOfFortuneFormula,
)
from app.core.exceptions import (
    InvalidCoordinatesError,
    InvalidTimezoneError,
    ChartCalculationError,
)

router = APIRouter()

# ... copy all endpoint implementations from swisseph_routers.py ...
# Update import paths as shown above
```

### Step 6: Register Router

**app/api/v1/__init__.py:**
```python
from fastapi import APIRouter
from app.api.v1.endpoints import users, astrology  # Add astrology

api_router = APIRouter()

# Your existing routes
api_router.include_router(users.router, prefix="/users", tags=["users"])

# Add astrology routes
api_router.include_router(astrology.router, prefix="/astrology", tags=["Astrology"])
```

**app/main.py:**
```python
from fastapi import FastAPI
from app.api.v1 import api_router
from app.core.exceptions import (
    ChartCalculationError,
    InvalidCoordinatesError,
    InvalidTimezoneError,
)

app = FastAPI(title="Your API")

# Add exception handlers (if not already centralized)
# ... exception handlers from the quick integration section ...

# Include API router
app.include_router(api_router, prefix="/api/v1")
```

### Step 7: Update Dependencies

**requirements.txt:**
```txt
fastapi>=0.100.0
uvicorn>=0.20.0
pydantic>=2.0.0
pyswisseph>=2.10.3.2
pytz>=2024.1
# ... your other dependencies ...
```

---

## Handling Conflicts

### If You Already Have `models.py`

**Option 1: Namespace the models**
```python
# Create swisseph_models.py instead
# Import as: from swisseph_models import NatalChartRequest
```

**Option 2: Create a package structure**
```python
# models/
# ├── __init__.py
# ├── user.py
# └── astrology.py

# Import as: from models.astrology import NatalChartRequest
```

### If You Already Have Exception Handlers

**Option 1: Merge exception handlers**
```python
# Add swisseph exception handlers to your existing exception handler file
# No conflicts - just additional handlers
```

**Option 2: Conditional exception handling**
```python
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    # Check if it's a swisseph error or your existing logic
    if "coordinate" in str(exc).lower() or "latitude" in str(exc).lower():
        return JSONResponse(status_code=422, content={...})
    # Otherwise handle as normal
    return your_existing_handler(request, exc)
```

### If You Have Existing `/api/v1` Prefix

**Solution: Use a different sub-path**
```python
# Instead of /api/v1/natal/calculate
# Use /api/v1/astrology/natal/calculate

app.include_router(
    swisseph_router,
    prefix="/api/v1/astrology",  # Adds extra nesting
    tags=["Astrology"]
)
```

### If You Use Different Pydantic Version

**Check compatibility:**
```bash
pip show pydantic
```

If you're on Pydantic v1:
- Models use `Config` class instead of `model_config`
- Field validators use `@validator` instead of `@field_validator`
- Need to downgrade models or upgrade your Pydantic

**Migration to Pydantic v2 (if needed):**
```bash
pip install pydantic>=2.0
pip install pydantic-settings  # If you use settings
```

Then update models:
```python
# OLD (Pydantic v1)
class Config:
    schema_extra = {...}

# NEW (Pydantic v2)
model_config = ConfigDict(json_schema_extra={...})
```

---

## Testing After Integration

### Step 1: Basic Import Test

```python
# test_integration.py
def test_imports():
    """Test that all modules import correctly."""
    from swisseph_routers import router
    from swisseph_models import NatalChartRequest
    from swisseph_exceptions import ChartCalculationError
    from natal import NatalChart

    assert router is not None
    assert NatalChartRequest is not None
    assert ChartCalculationError is not None
    assert NatalChart is not None
    print("✓ All imports successful")

if __name__ == "__main__":
    test_imports()
```

### Step 2: API Schema Test

```python
# test_schema.py
from main import app

def test_openapi_schema():
    """Verify astrology endpoints appear in OpenAPI schema."""
    schema = app.openapi()

    # Check astrology endpoints exist
    astrology_paths = [p for p in schema['paths'].keys() if 'astrology' in p or 'natal' in p or 'transit' in p]

    print(f"Found {len(astrology_paths)} astrology endpoints:")
    for path in astrology_paths:
        print(f"  {path}")

    assert len(astrology_paths) >= 7, "Should have at least 7 astrology endpoints"
    print("✓ All endpoints registered")

if __name__ == "__main__":
    test_openapi_schema()
```

### Step 3: Endpoint Functionality Test

```python
# test_endpoints.py
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_natal_calculation():
    """Test natal chart calculation."""
    response = client.post(
        "/api/v1/astrology/natal/calculate",  # Adjust path to your prefix
        json={
            "birth_date": "1990-06-15T14:30:00",
            "latitude": 40.7128,
            "longitude": -74.0060,
            "timezone": "America/New_York"
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert "planets" in data
    assert "houses" in data
    assert "aspects" in data
    print("✓ Natal chart calculation works")

def test_config_endpoints():
    """Test configuration endpoints."""
    response = client.get("/api/v1/astrology/config/house-systems")
    assert response.status_code == 200
    data = response.json()
    assert "house_systems" in data
    assert len(data["house_systems"]) > 0
    print("✓ Configuration endpoints work")

def test_error_handling():
    """Test error handling for invalid input."""
    response = client.post(
        "/api/v1/astrology/natal/calculate",
        json={
            "birth_date": "1990-06-15T14:30:00",
            "latitude": 100,  # Invalid!
            "longitude": -74.0060
        }
    )

    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    print("✓ Error handling works")

if __name__ == "__main__":
    test_natal_calculation()
    test_config_endpoints()
    test_error_handling()
    print("\n✓ All tests passed!")
```

### Step 4: Run Tests

```bash
# Install test dependencies if needed
pip install httpx pytest

# Run tests
python test_integration.py
python test_schema.py
python test_endpoints.py

# Or with pytest
pytest test_*.py -v
```

---

## Configuration Options

### Custom API Prefix

```python
app.include_router(
    swisseph_router,
    prefix="/api/v1/charts",      # Use /charts instead of /astrology
    tags=["Charts"]
)
```

Endpoints become:
- `/api/v1/charts/natal/calculate`
- `/api/v1/charts/transits/calculate`
- etc.

### Custom Tags for Organization

```python
app.include_router(
    swisseph_router,
    prefix="/api/v1/astrology",
    tags=["Astrology", "Swiss Ephemeris", "Calculations"]  # Multiple tags
)
```

### Dependency Injection

If you use dependencies (auth, database, etc.):

```python
from fastapi import Depends
from app.api.deps import get_current_user

# Wrap the router
app.include_router(
    swisseph_router,
    prefix="/api/v1/astrology",
    tags=["Astrology"],
    dependencies=[Depends(get_current_user)]  # Require auth for all endpoints
)
```

### CORS Configuration

If you need specific CORS settings:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],  # Specific domains
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Limit methods
    allow_headers=["*"],
)
```

### Environment-Specific Settings

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ASTROLOGY_API_PREFIX: str = "/api/v1/astrology"
    ENABLE_ASTROLOGY: bool = True

    class Config:
        env_file = ".env"

settings = Settings()

# main.py
from config import settings

if settings.ENABLE_ASTROLOGY:
    app.include_router(
        swisseph_router,
        prefix=settings.ASTROLOGY_API_PREFIX,
        tags=["Astrology"]
    )
```

---

## Common Issues & Solutions

### Issue 1: Import Errors

**Error:** `ModuleNotFoundError: No module named 'natal'`

**Solution:**
```bash
# Make sure natal.py is in the same directory or in PYTHONPATH
# Or use absolute imports
from app.services.astrology.natal import NatalChart
```

### Issue 2: Pydantic Validation Errors

**Error:** `ValidationError: ... field required`

**Solution:** Check that all required fields are provided in requests
```python
# All required fields (no default values):
- birth_date
- latitude
- longitude
```

### Issue 3: Swiss Ephemeris Data Files

**Error:** `SwissEph file not found`

**Solution:** Swiss Ephemeris needs data files for some calculations
```bash
# Usually handled automatically by pyswisseph
# If issues occur, set environment variable:
export SE_EPHE_PATH=/path/to/ephe/data
```

### Issue 4: Timezone Errors

**Error:** `UnknownTimeZoneError: 'Invalid/Timezone'`

**Solution:** Use valid IANA timezone names
```python
# Valid:
"America/New_York"
"Europe/London"
"Asia/Tokyo"

# Invalid:
"EST"
"GMT"
"PST"
```

### Issue 5: CORS Issues in Browser

**Error:** Browser console shows CORS errors

**Solution:** Ensure CORS middleware is properly configured
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Quick Reference

### Minimal Integration Checklist

- [ ] Copy 4 files: `natal.py`, `swisseph_exceptions.py`, `swisseph_models.py`, `swisseph_routers.py`
- [ ] Update imports in copied files
- [ ] Install dependencies: `pyswisseph`, `pytz`
- [ ] Add router to FastAPI app with custom prefix
- [ ] Add exception handlers
- [ ] Test with `/docs` endpoint
- [ ] Run basic API test

### File Mapping

| Source File | Destination | Rename? | Purpose |
|------------|-------------|---------|---------|
| `natal.py` | Same location as main.py | No | Core calculations |
| `exceptions.py` | Same location | Yes → `swisseph_exceptions.py` | Custom exceptions |
| `models.py` | Same location | Yes → `swisseph_models.py` | Pydantic models |
| `routers.py` | Same location | Yes → `swisseph_routers.py` | API endpoints |

### Import Updates Needed

In `swisseph_routers.py`:
```python
# Change these imports:
from models import ...          → from swisseph_models import ...
from exceptions import ...      → from swisseph_exceptions import ...
from natal import ...           → from natal import ...  # No change
```

---

## Summary

**Fastest Integration (5 minutes):**
1. Copy 4 files (rename 3 to avoid conflicts)
2. Update imports in `swisseph_routers.py`
3. Add `app.include_router(swisseph_router, prefix="/api/v1/astrology")`
4. Install dependencies
5. Done!

**Production Integration (30 minutes):**
1. Create organized module structure
2. Integrate into existing architecture
3. Add comprehensive error handling
4. Write tests
5. Configure CORS and security
6. Document endpoints

The API is self-contained and designed to integrate easily into existing FastAPI projects with minimal modifications.
