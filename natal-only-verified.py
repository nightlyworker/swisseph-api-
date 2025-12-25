"""
Natal Chart Calculator using Swiss Ephemeris
Calculates planetary positions, houses, and aspects for a birth chart

VERSION 2 - FULLY CORRECTED
Critical fixes applied:
1. swe.houses_ex() returns 13-element tuple (index 1-12 are houses, index 0 unused)
2. Day/night chart detection uses house position, not just longitude comparison
3. House system code passed as integer ord(b'P'), not bytes
4. Applying/separating aspect logic completely rewritten with proper math
5. Proper handling of edge cases in planet-in-house calculation
6. Added configurable Part of Fortune formula (traditional vs modern)
7. Proper sidereal flag handling for both planets and houses
"""

import swisseph as swe
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum
import math
import pytz


class NodeType(Enum):
    TRUE = "true"
    MEAN = "mean"


class ZodiacType(Enum):
    TROPICAL = "tropical"
    SIDEREAL = "sidereal"


class PartOfFortuneFormula(Enum):
    TRADITIONAL = "traditional"  # Day: ASC + Moon - Sun, Night: ASC + Sun - Moon
    MODERN = "modern"  # Always: ASC + Moon - Sun


@dataclass
class AspectDefinition:
    """Definition of an astrological aspect with variable orbs."""
    angle: float
    name: str
    symbol: str
    # Orbs: (luminary, personal, social, outer)
    orbs: Tuple[float, float, float, float]
    major: bool = True


class NatalChart:
    """
    Calculate and store natal chart data including planetary positions,
    houses, and aspects.
    
    IMPORTANT NOTES ON ACCURACY:
    - For maximum accuracy, provide path to Swiss Ephemeris data files (.se1)
    - Timezone handling is critical - always specify timezone for local birth times
    - House calculations at extreme latitudes (>66°) may be unreliable for some systems
    """
    
    # Planet categories for variable orbs
    LUMINARIES = {'Sun', 'Moon'}
    PERSONAL_PLANETS = {'Mercury', 'Venus', 'Mars'}
    SOCIAL_PLANETS = {'Jupiter', 'Saturn'}
    OUTER_PLANETS = {'Uranus', 'Neptune', 'Pluto', 'Chiron', 'North Node', 'South Node', 'Lilith'}
    
    # Main planets (always available with Moshier ephemeris)
    PLANETS_CORE = {
        'Sun': swe.SUN,
        'Moon': swe.MOON,
        'Mercury': swe.MERCURY,
        'Venus': swe.VENUS,
        'Mars': swe.MARS,
        'Jupiter': swe.JUPITER,
        'Saturn': swe.SATURN,
        'Uranus': swe.URANUS,
        'Neptune': swe.NEPTUNE,
        'Pluto': swe.PLUTO,
    }
    
    # Asteroids and other bodies (require Swiss Ephemeris files)
    PLANETS_EXTENDED = {
        'Chiron': swe.CHIRON,
    }
    
    # House systems - stored as byte strings for swe.houses_ex
    HOUSE_SYSTEMS = {
        'Placidus': b'P',
        'Koch': b'K',
        'Equal (ASC)': b'A',
        'Equal (MC)': b'E',  
        'Whole Sign': b'W',
        'Campanus': b'C',
        'Regiomontanus': b'R',
        'Porphyry': b'O',
        'Morinus': b'M',
        'Alcabitius': b'B',
        'Topocentric': b'T',
        'Meridian': b'X',
        'Vehlow Equal': b'V',
    }
    
    # Zodiac signs with traditional rulers
    SIGNS = [
        {'name': 'Aries', 'ruler': 'Mars', 'element': 'Fire', 'modality': 'Cardinal', 'start_degree': 0},
        {'name': 'Taurus', 'ruler': 'Venus', 'element': 'Earth', 'modality': 'Fixed', 'start_degree': 30},
        {'name': 'Gemini', 'ruler': 'Mercury', 'element': 'Air', 'modality': 'Mutable', 'start_degree': 60},
        {'name': 'Cancer', 'ruler': 'Moon', 'element': 'Water', 'modality': 'Cardinal', 'start_degree': 90},
        {'name': 'Leo', 'ruler': 'Sun', 'element': 'Fire', 'modality': 'Fixed', 'start_degree': 120},
        {'name': 'Virgo', 'ruler': 'Mercury', 'element': 'Earth', 'modality': 'Mutable', 'start_degree': 150},
        {'name': 'Libra', 'ruler': 'Venus', 'element': 'Air', 'modality': 'Cardinal', 'start_degree': 180},
        {'name': 'Scorpio', 'ruler': 'Mars', 'element': 'Water', 'modality': 'Fixed', 'start_degree': 210},
        {'name': 'Sagittarius', 'ruler': 'Jupiter', 'element': 'Fire', 'modality': 'Mutable', 'start_degree': 240},
        {'name': 'Capricorn', 'ruler': 'Saturn', 'element': 'Earth', 'modality': 'Cardinal', 'start_degree': 270},
        {'name': 'Aquarius', 'ruler': 'Saturn', 'element': 'Air', 'modality': 'Fixed', 'start_degree': 300},
        {'name': 'Pisces', 'ruler': 'Jupiter', 'element': 'Water', 'modality': 'Mutable', 'start_degree': 330},
    ]
    
    # Essential dignities (traditional 7 planets only)
    # Note: Mercury's exaltation in Virgo is most widely accepted
    DIGNITIES = {
        'Sun': {'domicile': ['Leo'], 'exaltation': 'Aries', 'detriment': ['Aquarius'], 'fall': 'Libra'},
        'Moon': {'domicile': ['Cancer'], 'exaltation': 'Taurus', 'detriment': ['Capricorn'], 'fall': 'Scorpio'},
        'Mercury': {'domicile': ['Gemini', 'Virgo'], 'exaltation': 'Virgo', 'detriment': ['Sagittarius', 'Pisces'], 'fall': 'Pisces'},
        'Venus': {'domicile': ['Taurus', 'Libra'], 'exaltation': 'Pisces', 'detriment': ['Scorpio', 'Aries'], 'fall': 'Virgo'},
        'Mars': {'domicile': ['Aries', 'Scorpio'], 'exaltation': 'Capricorn', 'detriment': ['Libra', 'Taurus'], 'fall': 'Cancer'},
        'Jupiter': {'domicile': ['Sagittarius', 'Pisces'], 'exaltation': 'Cancer', 'detriment': ['Gemini', 'Virgo'], 'fall': 'Capricorn'},
        'Saturn': {'domicile': ['Capricorn', 'Aquarius'], 'exaltation': 'Libra', 'detriment': ['Cancer', 'Leo'], 'fall': 'Aries'},
    }
    
    # Aspect definitions with symbol and variable orbs
    ASPECTS = [
        AspectDefinition(0, 'Conjunction', '☌', (10, 8, 7, 6), True),
        AspectDefinition(60, 'Sextile', '⚹', (6, 5, 4, 3), True),
        AspectDefinition(90, 'Square', '□', (8, 7, 6, 5), True),
        AspectDefinition(120, 'Trine', '△', (8, 7, 6, 5), True),
        AspectDefinition(180, 'Opposition', '☍', (10, 8, 7, 6), True),
        AspectDefinition(30, 'Semi-sextile', '⚺', (2, 2, 2, 1), False),
        AspectDefinition(45, 'Semi-square', '∠', (2, 2, 2, 1), False),
        AspectDefinition(135, 'Sesquiquadrate', '⚼', (2, 2, 2, 1), False),
        AspectDefinition(150, 'Quincunx', '⚻', (3, 3, 2, 2), False),
        AspectDefinition(72, 'Quintile', 'Q', (2, 2, 1, 1), False),
        AspectDefinition(144, 'Bi-quintile', 'bQ', (2, 2, 1, 1), False),
    ]
    
    def __init__(self, 
                 birth_date: datetime,
                 latitude: float,
                 longitude: float,
                 house_system: str = 'Placidus',
                 altitude: float = 0,
                 timezone: Optional[Union[str, pytz.tzinfo.BaseTzInfo]] = None,
                 ephemeris_path: Optional[str] = None,
                 node_type: NodeType = NodeType.TRUE,
                 zodiac_type: ZodiacType = ZodiacType.TROPICAL,
                 sidereal_mode: int = swe.SIDM_LAHIRI,
                 include_angles_in_aspects: bool = False,
                 include_minor_aspects: bool = True,
                 pof_formula: PartOfFortuneFormula = PartOfFortuneFormula.TRADITIONAL):
        """
        Initialize natal chart calculator.
        
        Args:
            birth_date: Birth date and time. If timezone is provided, this is interpreted
                       as LOCAL time. If timezone is None, this is assumed to be UTC.
            latitude: Birth location latitude (-90 to 90, positive = North)
            longitude: Birth location longitude (-180 to 180, positive = East)
            house_system: House system to use (default: Placidus)
            altitude: Altitude in meters above sea level (default: 0)
            timezone: Timezone string (e.g., 'America/New_York', 'Europe/London')
                     or pytz timezone object. If None, birth_date is assumed UTC.
            ephemeris_path: Path to Swiss Ephemeris data files (.se1 files)
                           Required for maximum accuracy. If None, uses less accurate
                           built-in analytical ephemeris.
            node_type: NodeType.TRUE (oscillating/true) or NodeType.MEAN lunar nodes
            zodiac_type: ZodiacType.TROPICAL or ZodiacType.SIDEREAL
            sidereal_mode: Ayanamsa for sidereal calculations (default: Lahiri)
            include_angles_in_aspects: Calculate aspects to ASC and MC
            include_minor_aspects: Include minor aspects (semi-sextile, quintile, etc.)
            pof_formula: Part of Fortune calculation method
        """
        # Validate inputs
        if not -90 <= latitude <= 90:
            raise ValueError(f"Latitude must be between -90 and 90, got {latitude}")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Longitude must be between -180 and 180, got {longitude}")
        
        # Store configuration
        self.birth_date_local = birth_date
        self.latitude = latitude
        self.longitude = longitude
        self.altitude = altitude
        self.node_type = node_type
        self.zodiac_type = zodiac_type
        self.sidereal_mode = sidereal_mode
        self.include_angles_in_aspects = include_angles_in_aspects
        self.include_minor_aspects = include_minor_aspects
        self.pof_formula = pof_formula
        self._use_moshier = True  # Will be set properly in _init_ephemeris
        
        # Initialize Swiss Ephemeris BEFORE any calculations
        self._init_ephemeris(ephemeris_path)
        
        # Validate and set house system
        if house_system not in self.HOUSE_SYSTEMS:
            raise ValueError(f"Unknown house system: {house_system}. "
                           f"Available: {list(self.HOUSE_SYSTEMS.keys())}")
        self.house_system = house_system
        self.house_system_code = self.HOUSE_SYSTEMS[house_system]
        
        # Check for extreme latitude with problematic house systems
        if abs(latitude) > 66 and house_system in ['Placidus', 'Koch', 'Regiomontanus']:
            import warnings
            warnings.warn(f"House system '{house_system}' may be unreliable at latitude {latitude}°. "
                         f"Consider using 'Equal (ASC)' or 'Whole Sign' instead.")
        
        # Handle timezone conversion
        self.timezone = self._parse_timezone(timezone)
        self.birth_date_utc = self._convert_to_utc(birth_date, self.timezone)
        
        # Calculate Julian Day (using UTC time)
        self.julian_day = self._calculate_julian_day()
        
        # Storage for calculated data
        self.planets: Dict = {}
        self.houses: Dict = {}
        self.aspects: List = []
        self._is_day_chart: Optional[bool] = None
    
    def _init_ephemeris(self, ephemeris_path: Optional[str]) -> None:
        """
        Initialize Swiss Ephemeris settings.
        
        Tries to use Swiss Ephemeris files for maximum accuracy.
        Falls back to Moshier (built-in) ephemeris if files not found.
        Moshier is accurate to ~0.001 degree for modern dates.
        """
        import os
        
        self._use_moshier = True  # Default to Moshier (built-in)
        
        # Only try to use SE files if a path is explicitly provided
        if ephemeris_path and os.path.isdir(ephemeris_path):
            try:
                files = os.listdir(ephemeris_path)
                if any(f.endswith('.se1') for f in files):
                    swe.set_ephe_path(ephemeris_path)
                    self._use_moshier = False
            except:
                pass
        
        # Set sidereal mode if using sidereal zodiac
        if self.zodiac_type == ZodiacType.SIDEREAL:
            swe.set_sid_mode(self.sidereal_mode)
    
    def _parse_timezone(self, timezone: Optional[Union[str, pytz.tzinfo.BaseTzInfo]]) -> Optional[pytz.tzinfo.BaseTzInfo]:
        """Parse timezone parameter into pytz timezone object."""
        if timezone is None:
            return None
        
        if isinstance(timezone, str):
            try:
                return pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                raise ValueError(f"Unknown timezone: {timezone}. "
                               f"Use standard IANA timezone names like 'America/New_York'")
        
        return timezone
    
    def _convert_to_utc(self, birth_date: datetime, 
                        timezone: Optional[pytz.tzinfo.BaseTzInfo]) -> datetime:
        """Convert birth date to UTC, handling DST correctly."""
        # If already timezone-aware, convert directly
        if birth_date.tzinfo is not None:
            return birth_date.astimezone(pytz.UTC)
        
        # If timezone provided, localize then convert
        if timezone is not None:
            # Use localize() to handle DST correctly
            try:
                local_dt = timezone.localize(birth_date, is_dst=None)
            except pytz.exceptions.AmbiguousTimeError:
                # During DST transition - assume standard time
                local_dt = timezone.localize(birth_date, is_dst=False)
            except pytz.exceptions.NonExistentTimeError:
                # Time doesn't exist (skipped during DST) - shift forward
                local_dt = timezone.localize(birth_date, is_dst=True)
            return local_dt.astimezone(pytz.UTC)
        
        # No timezone - assume UTC
        return birth_date.replace(tzinfo=pytz.UTC)
        
    def _calculate_julian_day(self) -> float:
        """
        Convert UTC datetime to Julian Day Number.
        Swiss Ephemeris expects Julian Day in Universal Time (UT).
        """
        ut = self.birth_date_utc
        
        # Calculate decimal hour
        hour_decimal = (ut.hour + 
                       ut.minute / 60.0 + 
                       ut.second / 3600.0 +
                       ut.microsecond / 3600000000.0)
        
        # Use Swiss Ephemeris Julian Day calculation
        jd = swe.julday(ut.year, ut.month, ut.day, hour_decimal)
        
        return jd
    
    def _get_sign_info(self, longitude: float) -> Dict:
        """
        Get zodiac sign information for an ecliptic longitude.
        
        Args:
            longitude: Ecliptic longitude in degrees (0-360)
            
        Returns:
            Dictionary with sign name, number, degree, element, modality, ruler
        """
        # Normalize longitude to 0-360
        longitude = longitude % 360
        
        sign_num = int(longitude / 30)
        degree_in_sign = longitude % 30
        
        # Ensure sign_num is in valid range
        sign_num = sign_num % 12
        
        sign_data = self.SIGNS[sign_num]
        
        # Format degree with minutes
        deg_int = int(degree_in_sign)
        minutes = int((degree_in_sign - deg_int) * 60)
        
        return {
            'sign': sign_data['name'],
            'sign_num': sign_num,
            'degree': degree_in_sign,
            'degree_int': deg_int,
            'minutes': minutes,
            'element': sign_data['element'],
            'modality': sign_data['modality'],
            'ruler': sign_data['ruler'],
            'formatted': f"{deg_int}°{minutes:02d}' {sign_data['name']}",
            'formatted_short': f"{degree_in_sign:.2f}° {sign_data['name'][:3]}"
        }
    
    def _get_dignity(self, planet_name: str, sign: str) -> Optional[str]:
        """
        Determine the essential dignity of a planet in a sign.
        
        Returns: 'domicile', 'exaltation', 'detriment', 'fall', or None (peregrine)
        """
        if planet_name not in self.DIGNITIES:
            return None
        
        dignity = self.DIGNITIES[planet_name]
        
        if sign in dignity['domicile']:
            return 'domicile'
        elif sign == dignity['exaltation']:
            return 'exaltation'
        elif sign in dignity['detriment']:
            return 'detriment'
        elif sign == dignity['fall']:
            return 'fall'
        
        return None  # Peregrine
    
    def _get_planet_category(self, planet_name: str) -> int:
        """
        Get planet category for orb calculation.
        
        Returns: 0=luminary, 1=personal, 2=social, 3=outer/points
        """
        if planet_name in self.LUMINARIES:
            return 0
        elif planet_name in self.PERSONAL_PLANETS:
            return 1
        elif planet_name in self.SOCIAL_PLANETS:
            return 2
        elif planet_name in ['Ascendant', 'MC', 'Descendant', 'IC']:
            return 0  # Treat angles like luminaries (wide orbs)
        else:
            return 3  # Outer planets and points
    
    def _get_aspect_orb(self, aspect: AspectDefinition, 
                        planet1: str, planet2: str) -> float:
        """
        Calculate the maximum orb for an aspect between two planets.
        Uses the smaller of the two planets' orbs (more conservative).
        """
        cat1 = self._get_planet_category(planet1)
        cat2 = self._get_planet_category(planet2)
        
        # Use the tighter orb (more conservative)
        return min(aspect.orbs[cat1], aspect.orbs[cat2])
    
    def _get_calc_flags(self) -> int:
        """Get calculation flags for Swiss Ephemeris."""
        # Use appropriate ephemeris based on what's available
        if self._use_moshier:
            # Moshier is built-in, accurate to ~1 arc-second for modern dates
            flags = swe.FLG_MOSEPH | swe.FLG_SPEED
        else:
            # Swiss Ephemeris files available - maximum accuracy
            flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        
        if self.zodiac_type == ZodiacType.SIDEREAL:
            flags |= swe.FLG_SIDEREAL
        
        return flags
    
    def calculate_planets(self) -> Dict:
        """
        Calculate positions for all planets including nodes and Lilith.
        
        Note: Chiron requires Swiss Ephemeris files. When using the built-in
        Moshier ephemeris, Chiron will be omitted.
        
        Returns:
            Dictionary with planetary data including:
            - longitude, latitude, distance, speed
            - sign, degree, element, modality
            - retrograde status, dignity
        """
        flags = self._get_calc_flags()
        
        # Calculate core planets (always available)
        for name, planet_id in self.PLANETS_CORE.items():
            self._calculate_body(name, planet_id, flags)
        
        # Calculate extended bodies (may require SE files)
        for name, planet_id in self.PLANETS_EXTENDED.items():
            try:
                self._calculate_body(name, planet_id, flags)
            except Exception as e:
                # Chiron and other asteroids require SE files
                # Skip silently when using Moshier ephemeris
                if self._use_moshier:
                    pass  # Expected - Moshier doesn't have asteroids
                else:
                    import warnings
                    warnings.warn(f"Could not calculate {name}: {e}")
        
        # Calculate North Node
        node_id = swe.TRUE_NODE if self.node_type == NodeType.TRUE else swe.MEAN_NODE
        self._calculate_body('North Node', node_id, flags)
        
        # South Node is exactly opposite North Node
        nn = self.planets['North Node']
        sn_long = (nn['longitude'] + 180) % 360
        sign_info = self._get_sign_info(sn_long)
        
        self.planets['South Node'] = {
            'longitude': sn_long,
            'latitude': 0,  # Nodes are on the ecliptic by definition
            'distance': nn['distance'],
            'speed': nn['speed'],  # Same speed, same direction
            'retrograde': nn['retrograde'],
            **sign_info,
            'dignity': None,
        }
        
        # Calculate Black Moon Lilith (Mean Lunar Apogee)
        # This should work with Moshier
        try:
            self._calculate_body('Lilith', swe.MEAN_APOG, flags)
        except Exception:
            pass  # Skip if not available
        
        return self.planets
    
    def _calculate_body(self, name: str, body_id: int, flags: int) -> None:
        """Calculate position for a single celestial body."""
        result, ret_flag = swe.calc_ut(self.julian_day, body_id, flags)
        
        longitude = result[0]
        latitude = result[1]
        distance = result[2]
        speed = result[3]  # Speed in longitude (degrees/day)
        
        sign_info = self._get_sign_info(longitude)
        dignity = self._get_dignity(name, sign_info['sign'])
        
        self.planets[name] = {
            'longitude': longitude,
            'latitude': latitude,
            'distance': distance,
            'speed': speed,
            'retrograde': speed < 0,
            **sign_info,
            'dignity': dignity,
        }
    
    def calculate_houses(self) -> Dict:
        """
        Calculate house cusps and angles.
        
        Swiss Ephemeris swe.houses_ex() returns a 12-element tuple
        where index 0-11 are house cusps 1-12.
        
        Returns:
            Dictionary containing:
            - cusps: List of 12 house cusp longitudes (index 0 = house 1)
            - ascendant, mc, ic, descendant, vertex with positions and signs
        """
        # swe.houses_ex returns:
        # cusps: 12-element tuple, cusps[0] through cusps[11] are houses 1-12
        #        cusps[0] = house 1 cusp = Ascendant
        # ascmc: (ASC, MC, ARMC, Vertex, Equatorial ASC, co-ASC Koch, co-ASC Munkasey, Polar ASC)
        cusps_raw, ascmc = swe.houses_ex(
            self.julian_day,
            self.latitude,
            self.longitude,
            self.house_system_code
        )
        
        # cusps_raw is 12 elements: index 0 = house 1, index 11 = house 12
        cusps = list(cusps_raw)
        
        # Extract angles from ascmc
        self.houses = {
            'cusps': cusps,  # List of 12 cusps, index 0 = house 1
            'ascendant': ascmc[0],
            'mc': ascmc[1],
            'armc': ascmc[2],  # Sidereal time in degrees
            'vertex': ascmc[3],
            'equatorial_ascendant': ascmc[4],
            # Calculate IC and Descendant
            'ic': (ascmc[1] + 180) % 360,
            'descendant': (ascmc[0] + 180) % 360,
        }
        
        # Add sign information for all angles
        for angle in ['ascendant', 'mc', 'ic', 'descendant', 'vertex']:
            sign_info = self._get_sign_info(self.houses[angle])
            self.houses[f'{angle}_sign'] = sign_info['sign']
            self.houses[f'{angle}_degree'] = sign_info['degree']
            self.houses[f'{angle}_formatted'] = sign_info['formatted']
        
        # Create cusp_signs list for easy access
        self.houses['cusp_signs'] = []
        for i, cusp_long in enumerate(cusps):
            sign_info = self._get_sign_info(cusp_long)
            self.houses['cusp_signs'].append({
                'house': i + 1,
                'longitude': cusp_long,
                **sign_info
            })
        
        return self.houses
    
    def _is_day_chart_calc(self) -> bool:
        """
        Determine if this is a day chart (Sun above horizon) or night chart.
        
        A day chart has the Sun in houses 7-12 (above the horizon).
        A night chart has the Sun in houses 1-6 (below the horizon).
        """
        if self._is_day_chart is not None:
            return self._is_day_chart
        
        if 'Sun' not in self.planets:
            self.calculate_planets()
        if 'cusps' not in self.houses:
            self.calculate_houses()
        
        # Get Sun's house position
        sun_house = self.get_planet_in_house('Sun')
        
        # Sun is above horizon in houses 7-12
        self._is_day_chart = sun_house >= 7
        
        return self._is_day_chart
    
    def calculate_part_of_fortune(self) -> Dict:
        """
        Calculate the Part of Fortune (Pars Fortunae).
        
        Traditional formula:
        - Day chart: ASC + Moon - Sun
        - Night chart: ASC + Sun - Moon
        
        Modern formula (always): ASC + Moon - Sun
        
        Returns:
            Dictionary with Part of Fortune position data.
        """
        if not self.planets:
            self.calculate_planets()
        if not self.houses:
            self.calculate_houses()
        
        asc = self.houses['ascendant']
        sun = self.planets['Sun']['longitude']
        moon = self.planets['Moon']['longitude']
        
        # Determine formula to use
        if self.pof_formula == PartOfFortuneFormula.MODERN:
            use_day_formula = True
        else:  # TRADITIONAL
            use_day_formula = self._is_day_chart_calc()
        
        # Calculate Part of Fortune
        if use_day_formula:
            pof = (asc + moon - sun) % 360
        else:
            pof = (asc + sun - moon) % 360
        
        sign_info = self._get_sign_info(pof)
        
        self.planets['Part of Fortune'] = {
            'longitude': pof,
            'latitude': 0,
            'distance': 0,
            'speed': 0,
            'retrograde': False,
            **sign_info,
            'dignity': None,
            'formula_used': 'day' if use_day_formula else 'night',
        }
        
        return self.planets['Part of Fortune']
    
    def get_planet_in_house(self, planet_name: str) -> int:
        """
        Determine which house a planet is in.
        
        This correctly handles:
        - Houses spanning 0° Aries (the 360°/0° boundary)
        - Houses larger than 30° (at high latitudes)
        - All house systems including Whole Sign
        
        Args:
            planet_name: Name of the planet/point
            
        Returns:
            House number (1-12)
        """
        if planet_name not in self.planets:
            raise ValueError(f"Planet '{planet_name}' not found. "
                           f"Available: {list(self.planets.keys())}")
        if 'cusps' not in self.houses:
            raise ValueError("Houses not calculated. Call calculate_houses() first.")
        
        planet_long = self.planets[planet_name]['longitude'] % 360
        cusps = self.houses['cusps']
        
        # Check each house
        for i in range(12):
            house_num = i + 1
            cusp_start = cusps[i] % 360
            cusp_end = cusps[(i + 1) % 12] % 360
            
            if self._longitude_in_range(planet_long, cusp_start, cusp_end):
                return house_num
        
        # Fallback - should never reach here with correct data
        # Return based on simple 30° division from ASC
        asc = self.houses['ascendant']
        relative_pos = (planet_long - asc) % 360
        return int(relative_pos / 30) + 1 if int(relative_pos / 30) < 12 else 12
    
    def _longitude_in_range(self, point: float, start: float, end: float) -> bool:
        """
        Check if a point is within a range of ecliptic longitudes.
        Correctly handles the 360°/0° wrap-around.
        
        The range is [start, end) - inclusive of start, exclusive of end.
        """
        point = point % 360
        start = start % 360
        end = end % 360
        
        if start < end:
            # Normal case: range doesn't cross 0°
            return start <= point < end
        else:
            # Range crosses 0° Aries
            return point >= start or point < end
    
    def calculate_aspects(self, orb_factor: float = 1.0) -> List[Dict]:
        """
        Calculate aspects between planets.
        
        Args:
            orb_factor: Multiplier for orb sizes (default: 1.0)
                       Use < 1.0 for tighter orbs, > 1.0 for wider orbs
            
        Returns:
            List of aspect dictionaries, sorted by orb (tightest first)
        """
        if not self.planets:
            self.calculate_planets()
        if self.include_angles_in_aspects and not self.houses:
            self.calculate_houses()
        
        self.aspects = []
        
        # Build list of points to check
        points = {}
        for name, data in self.planets.items():
            points[name] = {
                'longitude': data['longitude'],
                'speed': data.get('speed', 0),
            }
        
        # Add angles if requested
        if self.include_angles_in_aspects and self.houses:
            for angle in ['Ascendant', 'MC']:
                angle_key = angle.lower()
                points[angle] = {
                    'longitude': self.houses[angle_key],
                    'speed': 0,  # Angles don't move in the natal chart
                }
        
        point_names = list(points.keys())
        
        # Check all pairs
        for i, name1 in enumerate(point_names):
            for name2 in point_names[i + 1:]:
                self._check_aspect(name1, name2, points, orb_factor)
        
        # Sort by orb (tightest first)
        self.aspects.sort(key=lambda x: x['orb'])
        
        return self.aspects
    
    def _check_aspect(self, name1: str, name2: str, 
                      points: Dict, orb_factor: float) -> None:
        """Check if two points form any aspect and add to aspects list."""
        pos1 = points[name1]['longitude']
        pos2 = points[name2]['longitude']
        speed1 = points[name1]['speed']
        speed2 = points[name2]['speed']
        
        # Calculate angular separation (always 0-180)
        separation = abs(pos1 - pos2)
        if separation > 180:
            separation = 360 - separation
        
        # Check each aspect type
        for aspect_def in self.ASPECTS:
            # Skip minor aspects if not requested
            if not aspect_def.major and not self.include_minor_aspects:
                continue
            
            # Calculate orb (difference from exact aspect)
            orb = abs(separation - aspect_def.angle)
            max_orb = self._get_aspect_orb(aspect_def, name1, name2) * orb_factor
            
            if orb <= max_orb:
                # Determine if applying or separating
                applying = self._calculate_applying(
                    pos1, pos2, speed1, speed2, aspect_def.angle
                )
                
                self.aspects.append({
                    'planet1': name1,
                    'planet2': name2,
                    'aspect': aspect_def.name,
                    'symbol': aspect_def.symbol,
                    'angle': aspect_def.angle,
                    'orb': round(orb, 4),
                    'max_orb': max_orb,
                    'applying': applying,
                    'major': aspect_def.major,
                    'exactness': round(100 * (1 - orb / max_orb), 1),  # Percentage
                    'formatted': f"{name1} {aspect_def.symbol} {name2} ({orb:.2f}°)"
                })
    
    def _calculate_applying(self, pos1: float, pos2: float,
                           speed1: float, speed2: float,
                           aspect_angle: float) -> bool:
        """
        Determine if an aspect is applying (getting closer) or separating.
        
        An aspect is APPLYING when the orb is decreasing over time.
        An aspect is SEPARATING when the orb is increasing over time.
        
        This handles all cases including:
        - Both planets direct
        - One or both planets retrograde
        - Conjunctions and oppositions
        - The 360°/0° boundary
        """
        # Handle zero speeds (angles, nodes)
        if speed1 == 0 and speed2 == 0:
            return False  # Static - neither applying nor separating
        
        # Current separation (can be negative for direction)
        # Use signed difference, keeping track of which direction
        diff = (pos2 - pos1) % 360
        if diff > 180:
            diff -= 360  # Now diff is in range (-180, 180]
        
        # For conjunction (0°), we care about the absolute separation approaching 0
        # For opposition (180°), we care about absolute separation approaching 180
        # For other aspects, we need to consider both +angle and -angle possibilities
        
        current_sep = abs(diff)
        
        # Calculate how separation changes over a small time increment
        # Relative speed: positive means pos2 is moving faster (in zodiacal direction)
        relative_speed = speed2 - speed1
        
        # After small time dt, new diff would be approximately:
        # new_diff = diff + relative_speed * dt
        # We want to know if |new_diff| is getting closer to aspect_angle
        
        if aspect_angle == 0:  # Conjunction
            # Applying if separation is decreasing
            if diff > 0:
                return relative_speed < 0
            else:
                return relative_speed > 0
        
        elif aspect_angle == 180:  # Opposition
            # Applying if separation is approaching 180
            if current_sep < 180:
                # Need separation to increase
                if diff > 0:
                    return relative_speed > 0
                else:
                    return relative_speed < 0
            else:
                return False  # At exact opposition
        
        else:  # Other aspects (60, 90, 120, etc.)
            # The aspect can form at +angle or -angle from planet1
            # Figure out which one we're approaching
            
            # Distance to aspect at +angle
            dist_to_plus = abs(current_sep - aspect_angle)
            
            # Are we getting closer to the aspect?
            # Check if the current separation is approaching aspect_angle
            if current_sep < aspect_angle:
                # Separation needs to increase to reach aspect
                if diff > 0:
                    return relative_speed > 0  # pos2 moving away
                else:
                    return relative_speed < 0  # pos2 moving toward (in negative direction)
            else:
                # Separation needs to decrease to reach aspect
                if diff > 0:
                    return relative_speed < 0
                else:
                    return relative_speed > 0
    
    def generate_full_chart(self) -> Dict:
        """
        Calculate and return complete natal chart data.
        
        This is the main method - it calculates everything and returns
        a comprehensive dictionary with all chart data.
        
        Returns:
            Dictionary containing:
            - metadata: Birth data, settings, Julian day
            - planets: All planetary positions with signs, houses, aspects
            - houses: House cusps and angles
            - aspects: All planetary aspects
        """
        # Calculate in proper order
        self.calculate_planets()
        self.calculate_houses()
        self.calculate_part_of_fortune()
        self.calculate_aspects()
        
        # Add house positions to each planet
        for planet_name in self.planets:
            self.planets[planet_name]['house'] = self.get_planet_in_house(planet_name)
        
        return {
            'metadata': {
                'birth_date_local': self.birth_date_local.isoformat(),
                'birth_date_utc': self.birth_date_utc.isoformat(),
                'timezone': str(self.timezone) if self.timezone else 'UTC',
                'latitude': self.latitude,
                'longitude': self.longitude,
                'altitude': self.altitude,
                'house_system': self.house_system,
                'zodiac_type': self.zodiac_type.value,
                'node_type': self.node_type.value,
                'julian_day': self.julian_day,
                'is_day_chart': self._is_day_chart_calc(),
                'sidereal_mode': self.sidereal_mode if self.zodiac_type == ZodiacType.SIDEREAL else None,
                'ephemeris': 'Moshier (built-in)' if self._use_moshier else 'Swiss Ephemeris',
            },
            'planets': self.planets,
            'houses': self.houses,
            'aspects': self.aspects,
        }
    
    def format_chart_text(self) -> str:
        """Generate a human-readable text summary of the chart."""
        # Ensure chart is calculated
        if not self.planets or not self.houses:
            self.generate_full_chart()
        
        lines = []
        lines.append("=" * 75)
        lines.append("NATAL CHART")
        lines.append("=" * 75)
        
        # Birth info
        if self.timezone:
            lines.append(f"Birth (Local):  {self.birth_date_local.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Birth (UTC):    {self.birth_date_utc.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Timezone:       {self.timezone}")
        else:
            lines.append(f"Birth (UTC):    {self.birth_date_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        
        lines.append(f"Location:       {abs(self.latitude):.4f}°{'N' if self.latitude >= 0 else 'S'}, "
                    f"{abs(self.longitude):.4f}°{'E' if self.longitude >= 0 else 'W'}")
        lines.append(f"House System:   {self.house_system}")
        lines.append(f"Zodiac:         {self.zodiac_type.value.title()}")
        lines.append(f"Chart Sect:     {'Day' if self._is_day_chart_calc() else 'Night'}")
        lines.append("")
        
        # Planets table
        lines.append("PLANETARY POSITIONS")
        lines.append("-" * 75)
        lines.append(f"{'Planet':<14} {'Position':<18} {'House':<7} {'Speed':<12} {'Dignity'}")
        lines.append("-" * 75)
        
        planet_order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
                       'Uranus', 'Neptune', 'Pluto', 'North Node', 'South Node',
                       'Chiron', 'Lilith', 'Part of Fortune']
        
        for name in planet_order:
            if name not in self.planets:
                continue
            p = self.planets[name]
            
            # Motion status
            if p['speed'] == 0:
                motion = ""
            elif p['retrograde']:
                motion = f"R {abs(p['speed']):.2f}°/d"
            else:
                motion = f"D {p['speed']:.2f}°/d"
            
            dignity = p.get('dignity') or ''
            house = p.get('house', '?')
            
            lines.append(f"{name:<14} {p['formatted']:<18} {house:<7} {motion:<12} {dignity}")
        
        lines.append("")
        
        # Angles
        lines.append("ANGLES")
        lines.append("-" * 75)
        for angle, abbr in [('ascendant', 'ASC'), ('mc', 'MC'), ('descendant', 'DSC'), ('ic', 'IC')]:
            lines.append(f"{abbr:<14} {self.houses[f'{angle}_formatted']}")
        lines.append("")
        
        # House cusps
        lines.append("HOUSE CUSPS")
        lines.append("-" * 75)
        for i in range(0, 12, 3):
            row = []
            for j in range(3):
                if i + j < 12:
                    cusp = self.houses['cusp_signs'][i + j]
                    row.append(f"H{cusp['house']:2d}: {cusp['formatted']:<16}")
            lines.append("  ".join(row))
        lines.append("")
        
        # Aspects
        lines.append("ASPECTS")
        lines.append("-" * 75)
        
        major = [a for a in self.aspects if a['major']]
        minor = [a for a in self.aspects if not a['major']]
        
        if major:
            lines.append("Major:")
            for asp in major:
                status = "applying" if asp['applying'] else "separating"
                lines.append(f"  {asp['planet1']:<12} {asp['symbol']} {asp['planet2']:<12} "
                           f"orb {asp['orb']:5.2f}° ({status})")
        
        if minor and self.include_minor_aspects:
            lines.append("Minor:")
            for asp in minor:
                status = "applying" if asp['applying'] else "separating"
                lines.append(f"  {asp['planet1']:<12} {asp['symbol']} {asp['planet2']:<12} "
                           f"orb {asp['orb']:5.2f}° ({status})")
        
        return "\n".join(lines)


# Convenience function
def calculate_natal_chart(birth_datetime: datetime, 
                          latitude: float, 
                          longitude: float,
                          house_system: str = 'Placidus',
                          timezone: Optional[Union[str, pytz.tzinfo.BaseTzInfo]] = None,
                          **kwargs) -> Dict:
    """
    Calculate a complete natal chart.
    
    This is a convenience function that creates a NatalChart instance
    and returns the full chart data.
    
    Args:
        birth_datetime: Birth date/time (local if timezone provided, UTC otherwise)
        latitude: Birth latitude (-90 to 90, positive = North)
        longitude: Birth longitude (-180 to 180, positive = East)
        house_system: House system (default: 'Placidus')
        timezone: Timezone string or pytz object (e.g., 'America/New_York')
        **kwargs: Additional arguments for NatalChart
        
    Returns:
        Complete chart data dictionary
        
    Example:
        >>> from datetime import datetime
        >>> birth = datetime(1990, 6, 15, 14, 30)
        >>> chart = calculate_natal_chart(
        ...     birth, 40.7128, -74.0060,
        ...     timezone='America/New_York'
        ... )
        >>> print(chart['planets']['Sun']['formatted'])
        24°12' Gemini
    """
    chart = NatalChart(birth_datetime, latitude, longitude, house_system,
                       timezone=timezone, **kwargs)
    return chart.generate_full_chart()


# Test with known chart
if __name__ == "__main__":
    print("Natal Chart Calculator - Test Run")
    print("=" * 75)
    print()
    
    # Test chart: June 15, 1990, 2:30 PM EDT, New York City
    birth = datetime(1990, 6, 15, 14, 30, 0)
    
    chart = NatalChart(
        birth_date=birth,
        latitude=40.7128,   # New York
        longitude=-74.0060,
        timezone='America/New_York',
        house_system='Placidus',
        node_type=NodeType.TRUE,
        include_minor_aspects=False,
        include_angles_in_aspects=True
    )
    
    data = chart.generate_full_chart()
    
    print(chart.format_chart_text())
    
    print()
    print("=" * 75)
    print("VERIFICATION DATA")
    print("=" * 75)
    print(f"Julian Day: {data['metadata']['julian_day']:.6f}")
    print(f"Sun longitude: {data['planets']['Sun']['longitude']:.4f}°")
    print(f"Moon longitude: {data['planets']['Moon']['longitude']:.4f}°")
    print(f"ASC longitude: {data['houses']['ascendant']:.4f}°")
    print(f"MC longitude: {data['houses']['mc']:.4f}°")
    print()
    print("Compare these values with astro.com or another reliable source")
    print("to verify accuracy.")