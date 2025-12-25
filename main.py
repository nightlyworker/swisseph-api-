from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from exceptions import (
    SwissEphAPIException,
    ChartCalculationError,
    InvalidDateTimeError,
    InvalidCoordinatesError,
    InvalidTimezoneError
)
from routers import router

app = FastAPI(
    title="Swiss Ephemeris API",
    description="Astrological chart calculation API using Swiss Ephemeris",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError exceptions from natal.py."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "ValidationError",
            "message": str(exc),
            "detail": None
        }
    )


@app.exception_handler(InvalidCoordinatesError)
async def invalid_coordinates_handler(request: Request, exc: InvalidCoordinatesError):
    """Handle invalid coordinates errors."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "InvalidCoordinatesError",
            "message": str(exc),
            "detail": None
        }
    )


@app.exception_handler(InvalidTimezoneError)
async def invalid_timezone_handler(request: Request, exc: InvalidTimezoneError):
    """Handle invalid timezone errors."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "InvalidTimezoneError",
            "message": str(exc),
            "detail": None
        }
    )


@app.exception_handler(ChartCalculationError)
async def chart_calculation_error_handler(request: Request, exc: ChartCalculationError):
    """Handle chart calculation errors."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "ChartCalculationError",
            "message": str(exc),
            "detail": None
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    return JSONResponse(
        status_code=422,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "detail": exc.errors()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other unexpected exceptions."""
    # In production, log this error server-side
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred",
            "detail": None
        }
    )


# Include API router
app.include_router(router, prefix="/api/v1", tags=["API"])


# Root endpoints
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Swiss Ephemeris API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}
