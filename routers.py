"""API routers for Swiss Ephemeris API."""

from fastapi import APIRouter, HTTPException
import pytz

from models import (
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
from natal import (
    NatalChart,
    TransitChart,
    ChartConfig,
    NodeType,
    ZodiacType,
    PartOfFortuneFormula,
)
from exceptions import InvalidCoordinatesError, InvalidTimezoneError, ChartCalculationError

router = APIRouter()


# Helper Functions
def _build_natal_chart(request: NatalChartRequest) -> NatalChart:
    """Convert request model to NatalChart instance."""
    try:
        return NatalChart(
            birth_date=request.birth_date,
            latitude=request.latitude,
            longitude=request.longitude,
            house_system=request.house_system.value,
            timezone=request.timezone,
            node_type=NodeType(request.node_type.value),
            zodiac_type=ZodiacType(request.zodiac_type.value),
            include_minor_aspects=request.include_minor_aspects,
            sidereal_mode=request.sidereal_mode,
            pof_formula=PartOfFortuneFormula(request.pof_formula.value)
        )
    except ValueError as e:
        raise InvalidCoordinatesError(str(e))
    except pytz.exceptions.UnknownTimeZoneError as e:
        raise InvalidTimezoneError(f"Unknown timezone: {request.timezone}")


def _convert_transit_events(events: list) -> list[TransitEventData]:
    """Convert TransitEvent dataclass instances to Pydantic models."""
    return [
        TransitEventData(
            transit_planet=event.transit_planet,
            natal_planet=event.natal_planet,
            aspect=event.aspect,
            aspect_symbol=event.aspect_symbol,
            exact_date=event.exact_date,
            orb=event.orb,
            applying=event.applying,
            transit_retrograde=event.transit_retrograde
        )
        for event in events
    ]


# Configuration Endpoints
@router.get(
    "/config/house-systems",
    response_model=ConfigHouseSystemsResponse,
    summary="List Available House Systems",
    description="Get a list of all supported house systems for natal chart calculations."
)
async def get_house_systems():
    """List all available house systems."""
    return ConfigHouseSystemsResponse(
        house_systems=list(ChartConfig.HOUSE_SYSTEMS.keys())
    )


@router.get(
    "/config/aspects",
    response_model=ConfigAspectsResponse,
    summary="List Aspect Definitions",
    description="""
    Get definitions of all supported aspects including:
    - Aspect name and symbol
    - Exact angle
    - Orb allowances for natal and transit calculations
    - Categorized by major and minor aspects
    """
)
async def get_aspects():
    """List all aspect definitions with orb information."""
    major = [
        AspectDefinitionResponse(
            name=asp.name,
            symbol=asp.symbol,
            angle=asp.angle,
            natal_orbs={
                "luminary": asp.natal_orbs[0],
                "personal": asp.natal_orbs[1],
                "social": asp.natal_orbs[2],
                "outer": asp.natal_orbs[3]
            },
            transit_orbs={
                "luminary": asp.transit_orbs[0],
                "personal": asp.transit_orbs[1],
                "social": asp.transit_orbs[2],
                "outer": asp.transit_orbs[3]
            }
        )
        for asp in ChartConfig.ASPECTS if asp.major
    ]

    minor = [
        AspectDefinitionResponse(
            name=asp.name,
            symbol=asp.symbol,
            angle=asp.angle,
            natal_orbs={
                "luminary": asp.natal_orbs[0],
                "personal": asp.natal_orbs[1],
                "social": asp.natal_orbs[2],
                "outer": asp.natal_orbs[3]
            },
            transit_orbs={
                "luminary": asp.transit_orbs[0],
                "personal": asp.transit_orbs[1],
                "social": asp.transit_orbs[2],
                "outer": asp.transit_orbs[3]
            }
        )
        for asp in ChartConfig.ASPECTS if not asp.major
    ]

    return ConfigAspectsResponse(
        major_aspects=major,
        minor_aspects=minor
    )


# Natal Chart Endpoints
@router.post(
    "/natal/calculate",
    response_model=NatalChartResponse,
    summary="Calculate Natal Chart",
    description="""
    Calculate a complete natal chart including:
    - Planetary positions in signs and houses
    - House cusps and angles (ASC, MC, IC, DSC, Vertex)
    - Major and minor aspects between planets
    - Part of Fortune
    - Planetary dignities

    Supports multiple house systems, tropical/sidereal zodiac, and true/mean nodes.
    """,
    responses={
        200: {"description": "Successful calculation"},
        422: {"description": "Validation error - invalid input parameters"},
        500: {"description": "Calculation error - Swiss Ephemeris internal error"}
    }
)
async def calculate_natal_chart(request: NatalChartRequest):
    """Calculate a single natal chart."""
    try:
        chart = _build_natal_chart(request)
        result = chart.generate_full_chart()
        return NatalChartResponse(**result)
    except (InvalidCoordinatesError, InvalidTimezoneError):
        raise
    except Exception as e:
        raise ChartCalculationError(f"Chart calculation failed: {str(e)}")


@router.post(
    "/natal/calculate/batch",
    response_model=BatchResponse,
    summary="Calculate Multiple Natal Charts",
    description="""
    Calculate multiple natal charts in a single request.

    Each chart is processed independently - partial failures are allowed.
    The response includes individual results for each chart with success/error status,
    plus summary statistics of total, successful, and failed calculations.
    """,
    responses={
        200: {"description": "Batch processing complete (may include partial failures)"},
        422: {"description": "Validation error in request structure"}
    }
)
async def calculate_natal_batch(request: NatalChartBatchRequest):
    """Calculate multiple natal charts in batch."""
    results = []

    for idx, chart_req in enumerate(request.charts):
        try:
            chart = _build_natal_chart(chart_req)
            data = chart.generate_full_chart()
            results.append(BatchResultItem(
                id=chart_req.id or f"chart_{idx}",
                success=True,
                data=NatalChartResponse(**data),
                error=None
            ))
        except Exception as e:
            results.append(BatchResultItem(
                id=chart_req.id or f"chart_{idx}",
                success=False,
                data=None,
                error=ErrorDetail(
                    type=type(e).__name__,
                    message=str(e),
                    detail=None
                )
            ))

    return BatchResponse(
        results=results,
        summary=BatchSummary(
            total=len(results),
            successful=sum(1 for r in results if r.success),
            failed=sum(1 for r in results if not r.success)
        )
    )


# Transit Endpoints
@router.post(
    "/transits/calculate",
    response_model=TransitResponse,
    summary="Calculate Transits",
    description="""
    Calculate current transiting planet positions and their aspects to a natal chart.

    Returns:
    - Transiting planet positions in signs and natal houses
    - Aspects from transiting planets to natal planets and angles
    - Optionally includes aspects between transiting planets
    - Applying/separating status for each aspect
    - Retrograde indicators
    """,
    responses={
        200: {"description": "Successful calculation"},
        422: {"description": "Validation error - invalid input parameters"},
        500: {"description": "Calculation error"}
    }
)
async def calculate_transits(request: TransitCalculationRequest):
    """Calculate transits for a specific date."""
    try:
        natal = _build_natal_chart(request.natal_chart)
        transit_calc = TransitChart(natal)

        result = transit_calc.calculate_transits(
            transit_date=request.transit_date,
            timezone=request.transit_timezone,
            include_minor_aspects=request.include_minor_aspects,
            include_transit_to_transit=request.include_transit_to_transit,
            orb_factor=request.orb_factor
        )

        return TransitResponse(**result)
    except (InvalidCoordinatesError, InvalidTimezoneError):
        raise
    except Exception as e:
        raise ChartCalculationError(f"Transit calculation failed: {str(e)}")


@router.post(
    "/transits/calculate/batch",
    response_model=BatchResponse,
    summary="Calculate Multiple Transit Dates",
    description="""
    Calculate transits for multiple dates against a single natal chart.

    Useful for tracking planetary movements over time or comparing
    different time periods. Each transit date is processed independently,
    allowing partial failures.
    """,
    responses={
        200: {"description": "Batch processing complete (may include partial failures)"},
        422: {"description": "Validation error in request structure"}
    }
)
async def calculate_transits_batch(request: TransitBatchRequest):
    """Calculate multiple transit dates for one natal chart."""
    try:
        natal = _build_natal_chart(request.natal_chart)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid natal chart data: {str(e)}"
        )

    results = []
    transit_calc = TransitChart(natal)

    for idx, transit_input in enumerate(request.transit_dates):
        try:
            result = transit_calc.calculate_transits(
                transit_date=transit_input.date,
                timezone=transit_input.timezone,
                include_minor_aspects=request.include_minor_aspects,
                include_transit_to_transit=request.include_transit_to_transit,
                orb_factor=request.orb_factor
            )

            results.append(BatchResultItem(
                id=transit_input.id or f"transit_{idx}",
                success=True,
                data=TransitResponse(**result),
                error=None
            ))
        except Exception as e:
            results.append(BatchResultItem(
                id=transit_input.id or f"transit_{idx}",
                success=False,
                data=None,
                error=ErrorDetail(
                    type=type(e).__name__,
                    message=str(e),
                    detail=None
                )
            ))

    return BatchResponse(
        results=results,
        summary=BatchSummary(
            total=len(results),
            successful=sum(1 for r in results if r.success),
            failed=sum(1 for r in results if not r.success)
        )
    )


@router.post(
    "/transits/exact",
    response_model=ExactTransitsResponse,
    summary="Find Exact Transit Events",
    description="""
    Find exact transit events (when transiting planets form exact aspects to natal points)
    within a specified date range.

    This endpoint searches for precise moments when transits become exact, useful for:
    - Identifying significant upcoming astrological events
    - Planning based on astrological timing
    - Tracking planetary cycles

    You can filter by:
    - Specific transiting planets
    - Specific aspects (conjunction, square, trine, etc.)
    - Specific natal points to aspect

    The search algorithm handles retrograde motion and finds all exact crossings.
    """,
    responses={
        200: {"description": "Successful search - returns list of exact transit events"},
        422: {"description": "Validation error - invalid date range or parameters"},
        500: {"description": "Calculation error"}
    }
)
async def find_exact_transits(request: ExactTransitsRequest):
    """Find exact transit events in a date range."""
    try:
        natal = _build_natal_chart(request.natal_chart)
        transit_calc = TransitChart(natal)

        events = transit_calc.find_exact_transits(
            start_date=request.start_date,
            end_date=request.end_date,
            timezone=request.timezone,
            planets=request.planets,
            aspects=request.aspects,
            natal_points=request.natal_points
        )

        return ExactTransitsResponse(
            events=_convert_transit_events(events),
            count=len(events)
        )
    except (InvalidCoordinatesError, InvalidTimezoneError):
        raise
    except Exception as e:
        raise ChartCalculationError(f"Exact transit search failed: {str(e)}")
