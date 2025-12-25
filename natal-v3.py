"""
Natal and Transit Chart Calculator using Swiss Ephemeris
Calculates planetary positions, houses, aspects for birth charts and transits

VERSION 3 - WITH TRANSIT SUPPORT
Features:
- Full natal chart calculation (verified against astro.com)
- Personalized transit charts showing transits to natal positions
- Transit-to-transit aspects
- Configurable orbs for natal vs transit aspects
- Transit planet positions in natal houses
- Retrograde tracking
- Date range transit search (find exact aspects)
"""

import swisseph as swe
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass, field
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
    TRADITIONAL = "traditional"
    MODERN = "modern"


@dataclass
class AspectDefinition:
    """Definition of an astrological aspect with variable orbs."""
    angle: float
    name: str
    symbol: str
    # Orbs for natal aspects: (luminary, personal, social, outer)
    natal_orbs: Tuple[float, float, float, float]
    # Orbs for transit aspects (typically tighter)
    transit_orbs: Tuple[float, float, float, float]
    major: bool = True


@dataclass
class TransitEvent:
    """Represents a transit aspect event."""
    transit_planet: str
    natal_planet: str
    aspect: str
    aspect_symbol: str
    exact_date: datetime
    orb: float
    applying: bool
    transit_retrograde: bool


class ChartConfig:
    """Shared configuration for chart calculations."""
    
    # Planet categories for variable orbs
    LUMINARIES = {'Sun', 'Moon'}
    PERSONAL_PLANETS = {'Mercury', 'Venus', 'Mars'}
    SOCIAL_PLANETS = {'Jupiter', 'Saturn'}
    OUTER_PLANETS = {'Uranus', 'Neptune', 'Pluto', 'Chiron', 'North Node', 'South Node', 'Lilith'}
    
    # Core planets (available with Moshier ephemeris)
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
    
    # Extended bodies (require SE files)
    PLANETS_EXTENDED = {
        'Chiron': swe.CHIRON,
    }
    
    # House systems
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
    }
    
    # Zodiac signs
    SIGNS = [
        {'name': 'Aries', 'symbol': '♈', 'ruler': 'Mars', 'element': 'Fire', 'modality': 'Cardinal'},
        {'name': 'Taurus', 'symbol': '♉', 'ruler': 'Venus', 'element': 'Earth', 'modality': 'Fixed'},
        {'name': 'Gemini', 'symbol': '♊', 'ruler': 'Mercury', 'element': 'Air', 'modality': 'Mutable'},
        {'name': 'Cancer', 'symbol': '♋', 'ruler': 'Moon', 'element': 'Water', 'modality': 'Cardinal'},
        {'name': 'Leo', 'symbol': '♌', 'ruler': 'Sun', 'element': 'Fire', 'modality': 'Fixed'},
        {'name': 'Virgo', 'symbol': '♍', 'ruler': 'Mercury', 'element': 'Earth', 'modality': 'Mutable'},
        {'name': 'Libra', 'symbol': '♎', 'ruler': 'Venus', 'element': 'Air', 'modality': 'Cardinal'},
        {'name': 'Scorpio', 'symbol': '♏', 'ruler': 'Mars', 'element': 'Water', 'modality': 'Fixed'},
        {'name': 'Sagittarius', 'symbol': '♐', 'ruler': 'Jupiter', 'element': 'Fire', 'modality': 'Mutable'},
        {'name': 'Capricorn', 'symbol': '♑', 'ruler': 'Saturn', 'element': 'Earth', 'modality': 'Cardinal'},
        {'name': 'Aquarius', 'symbol': '♒', 'ruler': 'Saturn', 'element': 'Air', 'modality': 'Fixed'},
        {'name': 'Pisces', 'symbol': '♓', 'ruler': 'Jupiter', 'element': 'Water', 'modality': 'Mutable'},
    ]
    
    # Essential dignities
    DIGNITIES = {
        'Sun': {'domicile': ['Leo'], 'exaltation': 'Aries', 'detriment': ['Aquarius'], 'fall': 'Libra'},
        'Moon': {'domicile': ['Cancer'], 'exaltation': 'Taurus', 'detriment': ['Capricorn'], 'fall': 'Scorpio'},
        'Mercury': {'domicile': ['Gemini', 'Virgo'], 'exaltation': 'Virgo', 'detriment': ['Sagittarius', 'Pisces'], 'fall': 'Pisces'},
        'Venus': {'domicile': ['Taurus', 'Libra'], 'exaltation': 'Pisces', 'detriment': ['Scorpio', 'Aries'], 'fall': 'Virgo'},
        'Mars': {'domicile': ['Aries', 'Scorpio'], 'exaltation': 'Capricorn', 'detriment': ['Libra', 'Taurus'], 'fall': 'Cancer'},
        'Jupiter': {'domicile': ['Sagittarius', 'Pisces'], 'exaltation': 'Cancer', 'detriment': ['Gemini', 'Virgo'], 'fall': 'Capricorn'},
        'Saturn': {'domicile': ['Capricorn', 'Aquarius'], 'exaltation': 'Libra', 'detriment': ['Cancer', 'Leo'], 'fall': 'Aries'},
    }
    
    # Aspect definitions with natal and transit orbs
    ASPECTS = [
        AspectDefinition(0, 'Conjunction', '☌', (10, 8, 7, 6), (8, 6, 5, 4), True),
        AspectDefinition(60, 'Sextile', '⚹', (6, 5, 4, 3), (4, 3, 2, 2), True),
        AspectDefinition(90, 'Square', '□', (8, 7, 6, 5), (6, 5, 4, 3), True),
        AspectDefinition(120, 'Trine', '△', (8, 7, 6, 5), (6, 5, 4, 3), True),
        AspectDefinition(180, 'Opposition', '☍', (10, 8, 7, 6), (8, 6, 5, 4), True),
        AspectDefinition(30, 'Semi-sextile', '⚺', (2, 2, 2, 1), (1, 1, 1, 1), False),
        AspectDefinition(45, 'Semi-square', '∠', (2, 2, 2, 1), (1, 1, 1, 1), False),
        AspectDefinition(135, 'Sesquiquadrate', '⚼', (2, 2, 2, 1), (1, 1, 1, 1), False),
        AspectDefinition(150, 'Quincunx', '⚻', (3, 3, 2, 2), (2, 2, 1, 1), False),
    ]


class NatalChart:
    """
    Calculate and store natal chart data.
    """
    
    def __init__(self,
                 birth_date: datetime,
                 latitude: float,
                 longitude: float,
                 house_system: str = 'Placidus',
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
            birth_date: Birth date/time (local if timezone provided, UTC otherwise)
            latitude: Birth latitude (-90 to 90, positive = North)
            longitude: Birth longitude (-180 to 180, positive = East)
            house_system: House system name
            timezone: Timezone string or pytz object
            ephemeris_path: Path to Swiss Ephemeris files (optional)
            node_type: TRUE or MEAN lunar nodes
            zodiac_type: TROPICAL or SIDEREAL
            sidereal_mode: Ayanamsa for sidereal calculations
            include_angles_in_aspects: Include ASC/MC in aspects
            include_minor_aspects: Include minor aspects
            pof_formula: Part of Fortune formula
        """
        # Validate inputs
        if not -90 <= latitude <= 90:
            raise ValueError(f"Latitude must be between -90 and 90")
        if not -180 <= longitude <= 180:
            raise ValueError(f"Longitude must be between -180 and 180")
        if house_system not in ChartConfig.HOUSE_SYSTEMS:
            raise ValueError(f"Unknown house system: {house_system}")
        
        self.birth_date_local = birth_date
        self.latitude = latitude
        self.longitude = longitude
        self.house_system = house_system
        self.house_system_code = ChartConfig.HOUSE_SYSTEMS[house_system]
        self.node_type = node_type
        self.zodiac_type = zodiac_type
        self.sidereal_mode = sidereal_mode
        self.include_angles_in_aspects = include_angles_in_aspects
        self.include_minor_aspects = include_minor_aspects
        self.pof_formula = pof_formula
        self._use_moshier = True
        
        # Initialize ephemeris
        self._init_ephemeris(ephemeris_path)
        
        # Timezone handling
        self.timezone = self._parse_timezone(timezone)
        self.birth_date_utc = self._convert_to_utc(birth_date, self.timezone)
        
        # Calculate Julian Day
        self.julian_day = self._calculate_julian_day(self.birth_date_utc)
        
        # Storage
        self.planets: Dict = {}
        self.houses: Dict = {}
        self.aspects: List = []
        self._is_day_chart: Optional[bool] = None
    
    def _init_ephemeris(self, ephemeris_path: Optional[str]) -> None:
        """Initialize Swiss Ephemeris."""
        import os
        self._use_moshier = True
        
        if ephemeris_path and os.path.isdir(ephemeris_path):
            try:
                files = os.listdir(ephemeris_path)
                if any(f.endswith('.se1') for f in files):
                    swe.set_ephe_path(ephemeris_path)
                    self._use_moshier = False
            except:
                pass
        
        if self.zodiac_type == ZodiacType.SIDEREAL:
            swe.set_sid_mode(self.sidereal_mode)
    
    def _parse_timezone(self, timezone):
        if timezone is None:
            return None
        if isinstance(timezone, str):
            try:
                return pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                raise ValueError(f"Unknown timezone: {timezone}")
        return timezone
    
    def _convert_to_utc(self, dt: datetime, tz) -> datetime:
        if dt.tzinfo is not None:
            return dt.astimezone(pytz.UTC)
        if tz is not None:
            try:
                local_dt = tz.localize(dt, is_dst=None)
            except pytz.exceptions.AmbiguousTimeError:
                local_dt = tz.localize(dt, is_dst=False)
            except pytz.exceptions.NonExistentTimeError:
                local_dt = tz.localize(dt, is_dst=True)
            return local_dt.astimezone(pytz.UTC)
        return dt.replace(tzinfo=pytz.UTC)
    
    def _calculate_julian_day(self, dt: datetime) -> float:
        hour_decimal = dt.hour + dt.minute / 60.0 + dt.second / 3600.0
        return swe.julday(dt.year, dt.month, dt.day, hour_decimal)
    
    def _get_calc_flags(self) -> int:
        flags = swe.FLG_MOSEPH if self._use_moshier else swe.FLG_SWIEPH
        flags |= swe.FLG_SPEED
        if self.zodiac_type == ZodiacType.SIDEREAL:
            flags |= swe.FLG_SIDEREAL
        return flags
    
    def _get_sign_info(self, longitude: float) -> Dict:
        longitude = longitude % 360
        sign_num = int(longitude / 30) % 12
        degree_in_sign = longitude % 30
        sign_data = ChartConfig.SIGNS[sign_num]
        deg_int = int(degree_in_sign)
        minutes = int((degree_in_sign - deg_int) * 60)
        
        return {
            'sign': sign_data['name'],
            'sign_symbol': sign_data['symbol'],
            'sign_num': sign_num,
            'degree': degree_in_sign,
            'degree_int': deg_int,
            'minutes': minutes,
            'element': sign_data['element'],
            'modality': sign_data['modality'],
            'ruler': sign_data['ruler'],
            'formatted': f"{deg_int}°{minutes:02d}' {sign_data['name']}",
            'formatted_short': f"{deg_int}°{minutes:02d}' {sign_data['symbol']}"
        }
    
    def _get_dignity(self, planet_name: str, sign: str) -> Optional[str]:
        if planet_name not in ChartConfig.DIGNITIES:
            return None
        dignity = ChartConfig.DIGNITIES[planet_name]
        if sign in dignity['domicile']:
            return 'domicile'
        elif sign == dignity['exaltation']:
            return 'exaltation'
        elif sign in dignity['detriment']:
            return 'detriment'
        elif sign == dignity['fall']:
            return 'fall'
        return None
    
    def _get_planet_category(self, planet_name: str) -> int:
        if planet_name in ChartConfig.LUMINARIES:
            return 0
        elif planet_name in ChartConfig.PERSONAL_PLANETS:
            return 1
        elif planet_name in ChartConfig.SOCIAL_PLANETS:
            return 2
        elif planet_name in ['Ascendant', 'MC']:
            return 0
        return 3
    
    def calculate_planets(self) -> Dict:
        """Calculate positions for all planets."""
        flags = self._get_calc_flags()
        
        for name, planet_id in ChartConfig.PLANETS_CORE.items():
            self._calculate_body(name, planet_id, flags)
        
        for name, planet_id in ChartConfig.PLANETS_EXTENDED.items():
            try:
                self._calculate_body(name, planet_id, flags)
            except:
                pass
        
        # Lunar nodes
        node_id = swe.TRUE_NODE if self.node_type == NodeType.TRUE else swe.MEAN_NODE
        self._calculate_body('North Node', node_id, flags)
        
        nn = self.planets['North Node']
        sn_long = (nn['longitude'] + 180) % 360
        sign_info = self._get_sign_info(sn_long)
        self.planets['South Node'] = {
            'longitude': sn_long,
            'latitude': 0,
            'distance': nn['distance'],
            'speed': nn['speed'],
            'retrograde': nn['retrograde'],
            **sign_info,
            'dignity': None,
        }
        
        # Lilith
        try:
            self._calculate_body('Lilith', swe.MEAN_APOG, flags)
        except:
            pass
        
        return self.planets
    
    def _calculate_body(self, name: str, body_id: int, flags: int) -> None:
        result, _ = swe.calc_ut(self.julian_day, body_id, flags)
        sign_info = self._get_sign_info(result[0])
        self.planets[name] = {
            'longitude': result[0],
            'latitude': result[1],
            'distance': result[2],
            'speed': result[3],
            'retrograde': result[3] < 0,
            **sign_info,
            'dignity': self._get_dignity(name, sign_info['sign']),
        }
    
    def calculate_houses(self) -> Dict:
        """Calculate house cusps and angles."""
        cusps_raw, ascmc = swe.houses_ex(
            self.julian_day, self.latitude, self.longitude, self.house_system_code
        )
        
        cusps = list(cusps_raw)
        
        self.houses = {
            'cusps': cusps,
            'ascendant': ascmc[0],
            'mc': ascmc[1],
            'armc': ascmc[2],
            'vertex': ascmc[3],
            'ic': (ascmc[1] + 180) % 360,
            'descendant': (ascmc[0] + 180) % 360,
        }
        
        for angle in ['ascendant', 'mc', 'ic', 'descendant', 'vertex']:
            sign_info = self._get_sign_info(self.houses[angle])
            self.houses[f'{angle}_sign'] = sign_info['sign']
            self.houses[f'{angle}_degree'] = sign_info['degree']
            self.houses[f'{angle}_formatted'] = sign_info['formatted']
        
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
        if self._is_day_chart is not None:
            return self._is_day_chart
        sun_house = self.get_planet_in_house('Sun')
        self._is_day_chart = sun_house >= 7
        return self._is_day_chart
    
    def calculate_part_of_fortune(self) -> Dict:
        """Calculate Part of Fortune."""
        if not self.planets:
            self.calculate_planets()
        if not self.houses:
            self.calculate_houses()
        
        asc = self.houses['ascendant']
        sun = self.planets['Sun']['longitude']
        moon = self.planets['Moon']['longitude']
        
        use_day = self.pof_formula == PartOfFortuneFormula.MODERN or self._is_day_chart_calc()
        
        if use_day:
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
        }
        return self.planets['Part of Fortune']
    
    def get_planet_in_house(self, planet_name: str) -> int:
        """Determine which house a planet is in."""
        if planet_name not in self.planets:
            raise ValueError(f"Planet '{planet_name}' not found")
        
        planet_long = self.planets[planet_name]['longitude'] % 360
        cusps = self.houses['cusps']
        
        for i in range(12):
            cusp_start = cusps[i] % 360
            cusp_end = cusps[(i + 1) % 12] % 360
            
            if cusp_start < cusp_end:
                if cusp_start <= planet_long < cusp_end:
                    return i + 1
            else:
                if planet_long >= cusp_start or planet_long < cusp_end:
                    return i + 1
        
        return 1
    
    def _get_aspect_orb(self, aspect: AspectDefinition, planet1: str, planet2: str, 
                        is_transit: bool = False) -> float:
        cat1 = self._get_planet_category(planet1)
        cat2 = self._get_planet_category(planet2)
        orbs = aspect.transit_orbs if is_transit else aspect.natal_orbs
        return min(orbs[cat1], orbs[cat2])
    
    def _calculate_applying(self, pos1: float, pos2: float,
                           speed1: float, speed2: float,
                           aspect_angle: float) -> bool:
        """Determine if aspect is applying or separating."""
        if speed1 == 0 and speed2 == 0:
            return False
        
        diff = (pos2 - pos1) % 360
        if diff > 180:
            diff -= 360
        
        current_sep = abs(diff)
        relative_speed = speed2 - speed1
        
        if aspect_angle == 0:
            if diff > 0:
                return relative_speed < 0
            else:
                return relative_speed > 0
        elif aspect_angle == 180:
            if current_sep < 180:
                return relative_speed > 0 if diff > 0 else relative_speed < 0
            return False
        else:
            if current_sep < aspect_angle:
                return relative_speed > 0 if diff > 0 else relative_speed < 0
            else:
                return relative_speed < 0 if diff > 0 else relative_speed > 0
    
    def calculate_aspects(self, orb_factor: float = 1.0) -> List[Dict]:
        """Calculate aspects between natal planets."""
        if not self.planets:
            self.calculate_planets()
        
        self.aspects = []
        points = {name: {'longitude': data['longitude'], 'speed': data.get('speed', 0)}
                  for name, data in self.planets.items()}
        
        if self.include_angles_in_aspects and self.houses:
            points['Ascendant'] = {'longitude': self.houses['ascendant'], 'speed': 0}
            points['MC'] = {'longitude': self.houses['mc'], 'speed': 0}
        
        point_names = list(points.keys())
        
        for i, name1 in enumerate(point_names):
            for name2 in point_names[i + 1:]:
                pos1, pos2 = points[name1]['longitude'], points[name2]['longitude']
                speed1, speed2 = points[name1]['speed'], points[name2]['speed']
                
                separation = abs(pos1 - pos2)
                if separation > 180:
                    separation = 360 - separation
                
                for aspect_def in ChartConfig.ASPECTS:
                    if not aspect_def.major and not self.include_minor_aspects:
                        continue
                    
                    orb = abs(separation - aspect_def.angle)
                    max_orb = self._get_aspect_orb(aspect_def, name1, name2) * orb_factor
                    
                    if orb <= max_orb:
                        self.aspects.append({
                            'planet1': name1,
                            'planet2': name2,
                            'aspect': aspect_def.name,
                            'symbol': aspect_def.symbol,
                            'angle': aspect_def.angle,
                            'orb': round(orb, 4),
                            'max_orb': max_orb,
                            'applying': self._calculate_applying(pos1, pos2, speed1, speed2, aspect_def.angle),
                            'major': aspect_def.major,
                        })
        
        self.aspects.sort(key=lambda x: x['orb'])
        return self.aspects
    
    def generate_full_chart(self) -> Dict:
        """Calculate complete natal chart."""
        self.calculate_planets()
        self.calculate_houses()
        self.calculate_part_of_fortune()
        self.calculate_aspects()
        
        for planet_name in self.planets:
            self.planets[planet_name]['house'] = self.get_planet_in_house(planet_name)
        
        return {
            'metadata': {
                'birth_date_local': self.birth_date_local.isoformat(),
                'birth_date_utc': self.birth_date_utc.isoformat(),
                'timezone': str(self.timezone) if self.timezone else 'UTC',
                'latitude': self.latitude,
                'longitude': self.longitude,
                'house_system': self.house_system,
                'zodiac_type': self.zodiac_type.value,
                'node_type': self.node_type.value,
                'julian_day': self.julian_day,
                'is_day_chart': self._is_day_chart_calc(),
            },
            'planets': self.planets,
            'houses': self.houses,
            'aspects': self.aspects,
        }
    
    def format_chart_text(self) -> str:
        """Generate human-readable chart summary."""
        if not self.planets or not self.houses:
            self.generate_full_chart()
        
        lines = []
        lines.append("=" * 75)
        lines.append("NATAL CHART")
        lines.append("=" * 75)
        
        if self.timezone:
            lines.append(f"Birth (Local):  {self.birth_date_local.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Birth (UTC):    {self.birth_date_utc.strftime('%Y-%m-%d %H:%M:%S')}")
            lines.append(f"Timezone:       {self.timezone}")
        else:
            lines.append(f"Birth (UTC):    {self.birth_date_utc.strftime('%Y-%m-%d %H:%M:%S')}")
        
        lines.append(f"Location:       {abs(self.latitude):.4f}°{'N' if self.latitude >= 0 else 'S'}, "
                    f"{abs(self.longitude):.4f}°{'E' if self.longitude >= 0 else 'W'}")
        lines.append(f"House System:   {self.house_system}")
        lines.append("")
        
        lines.append("PLANETARY POSITIONS")
        lines.append("-" * 75)
        lines.append(f"{'Planet':<14} {'Position':<18} {'House':<7} {'Motion':<12} {'Dignity'}")
        lines.append("-" * 75)
        
        planet_order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
                       'Uranus', 'Neptune', 'Pluto', 'North Node', 'South Node',
                       'Chiron', 'Lilith', 'Part of Fortune']
        
        for name in planet_order:
            if name not in self.planets:
                continue
            p = self.planets[name]
            motion = "R" if p['retrograde'] else "D" if p['speed'] != 0 else ""
            if p['speed'] != 0:
                motion += f" {abs(p['speed']):.2f}°/d"
            dignity = p.get('dignity') or ''
            lines.append(f"{name:<14} {p['formatted']:<18} {p.get('house', '?'):<7} {motion:<12} {dignity}")
        
        lines.append("")
        lines.append("ANGLES")
        lines.append("-" * 75)
        for angle, abbr in [('ascendant', 'ASC'), ('mc', 'MC'), ('descendant', 'DSC'), ('ic', 'IC')]:
            lines.append(f"{abbr:<14} {self.houses[f'{angle}_formatted']}")
        
        return "\n".join(lines)


class TransitChart:
    """
    Calculate transits to a natal chart.
    """
    
    def __init__(self, natal_chart: NatalChart):
        """
        Initialize transit calculator.
        
        Args:
            natal_chart: The natal chart to calculate transits against
        """
        self.natal = natal_chart
        
        # Ensure natal chart is calculated
        if not self.natal.planets:
            self.natal.generate_full_chart()
        
        # Transit data storage
        self.transit_date: Optional[datetime] = None
        self.transit_date_utc: Optional[datetime] = None
        self.transit_julian_day: Optional[float] = None
        self.transit_planets: Dict = {}
        self.transit_to_natal_aspects: List = []
        self.transit_to_transit_aspects: List = []
    
    def calculate_transits(self, 
                          transit_date: datetime,
                          timezone: Optional[Union[str, pytz.tzinfo.BaseTzInfo]] = None,
                          include_minor_aspects: bool = False,
                          include_transit_to_transit: bool = False,
                          orb_factor: float = 1.0) -> Dict:
        """
        Calculate transit positions and aspects to natal chart.
        
        Args:
            transit_date: Date/time to calculate transits for
            timezone: Timezone of transit_date (or None for UTC)
            include_minor_aspects: Include minor aspects
            include_transit_to_transit: Also calculate transit-to-transit aspects
            orb_factor: Multiplier for aspect orbs
            
        Returns:
            Dictionary with transit data
        """
        self.transit_date = transit_date
        
        # Convert to UTC
        tz = self.natal._parse_timezone(timezone)
        self.transit_date_utc = self.natal._convert_to_utc(transit_date, tz)
        self.transit_julian_day = self.natal._calculate_julian_day(self.transit_date_utc)
        
        # Calculate transit planet positions
        self._calculate_transit_planets()
        
        # Calculate aspects to natal
        self._calculate_transit_to_natal_aspects(include_minor_aspects, orb_factor)
        
        # Optionally calculate transit-to-transit aspects
        if include_transit_to_transit:
            self._calculate_transit_to_transit_aspects(include_minor_aspects, orb_factor)
        
        return {
            'transit_date': transit_date.isoformat(),
            'transit_date_utc': self.transit_date_utc.isoformat(),
            'transit_planets': self.transit_planets,
            'transit_to_natal': self.transit_to_natal_aspects,
            'transit_to_transit': self.transit_to_transit_aspects if include_transit_to_transit else [],
        }
    
    def _calculate_transit_planets(self) -> None:
        """Calculate positions of transiting planets."""
        flags = self.natal._get_calc_flags()
        
        self.transit_planets = {}
        
        for name, planet_id in ChartConfig.PLANETS_CORE.items():
            self._calculate_transit_body(name, planet_id, flags)
        
        for name, planet_id in ChartConfig.PLANETS_EXTENDED.items():
            try:
                self._calculate_transit_body(name, planet_id, flags)
            except:
                pass
        
        # Lunar nodes
        node_id = swe.TRUE_NODE if self.natal.node_type == NodeType.TRUE else swe.MEAN_NODE
        self._calculate_transit_body('North Node', node_id, flags)
        
        nn = self.transit_planets['North Node']
        sn_long = (nn['longitude'] + 180) % 360
        sign_info = self.natal._get_sign_info(sn_long)
        self.transit_planets['South Node'] = {
            'longitude': sn_long,
            'speed': nn['speed'],
            'retrograde': nn['retrograde'],
            **sign_info,
        }
        
        # Lilith
        try:
            self._calculate_transit_body('Lilith', swe.MEAN_APOG, flags)
        except:
            pass
        
        # Add natal house positions for each transit planet
        for name in self.transit_planets:
            self.transit_planets[name]['natal_house'] = self._get_transit_in_natal_house(name)
    
    def _calculate_transit_body(self, name: str, body_id: int, flags: int) -> None:
        """Calculate position for a single transiting body."""
        result, _ = swe.calc_ut(self.transit_julian_day, body_id, flags)
        sign_info = self.natal._get_sign_info(result[0])
        
        self.transit_planets[name] = {
            'longitude': result[0],
            'speed': result[3],
            'retrograde': result[3] < 0,
            **sign_info,
        }
    
    def _get_transit_in_natal_house(self, planet_name: str) -> int:
        """Determine which natal house a transit planet is in."""
        planet_long = self.transit_planets[planet_name]['longitude'] % 360
        cusps = self.natal.houses['cusps']
        
        for i in range(12):
            cusp_start = cusps[i] % 360
            cusp_end = cusps[(i + 1) % 12] % 360
            
            if cusp_start < cusp_end:
                if cusp_start <= planet_long < cusp_end:
                    return i + 1
            else:
                if planet_long >= cusp_start or planet_long < cusp_end:
                    return i + 1
        return 1
    
    def _calculate_transit_to_natal_aspects(self, include_minor: bool, orb_factor: float) -> None:
        """Calculate aspects between transit planets and natal planets."""
        self.transit_to_natal_aspects = []
        
        # Transit planets to check (skip Part of Fortune for transits)
        transit_bodies = [name for name in self.transit_planets.keys() 
                         if name != 'Part of Fortune']
        
        # Natal points to check
        natal_points = {}
        for name, data in self.natal.planets.items():
            natal_points[name] = data['longitude']
        
        # Add natal angles
        natal_points['Natal ASC'] = self.natal.houses['ascendant']
        natal_points['Natal MC'] = self.natal.houses['mc']
        
        for transit_name in transit_bodies:
            transit_pos = self.transit_planets[transit_name]['longitude']
            transit_speed = self.transit_planets[transit_name]['speed']
            
            for natal_name, natal_pos in natal_points.items():
                separation = abs(transit_pos - natal_pos)
                if separation > 180:
                    separation = 360 - separation
                
                for aspect_def in ChartConfig.ASPECTS:
                    if not aspect_def.major and not include_minor:
                        continue
                    
                    orb = abs(separation - aspect_def.angle)
                    
                    # Use transit orbs (tighter)
                    cat1 = self.natal._get_planet_category(transit_name)
                    cat2 = self.natal._get_planet_category(natal_name.replace('Natal ', ''))
                    max_orb = min(aspect_def.transit_orbs[cat1], aspect_def.transit_orbs[cat2]) * orb_factor
                    
                    if orb <= max_orb:
                        applying = self.natal._calculate_applying(
                            transit_pos, natal_pos, transit_speed, 0, aspect_def.angle
                        )
                        
                        self.transit_to_natal_aspects.append({
                            'transit_planet': transit_name,
                            'natal_planet': natal_name,
                            'aspect': aspect_def.name,
                            'symbol': aspect_def.symbol,
                            'angle': aspect_def.angle,
                            'orb': round(orb, 4),
                            'max_orb': max_orb,
                            'applying': applying,
                            'major': aspect_def.major,
                            'transit_retrograde': self.transit_planets[transit_name]['retrograde'],
                            'transit_house': self.transit_planets[transit_name]['natal_house'],
                        })
        
        # Sort by orb
        self.transit_to_natal_aspects.sort(key=lambda x: x['orb'])
    
    def _calculate_transit_to_transit_aspects(self, include_minor: bool, orb_factor: float) -> None:
        """Calculate aspects between transiting planets."""
        self.transit_to_transit_aspects = []
        
        transit_bodies = [name for name in self.transit_planets.keys() 
                         if name not in ['Part of Fortune', 'South Node']]
        
        for i, name1 in enumerate(transit_bodies):
            for name2 in transit_bodies[i + 1:]:
                pos1 = self.transit_planets[name1]['longitude']
                pos2 = self.transit_planets[name2]['longitude']
                speed1 = self.transit_planets[name1]['speed']
                speed2 = self.transit_planets[name2]['speed']
                
                separation = abs(pos1 - pos2)
                if separation > 180:
                    separation = 360 - separation
                
                for aspect_def in ChartConfig.ASPECTS:
                    if not aspect_def.major and not include_minor:
                        continue
                    
                    orb = abs(separation - aspect_def.angle)
                    cat1 = self.natal._get_planet_category(name1)
                    cat2 = self.natal._get_planet_category(name2)
                    max_orb = min(aspect_def.transit_orbs[cat1], aspect_def.transit_orbs[cat2]) * orb_factor
                    
                    if orb <= max_orb:
                        self.transit_to_transit_aspects.append({
                            'planet1': name1,
                            'planet2': name2,
                            'aspect': aspect_def.name,
                            'symbol': aspect_def.symbol,
                            'angle': aspect_def.angle,
                            'orb': round(orb, 4),
                            'applying': self.natal._calculate_applying(pos1, pos2, speed1, speed2, aspect_def.angle),
                            'major': aspect_def.major,
                        })
        
        self.transit_to_transit_aspects.sort(key=lambda x: x['orb'])
    
    def find_exact_transits(self,
                           start_date: datetime,
                           end_date: datetime,
                           timezone: Optional[str] = None,
                           planets: Optional[List[str]] = None,
                           aspects: Optional[List[str]] = None,
                           natal_points: Optional[List[str]] = None) -> List[TransitEvent]:
        """
        Find dates when transits become exact within a date range.
        
        Args:
            start_date: Start of search range
            end_date: End of search range
            timezone: Timezone for dates
            planets: Transit planets to include (None = all)
            aspects: Aspect types to include (None = major only)
            natal_points: Natal points to check (None = all planets + angles)
            
        Returns:
            List of TransitEvent objects with exact dates
        """
        events = []
        
        # Default to major aspects
        if aspects is None:
            aspects = ['Conjunction', 'Sextile', 'Square', 'Trine', 'Opposition']
        
        # Default planets
        if planets is None:
            planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 
                      'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
        
        # Default natal points
        if natal_points is None:
            natal_points = list(self.natal.planets.keys()) + ['Natal ASC', 'Natal MC']
        
        # Get natal positions
        natal_positions = {}
        for name in natal_points:
            if name == 'Natal ASC':
                natal_positions[name] = self.natal.houses['ascendant']
            elif name == 'Natal MC':
                natal_positions[name] = self.natal.houses['mc']
            elif name in self.natal.planets:
                natal_positions[name] = self.natal.planets[name]['longitude']
        
        # Search with appropriate step size based on fastest planet
        # Moon moves ~13°/day, so use 6-hour steps for Moon, 1-day for others
        has_moon = 'Moon' in planets
        step_hours = 6 if has_moon else 24
        
        current = start_date
        tz = self.natal._parse_timezone(timezone)
        
        prev_separations = {}  # Track previous separations to detect crossings
        
        while current <= end_date:
            self.calculate_transits(current, timezone)
            
            for transit_name in planets:
                if transit_name not in self.transit_planets:
                    continue
                
                transit_pos = self.transit_planets[transit_name]['longitude']
                transit_speed = self.transit_planets[transit_name]['speed']
                transit_retro = self.transit_planets[transit_name]['retrograde']
                
                for natal_name, natal_pos in natal_positions.items():
                    for aspect_def in ChartConfig.ASPECTS:
                        if aspect_def.name not in aspects:
                            continue
                        
                        # Calculate current separation from exact aspect
                        separation = abs(transit_pos - natal_pos)
                        if separation > 180:
                            separation = 360 - separation
                        
                        diff_from_exact = separation - aspect_def.angle
                        
                        key = (transit_name, natal_name, aspect_def.name)
                        
                        if key in prev_separations:
                            prev_diff = prev_separations[key]
                            
                            # Check if we crossed exact (sign change in diff)
                            if prev_diff * diff_from_exact < 0 and abs(diff_from_exact) < 2:
                                # Linear interpolation to find approximate exact time
                                fraction = abs(prev_diff) / (abs(prev_diff) + abs(diff_from_exact))
                                exact_time = current - timedelta(hours=step_hours) + timedelta(hours=step_hours * fraction)
                                
                                events.append(TransitEvent(
                                    transit_planet=transit_name,
                                    natal_planet=natal_name,
                                    aspect=aspect_def.name,
                                    aspect_symbol=aspect_def.symbol,
                                    exact_date=exact_time,
                                    orb=0.0,
                                    applying=False,  # At exact, neither
                                    transit_retrograde=transit_retro,
                                ))
                        
                        prev_separations[key] = diff_from_exact
            
            current += timedelta(hours=step_hours)
        
        # Sort by date
        events.sort(key=lambda x: x.exact_date)
        
        return events
    
    def format_transit_text(self) -> str:
        """Generate human-readable transit summary."""
        if not self.transit_planets:
            return "No transits calculated. Call calculate_transits() first."
        
        lines = []
        lines.append("=" * 75)
        lines.append("TRANSIT CHART")
        lines.append("=" * 75)
        lines.append(f"Transit Date:   {self.transit_date_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        lines.append(f"For natal chart of: {self.natal.birth_date_local.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        # Transit positions
        lines.append("TRANSITING PLANETS")
        lines.append("-" * 75)
        lines.append(f"{'Planet':<14} {'Position':<18} {'In Natal H':<12} {'Motion'}")
        lines.append("-" * 75)
        
        planet_order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
                       'Uranus', 'Neptune', 'Pluto', 'North Node', 'Chiron']
        
        for name in planet_order:
            if name not in self.transit_planets:
                continue
            p = self.transit_planets[name]
            motion = "R" if p['retrograde'] else "D"
            motion += f" {abs(p['speed']):.2f}°/d"
            lines.append(f"{name:<14} {p['formatted']:<18} House {p['natal_house']:<5} {motion}")
        
        lines.append("")
        
        # Transit to natal aspects
        lines.append("TRANSITS TO NATAL CHART")
        lines.append("-" * 75)
        
        if self.transit_to_natal_aspects:
            for asp in self.transit_to_natal_aspects[:20]:  # Top 20
                status = "applying" if asp['applying'] else "separating"
                retro = " (R)" if asp['transit_retrograde'] else ""
                lines.append(f"  T.{asp['transit_planet']:<10}{retro} {asp['symbol']} "
                           f"N.{asp['natal_planet']:<14} orb {asp['orb']:5.2f}° ({status})")
        else:
            lines.append("  No transit aspects within orb")
        
        if self.transit_to_transit_aspects:
            lines.append("")
            lines.append("TRANSIT-TO-TRANSIT ASPECTS")
            lines.append("-" * 75)
            for asp in self.transit_to_transit_aspects[:10]:
                status = "applying" if asp['applying'] else "separating"
                lines.append(f"  {asp['planet1']:<12} {asp['symbol']} {asp['planet2']:<12} "
                           f"orb {asp['orb']:5.2f}° ({status})")
        
        return "\n".join(lines)


# Convenience functions
def calculate_natal_chart(birth_datetime: datetime,
                         latitude: float,
                         longitude: float,
                         house_system: str = 'Placidus',
                         timezone: Optional[str] = None,
                         **kwargs) -> Dict:
    """Calculate a complete natal chart."""
    chart = NatalChart(birth_datetime, latitude, longitude, house_system,
                       timezone=timezone, **kwargs)
    return chart.generate_full_chart()


def calculate_transits(natal_chart: NatalChart,
                      transit_date: datetime,
                      timezone: Optional[str] = None,
                      **kwargs) -> Dict:
    """Calculate transits for a natal chart."""
    transits = TransitChart(natal_chart)
    return transits.calculate_transits(transit_date, timezone, **kwargs)


# Example usage
if __name__ == "__main__":
    print("=" * 75)
    print("NATAL AND TRANSIT CHART CALCULATOR")
    print("=" * 75)
    print()
    
    # Create natal chart
    birth = datetime(1980, 10, 24, 11, 34, 0)

    natal = NatalChart(
        birth_date=birth,
        latitude=50.0755,
        longitude=14.4378,
        timezone='Europe/Prague',
        house_system='Placidus',
    )
    natal.generate_full_chart()
    
    print(natal.format_chart_text())
    print()
    
    # Calculate current transits
    transit_calc = TransitChart(natal)
    now = datetime.now()
    
    transit_calc.calculate_transits(
        transit_date=now,
        timezone='America/New_York',
        include_minor_aspects=False,
        include_transit_to_transit=True,
    )
    
    print(transit_calc.format_transit_text())
    print()
    
    # Find exact transits for the next 30 days
    print("=" * 75)
    print("UPCOMING EXACT TRANSITS (Next 30 days)")
    print("=" * 75)
    
    events = transit_calc.find_exact_transits(
        start_date=now,
        end_date=now + timedelta(days=30),
        timezone='America/New_York',
        planets=['Sun', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn'],
        aspects=['Conjunction', 'Square', 'Trine', 'Opposition'],
    )
    
    for event in events[:15]:
        retro = " (R)" if event.transit_retrograde else ""
        print(f"  {event.exact_date.strftime('%Y-%m-%d %H:%M')}  "
              f"T.{event.transit_planet}{retro} {event.aspect_symbol} N.{event.natal_planet}")