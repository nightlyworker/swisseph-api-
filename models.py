"""Pydantic models for Swiss Ephemeris API request/response validation."""

from datetime import datetime
from enum import Enum
from typing import Optional

import pytz
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic import ConfigDict


# Enums
class NodeTypeEnum(str, Enum):
    """Type of lunar node calculation."""
    TRUE = "true"
    MEAN = "mean"


class ZodiacTypeEnum(str, Enum):
    """Type of zodiac system."""
    TROPICAL = "tropical"
    SIDEREAL = "sidereal"


class PartOfFortuneFormulaEnum(str, Enum):
    """Formula for calculating Part of Fortune."""
    TRADITIONAL = "traditional"
    MODERN = "modern"


class HouseSystemEnum(str, Enum):
    """Available house systems."""
    PLACIDUS = "Placidus"
    KOCH = "Koch"
    EQUAL_ASC = "Equal (ASC)"
    EQUAL_MC = "Equal (MC)"
    WHOLE_SIGN = "Whole Sign"
    CAMPANUS = "Campanus"
    REGIOMONTANUS = "Regiomontanus"
    PORPHYRY = "Porphyry"
    MORINUS = "Morinus"
    ALCABITIUS = "Alcabitius"
    TOPOCENTRIC = "Topocentric"


# Request Models
class NatalChartRequest(BaseModel):
    """Request model for natal chart calculation."""

    birth_date: datetime = Field(
        ...,
        description="Birth date and time in ISO 8601 format",
        examples=["1990-06-15T14:30:00"]
    )
    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitude in decimal degrees (-90 to 90)"
    )
    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitude in decimal degrees (-180 to 180)"
    )
    timezone: Optional[str] = Field(
        None,
        description="IANA timezone name (e.g., 'America/New_York'). If not provided, assumes UTC."
    )
    house_system: HouseSystemEnum = Field(
        default=HouseSystemEnum.PLACIDUS,
        description="House system to use for house calculations"
    )
    node_type: NodeTypeEnum = Field(
        default=NodeTypeEnum.TRUE,
        description="Type of lunar node calculation (true or mean)"
    )
    zodiac_type: ZodiacTypeEnum = Field(
        default=ZodiacTypeEnum.TROPICAL,
        description="Zodiac system (tropical or sidereal)"
    )
    include_minor_aspects: bool = Field(
        default=True,
        description="Include minor aspects in calculations"
    )
    sidereal_mode: int = Field(
        default=1,
        description="Sidereal mode (1 = Lahiri/Chitrapaksha ayanamsa)"
    )
    pof_formula: PartOfFortuneFormulaEnum = Field(
        default=PartOfFortuneFormulaEnum.TRADITIONAL,
        description="Formula for Part of Fortune calculation"
    )

    @field_validator('timezone')
    @classmethod
    def validate_timezone(cls, v: Optional[str]) -> Optional[str]:
        """Validate timezone string."""
        if v is None:
            return v
        try:
            pytz.timezone(v)
            return v
        except pytz.exceptions.UnknownTimeZoneError:
            raise ValueError(f"Unknown timezone: {v}")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "birth_date": "1990-06-15T14:30:00",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "timezone": "America/New_York",
                "house_system": "Placidus",
                "node_type": "true",
                "zodiac_type": "tropical",
                "include_minor_aspects": True,
                "sidereal_mode": 1,
                "pof_formula": "traditional"
            }]
        }
    )


class NatalChartRequestWithId(NatalChartRequest):
    """Natal chart request with optional ID for batch operations."""
    id: Optional[str] = Field(
        None,
        description="Optional identifier for this chart in batch operations"
    )


class NatalChartBatchRequest(BaseModel):
    """Request model for batch natal chart calculations."""
    charts: list[NatalChartRequestWithId] = Field(
        ...,
        description="List of natal charts to calculate"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "charts": [
                    {
                        "id": "chart1",
                        "birth_date": "1990-06-15T14:30:00",
                        "latitude": 40.7128,
                        "longitude": -74.0060,
                        "timezone": "America/New_York"
                    },
                    {
                        "id": "chart2",
                        "birth_date": "1985-03-20T09:15:00",
                        "latitude": 51.5074,
                        "longitude": -0.1278,
                        "timezone": "Europe/London"
                    }
                ]
            }]
        }
    )


class TransitDateInput(BaseModel):
    """Single transit date input for batch operations."""
    id: Optional[str] = Field(
        None,
        description="Optional identifier for this transit date"
    )
    date: datetime = Field(
        ...,
        description="Transit date and time in ISO 8601 format"
    )
    timezone: Optional[str] = Field(
        None,
        description="IANA timezone name for this specific transit date"
    )


class TransitCalculationRequest(BaseModel):
    """Request model for transit calculation."""
    natal_chart: NatalChartRequest = Field(
        ...,
        description="Natal chart data"
    )
    transit_date: datetime = Field(
        ...,
        description="Date and time for transit calculation"
    )
    transit_timezone: Optional[str] = Field(
        None,
        description="Timezone for transit date (defaults to natal chart timezone)"
    )
    include_minor_aspects: bool = Field(
        default=False,
        description="Include minor aspects in transit calculations"
    )
    include_transit_to_transit: bool = Field(
        default=False,
        description="Include aspects between transiting planets"
    )
    orb_factor: float = Field(
        default=1.0,
        ge=0.1,
        le=3.0,
        description="Multiplier for aspect orbs (1.0 = default, <1.0 = tighter, >1.0 = wider)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "natal_chart": {
                    "birth_date": "1990-06-15T14:30:00",
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                    "timezone": "America/New_York"
                },
                "transit_date": "2025-12-25T12:00:00",
                "transit_timezone": "America/New_York",
                "include_minor_aspects": False,
                "include_transit_to_transit": False,
                "orb_factor": 1.0
            }]
        }
    )


class TransitBatchRequest(BaseModel):
    """Request model for batch transit calculations."""
    natal_chart: NatalChartRequest = Field(
        ...,
        description="Natal chart data"
    )
    transit_dates: list[TransitDateInput] = Field(
        ...,
        description="List of transit dates to calculate"
    )
    include_minor_aspects: bool = Field(
        default=False,
        description="Include minor aspects in transit calculations"
    )
    include_transit_to_transit: bool = Field(
        default=False,
        description="Include aspects between transiting planets"
    )
    orb_factor: float = Field(
        default=1.0,
        ge=0.1,
        le=3.0,
        description="Multiplier for aspect orbs"
    )


class ExactTransitsRequest(BaseModel):
    """Request model for finding exact transits in a date range."""
    natal_chart: NatalChartRequest = Field(
        ...,
        description="Natal chart data"
    )
    start_date: datetime = Field(
        ...,
        description="Start of date range for transit search"
    )
    end_date: datetime = Field(
        ...,
        description="End of date range for transit search"
    )
    timezone: Optional[str] = Field(
        None,
        description="Timezone for date range"
    )
    planets: Optional[list[str]] = Field(
        None,
        description="Filter by specific transiting planets (default: all major planets)"
    )
    aspects: Optional[list[str]] = Field(
        None,
        description="Filter by specific aspects (default: major aspects)"
    )
    natal_points: Optional[list[str]] = Field(
        None,
        description="Filter by specific natal points (default: all planets + angles)"
    )

    @model_validator(mode='after')
    def validate_date_range(self):
        """Ensure end_date is after start_date."""
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [{
                "natal_chart": {
                    "birth_date": "1990-06-15T14:30:00",
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                    "timezone": "America/New_York"
                },
                "start_date": "2025-12-25T00:00:00",
                "end_date": "2026-01-25T00:00:00",
                "timezone": "America/New_York",
                "planets": ["Sun", "Mercury", "Venus", "Mars", "Jupiter", "Saturn"],
                "aspects": ["Conjunction", "Square", "Trine", "Opposition"],
                "natal_points": ["Sun", "Moon", "Natal ASC", "Natal MC"]
            }]
        }
    )


# Response Models
class MetadataResponse(BaseModel):
    """Metadata for natal chart."""
    birth_date_local: str
    birth_date_utc: str
    timezone: str
    latitude: float
    longitude: float
    house_system: str
    zodiac_type: str
    node_type: str
    julian_day: float
    is_day_chart: bool


class PlanetPosition(BaseModel):
    """Planet position data."""
    longitude: float
    latitude: float
    distance: float
    speed: float
    retrograde: bool
    sign: str
    sign_symbol: str
    sign_num: int
    degree: float
    degree_int: int
    minutes: int
    element: str
    modality: str
    ruler: str
    formatted: str
    formatted_short: str
    dignity: Optional[str] = None
    house: Optional[int] = None


class HouseCuspInfo(BaseModel):
    """Information about a house cusp."""
    house: int
    longitude: float
    sign: str
    sign_symbol: str
    degree: float
    degree_int: int
    minutes: int
    formatted: str


class HousesData(BaseModel):
    """House system data."""
    cusps: list[float]
    ascendant: float
    mc: float
    armc: float
    vertex: float
    ic: float
    descendant: float
    ascendant_sign: str
    ascendant_degree: float
    ascendant_formatted: str
    mc_sign: str
    mc_degree: float
    mc_formatted: str
    ic_sign: str
    ic_degree: float
    ic_formatted: str
    descendant_sign: str
    descendant_degree: float
    descendant_formatted: str
    vertex_sign: str
    vertex_degree: float
    vertex_formatted: str
    cusp_signs: list[HouseCuspInfo]


class AspectData(BaseModel):
    """Aspect between two points."""
    planet1: str
    planet2: str
    aspect: str
    symbol: str
    angle: float
    orb: float
    max_orb: float
    applying: bool
    major: bool


class NatalChartResponse(BaseModel):
    """Complete natal chart response."""
    metadata: MetadataResponse
    planets: dict[str, PlanetPosition]
    houses: HousesData
    aspects: list[AspectData]


class TransitPlanetData(BaseModel):
    """Transiting planet data."""
    longitude: float
    speed: float
    retrograde: bool
    sign: str
    sign_symbol: str
    degree: float
    formatted: str
    natal_house: int


class TransitAspectData(BaseModel):
    """Transit aspect to natal point."""
    transit_planet: str
    natal_planet: str
    aspect: str
    symbol: str
    angle: float
    orb: float
    max_orb: float
    applying: bool
    major: bool
    transit_retrograde: bool
    transit_house: int


class TransitResponse(BaseModel):
    """Transit calculation response."""
    transit_date: str
    transit_date_utc: str
    transit_planets: dict[str, TransitPlanetData]
    transit_to_natal: list[TransitAspectData]
    transit_to_transit: list[AspectData]


class TransitEventData(BaseModel):
    """Exact transit event."""
    transit_planet: str
    natal_planet: str
    aspect: str
    aspect_symbol: str
    exact_date: datetime
    orb: float
    applying: bool
    transit_retrograde: bool


class ExactTransitsResponse(BaseModel):
    """Response for exact transits search."""
    events: list[TransitEventData]
    count: int


class ErrorDetail(BaseModel):
    """Error detail for batch operations."""
    type: str
    message: str
    detail: Optional[dict] = None


class BatchResultItem(BaseModel):
    """Single result in a batch operation."""
    id: Optional[str]
    success: bool
    data: Optional[NatalChartResponse | TransitResponse] = None
    error: Optional[ErrorDetail] = None


class BatchSummary(BaseModel):
    """Summary statistics for batch operation."""
    total: int
    successful: int
    failed: int


class BatchResponse(BaseModel):
    """Response for batch operations."""
    results: list[BatchResultItem]
    summary: BatchSummary


class AspectDefinitionResponse(BaseModel):
    """Aspect definition with orbs."""
    name: str
    symbol: str
    angle: float
    natal_orbs: dict[str, float]
    transit_orbs: dict[str, float]


class ConfigAspectsResponse(BaseModel):
    """Configuration response for aspects."""
    major_aspects: list[AspectDefinitionResponse]
    minor_aspects: list[AspectDefinitionResponse]


class ConfigHouseSystemsResponse(BaseModel):
    """Configuration response for house systems."""
    house_systems: list[str]
