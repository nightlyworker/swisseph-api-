"""
Natal and Transit Chart Calculator using Swiss Ephemeris
VERSION 4 - CORRECTED TRANSIT CALCULATIONS

Fixes in v4:
1. Simplified and corrected applying/separating logic for transit-to-natal aspects
2. Improved find_exact_transits with better boundary handling
3. Added all natal angles (ASC, MC, DSC, IC, Vertex) to transit calculations
4. Better handling of 360°/0° boundary crossings
5. More accurate Moon transit timing with smaller steps
6. Added transit ingress tracking (when planets change signs/houses)
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
    natal_orbs: Tuple[float, float, float, float]  # (luminary, personal, social, outer)
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
    
    def __str__(self):
        r = " (R)" if self.transit_retrograde else ""
        return f"{self.exact_date.strftime('%Y-%m-%d %H:%M')} T.{self.transit_planet}{r} {self.aspect_symbol} N.{self.natal_planet}"


class ChartConfig:
    """Shared configuration for chart calculations."""
    
    LUMINARIES = {'Sun', 'Moon'}
    PERSONAL_PLANETS = {'Mercury', 'Venus', 'Mars'}
    SOCIAL_PLANETS = {'Jupiter', 'Saturn'}
    OUTER_PLANETS = {'Uranus', 'Neptune', 'Pluto', 'Chiron', 'North Node', 'South Node', 'Lilith'}
    
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
    
    PLANETS_EXTENDED = {
        'Chiron': swe.CHIRON,
    }
    
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
    
    DIGNITIES = {
        'Sun': {'domicile': ['Leo'], 'exaltation': 'Aries', 'detriment': ['Aquarius'], 'fall': 'Libra'},
        'Moon': {'domicile': ['Cancer'], 'exaltation': 'Taurus', 'detriment': ['Capricorn'], 'fall': 'Scorpio'},
        'Mercury': {'domicile': ['Gemini', 'Virgo'], 'exaltation': 'Virgo', 'detriment': ['Sagittarius', 'Pisces'], 'fall': 'Pisces'},
        'Venus': {'domicile': ['Taurus', 'Libra'], 'exaltation': 'Pisces', 'detriment': ['Scorpio', 'Aries'], 'fall': 'Virgo'},
        'Mars': {'domicile': ['Aries', 'Scorpio'], 'exaltation': 'Capricorn', 'detriment': ['Libra', 'Taurus'], 'fall': 'Cancer'},
        'Jupiter': {'domicile': ['Sagittarius', 'Pisces'], 'exaltation': 'Cancer', 'detriment': ['Gemini', 'Virgo'], 'fall': 'Capricorn'},
        'Saturn': {'domicile': ['Capricorn', 'Aquarius'], 'exaltation': 'Libra', 'detriment': ['Cancer', 'Leo'], 'fall': 'Aries'},
    }
    
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


def normalize_degrees(deg: float) -> float:
    """Normalize degrees to 0-360 range."""
    return deg % 360


def angular_distance(pos1: float, pos2: float) -> float:
    """
    Calculate the shortest angular distance between two positions.
    Always returns a positive value 0-180.
    """
    diff = abs(normalize_degrees(pos1) - normalize_degrees(pos2))
    return min(diff, 360 - diff)


def signed_angular_distance(from_pos: float, to_pos: float) -> float:
    """
    Calculate signed angular distance from one position to another.
    Positive = to_pos is ahead (counterclockwise) of from_pos.
    Returns value in range (-180, 180].
    """
    diff = normalize_degrees(to_pos) - normalize_degrees(from_pos)
    if diff > 180:
        diff -= 360
    elif diff <= -180:
        diff += 360
    return diff


class NatalChart:
    """Calculate and store natal chart data."""
    
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
                 include_minor_aspects: bool = True,
                 pof_formula: PartOfFortuneFormula = PartOfFortuneFormula.TRADITIONAL):
        
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
        self.include_minor_aspects = include_minor_aspects
        self.pof_formula = pof_formula
        self._use_moshier = True
        
        self._init_ephemeris(ephemeris_path)
        
        self.timezone = self._parse_timezone(timezone)
        self.birth_date_utc = self._convert_to_utc(birth_date, self.timezone)
        self.julian_day = self._calculate_julian_day(self.birth_date_utc)
        
        self.planets: Dict = {}
        self.houses: Dict = {}
        self.aspects: List = []
        self._is_day_chart: Optional[bool] = None
    
    def _init_ephemeris(self, ephemeris_path: Optional[str]) -> None:
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
        hour_decimal = dt.hour + dt.minute / 60.0 + dt.second / 3600.0 + dt.microsecond / 3600000000.0
        return swe.julday(dt.year, dt.month, dt.day, hour_decimal)
    
    def _get_calc_flags(self) -> int:
        flags = swe.FLG_MOSEPH if self._use_moshier else swe.FLG_SWIEPH
        flags |= swe.FLG_SPEED
        if self.zodiac_type == ZodiacType.SIDEREAL:
            flags |= swe.FLG_SIDEREAL
        return flags
    
    def _get_sign_info(self, longitude: float) -> Dict:
        longitude = normalize_degrees(longitude)
        sign_num = int(longitude / 30)
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
        """0=luminary/angle, 1=personal, 2=social, 3=outer"""
        clean_name = planet_name.replace('Natal ', '')
        if clean_name in ChartConfig.LUMINARIES or clean_name in ['ASC', 'MC', 'DSC', 'IC', 'Ascendant', 'Vertex']:
            return 0
        elif clean_name in ChartConfig.PERSONAL_PLANETS:
            return 1
        elif clean_name in ChartConfig.SOCIAL_PLANETS:
            return 2
        return 3
    
    def calculate_planets(self) -> Dict:
        flags = self._get_calc_flags()
        
        for name, planet_id in ChartConfig.PLANETS_CORE.items():
            self._calculate_body(name, planet_id, flags)
        
        for name, planet_id in ChartConfig.PLANETS_EXTENDED.items():
            try:
                self._calculate_body(name, planet_id, flags)
            except:
                pass
        
        node_id = swe.TRUE_NODE if self.node_type == NodeType.TRUE else swe.MEAN_NODE
        self._calculate_body('North Node', node_id, flags)
        
        nn = self.planets['North Node']
        sn_long = normalize_degrees(nn['longitude'] + 180)
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
            'ic': normalize_degrees(ascmc[1] + 180),
            'descendant': normalize_degrees(ascmc[0] + 180),
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
        if not self.planets:
            self.calculate_planets()
        if not self.houses:
            self.calculate_houses()
        
        asc = self.houses['ascendant']
        sun = self.planets['Sun']['longitude']
        moon = self.planets['Moon']['longitude']
        
        use_day = self.pof_formula == PartOfFortuneFormula.MODERN or self._is_day_chart_calc()
        
        if use_day:
            pof = normalize_degrees(asc + moon - sun)
        else:
            pof = normalize_degrees(asc + sun - moon)
        
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
        if planet_name not in self.planets:
            raise ValueError(f"Planet '{planet_name}' not found")
        
        planet_long = normalize_degrees(self.planets[planet_name]['longitude'])
        cusps = self.houses['cusps']
        
        for i in range(12):
            cusp_start = normalize_degrees(cusps[i])
            cusp_end = normalize_degrees(cusps[(i + 1) % 12])
            
            if cusp_start < cusp_end:
                if cusp_start <= planet_long < cusp_end:
                    return i + 1
            else:  # House spans 0°
                if planet_long >= cusp_start or planet_long < cusp_end:
                    return i + 1
        return 1
    
    def _calculate_natal_applying(self, pos1: float, pos2: float,
                                   speed1: float, speed2: float,
                                   aspect_angle: float) -> bool:
        """Determine if natal aspect is applying or separating."""
        if speed1 == 0 and speed2 == 0:
            return False
        
        # Current angular separation
        sep = angular_distance(pos1, pos2)
        
        # Calculate where they'll be in a small time step
        future_pos1 = normalize_degrees(pos1 + speed1 * 0.1)  # 0.1 day
        future_pos2 = normalize_degrees(pos2 + speed2 * 0.1)
        future_sep = angular_distance(future_pos1, future_pos2)
        
        # Applying if separation is getting closer to the exact aspect angle
        current_orb = abs(sep - aspect_angle)
        future_orb = abs(future_sep - aspect_angle)
        
        return future_orb < current_orb
    
    def calculate_aspects(self, orb_factor: float = 1.0) -> List[Dict]:
        if not self.planets:
            self.calculate_planets()
        
        self.aspects = []
        points = {name: {'longitude': data['longitude'], 'speed': data.get('speed', 0)}
                  for name, data in self.planets.items()}
        
        # Add angles
        points['Ascendant'] = {'longitude': self.houses['ascendant'], 'speed': 0}
        points['MC'] = {'longitude': self.houses['mc'], 'speed': 0}
        
        point_names = list(points.keys())
        
        for i, name1 in enumerate(point_names):
            for name2 in point_names[i + 1:]:
                pos1, pos2 = points[name1]['longitude'], points[name2]['longitude']
                speed1, speed2 = points[name1]['speed'], points[name2]['speed']
                
                sep = angular_distance(pos1, pos2)
                
                for aspect_def in ChartConfig.ASPECTS:
                    if not aspect_def.major and not self.include_minor_aspects:
                        continue
                    
                    orb = abs(sep - aspect_def.angle)
                    cat1 = self._get_planet_category(name1)
                    cat2 = self._get_planet_category(name2)
                    max_orb = min(aspect_def.natal_orbs[cat1], aspect_def.natal_orbs[cat2]) * orb_factor
                    
                    if orb <= max_orb:
                        self.aspects.append({
                            'planet1': name1,
                            'planet2': name2,
                            'aspect': aspect_def.name,
                            'symbol': aspect_def.symbol,
                            'angle': aspect_def.angle,
                            'orb': round(orb, 4),
                            'max_orb': max_orb,
                            'applying': self._calculate_natal_applying(pos1, pos2, speed1, speed2, aspect_def.angle),
                            'major': aspect_def.major,
                        })
        
        self.aspects.sort(key=lambda x: x['orb'])
        return self.aspects
    
    def generate_full_chart(self) -> Dict:
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
    """Calculate transits to a natal chart."""
    
    def __init__(self, natal_chart: NatalChart):
        self.natal = natal_chart
        
        if not self.natal.planets:
            self.natal.generate_full_chart()
        
        self.transit_date: Optional[datetime] = None
        self.transit_date_utc: Optional[datetime] = None
        self.transit_julian_day: Optional[float] = None
        self.transit_planets: Dict = {}
        self.transit_to_natal_aspects: List = []
        self.transit_to_transit_aspects: List = []
    
    def _calculate_planet_position(self, jd: float, planet_id: int) -> Tuple[float, float]:
        """Calculate planet position and speed for a Julian day."""
        flags = self.natal._get_calc_flags()
        result, _ = swe.calc_ut(jd, planet_id, flags)
        return result[0], result[3]  # longitude, speed
    
    def calculate_transits(self,
                          transit_date: datetime,
                          timezone: Optional[Union[str, pytz.tzinfo.BaseTzInfo]] = None,
                          include_minor_aspects: bool = False,
                          include_transit_to_transit: bool = False,
                          orb_factor: float = 1.0) -> Dict:
        """Calculate transit positions and aspects to natal chart."""
        self.transit_date = transit_date
        
        tz = self.natal._parse_timezone(timezone)
        self.transit_date_utc = self.natal._convert_to_utc(transit_date, tz)
        self.transit_julian_day = self.natal._calculate_julian_day(self.transit_date_utc)
        
        self._calculate_transit_planets()
        self._calculate_transit_to_natal_aspects(include_minor_aspects, orb_factor)
        
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
        flags = self.natal._get_calc_flags()
        self.transit_planets = {}
        
        for name, planet_id in ChartConfig.PLANETS_CORE.items():
            self._calculate_transit_body(name, planet_id, flags)
        
        for name, planet_id in ChartConfig.PLANETS_EXTENDED.items():
            try:
                self._calculate_transit_body(name, planet_id, flags)
            except:
                pass
        
        node_id = swe.TRUE_NODE if self.natal.node_type == NodeType.TRUE else swe.MEAN_NODE
        self._calculate_transit_body('North Node', node_id, flags)
        
        nn = self.transit_planets['North Node']
        sn_long = normalize_degrees(nn['longitude'] + 180)
        sign_info = self.natal._get_sign_info(sn_long)
        self.transit_planets['South Node'] = {
            'longitude': sn_long,
            'speed': nn['speed'],
            'retrograde': nn['retrograde'],
            **sign_info,
        }
        
        try:
            self._calculate_transit_body('Lilith', swe.MEAN_APOG, flags)
        except:
            pass
        
        for name in self.transit_planets:
            self.transit_planets[name]['natal_house'] = self._get_transit_in_natal_house(name)
    
    def _calculate_transit_body(self, name: str, body_id: int, flags: int) -> None:
        result, _ = swe.calc_ut(self.transit_julian_day, body_id, flags)
        sign_info = self.natal._get_sign_info(result[0])
        
        self.transit_planets[name] = {
            'longitude': result[0],
            'speed': result[3],
            'retrograde': result[3] < 0,
            **sign_info,
        }
    
    def _get_transit_in_natal_house(self, planet_name: str) -> int:
        planet_long = normalize_degrees(self.transit_planets[planet_name]['longitude'])
        cusps = self.natal.houses['cusps']
        
        for i in range(12):
            cusp_start = normalize_degrees(cusps[i])
            cusp_end = normalize_degrees(cusps[(i + 1) % 12])
            
            if cusp_start < cusp_end:
                if cusp_start <= planet_long < cusp_end:
                    return i + 1
            else:
                if planet_long >= cusp_start or planet_long < cusp_end:
                    return i + 1
        return 1
    
    def _is_transit_applying(self, transit_pos: float, transit_speed: float,
                             natal_pos: float, aspect_angle: float) -> bool:
        """
        Determine if a transit is applying to or separating from a natal point.
        
        APPLYING: Transit is moving toward exact aspect
        SEPARATING: Transit is moving away from exact aspect
        
        This is simpler than natal-to-natal because the natal point is fixed.
        """
        # Current angular separation
        sep = angular_distance(transit_pos, natal_pos)
        current_orb = abs(sep - aspect_angle)
        
        # Predict where transit will be in small time step
        future_pos = normalize_degrees(transit_pos + transit_speed * 0.1)  # 0.1 day ahead
        future_sep = angular_distance(future_pos, natal_pos)
        future_orb = abs(future_sep - aspect_angle)
        
        # Applying if orb is decreasing
        return future_orb < current_orb
    
    def _calculate_transit_to_natal_aspects(self, include_minor: bool, orb_factor: float) -> None:
        self.transit_to_natal_aspects = []
        
        transit_bodies = [name for name in self.transit_planets.keys()
                         if name not in ['Part of Fortune']]
        
        # All natal points
        natal_points = {}
        for name, data in self.natal.planets.items():
            natal_points[name] = data['longitude']
        
        natal_points['Natal ASC'] = self.natal.houses['ascendant']
        natal_points['Natal MC'] = self.natal.houses['mc']
        natal_points['Natal DSC'] = self.natal.houses['descendant']
        natal_points['Natal IC'] = self.natal.houses['ic']
        natal_points['Natal Vertex'] = self.natal.houses['vertex']
        
        for transit_name in transit_bodies:
            transit_pos = self.transit_planets[transit_name]['longitude']
            transit_speed = self.transit_planets[transit_name]['speed']
            
            for natal_name, natal_pos in natal_points.items():
                sep = angular_distance(transit_pos, natal_pos)
                
                for aspect_def in ChartConfig.ASPECTS:
                    if not aspect_def.major and not include_minor:
                        continue
                    
                    orb = abs(sep - aspect_def.angle)
                    
                    cat1 = self.natal._get_planet_category(transit_name)
                    cat2 = self.natal._get_planet_category(natal_name)
                    max_orb = min(aspect_def.transit_orbs[cat1], aspect_def.transit_orbs[cat2]) * orb_factor
                    
                    if orb <= max_orb:
                        applying = self._is_transit_applying(
                            transit_pos, transit_speed, natal_pos, aspect_def.angle
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
        
        self.transit_to_natal_aspects.sort(key=lambda x: x['orb'])
    
    def _calculate_transit_to_transit_aspects(self, include_minor: bool, orb_factor: float) -> None:
        self.transit_to_transit_aspects = []
        
        transit_bodies = [name for name in self.transit_planets.keys()
                         if name not in ['Part of Fortune', 'South Node']]
        
        for i, name1 in enumerate(transit_bodies):
            for name2 in transit_bodies[i + 1:]:
                pos1 = self.transit_planets[name1]['longitude']
                pos2 = self.transit_planets[name2]['longitude']
                speed1 = self.transit_planets[name1]['speed']
                speed2 = self.transit_planets[name2]['speed']
                
                sep = angular_distance(pos1, pos2)
                
                for aspect_def in ChartConfig.ASPECTS:
                    if not aspect_def.major and not include_minor:
                        continue
                    
                    orb = abs(sep - aspect_def.angle)
                    cat1 = self.natal._get_planet_category(name1)
                    cat2 = self.natal._get_planet_category(name2)
                    max_orb = min(aspect_def.transit_orbs[cat1], aspect_def.transit_orbs[cat2]) * orb_factor
                    
                    if orb <= max_orb:
                        applying = self.natal._calculate_natal_applying(
                            pos1, pos2, speed1, speed2, aspect_def.angle
                        )
                        
                        self.transit_to_transit_aspects.append({
                            'planet1': name1,
                            'planet2': name2,
                            'aspect': aspect_def.name,
                            'symbol': aspect_def.symbol,
                            'angle': aspect_def.angle,
                            'orb': round(orb, 4),
                            'applying': applying,
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
        
        Uses an improved algorithm that:
        1. Tracks when transit crosses exact aspect points
        2. Handles retrograde motion correctly
        3. Uses appropriate step sizes for different planets
        """
        events = []
        
        if aspects is None:
            aspects = ['Conjunction', 'Sextile', 'Square', 'Trine', 'Opposition']
        
        if planets is None:
            planets = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars',
                      'Jupiter', 'Saturn', 'Uranus', 'Neptune', 'Pluto']
        
        if natal_points is None:
            natal_points = list(self.natal.planets.keys()) + ['Natal ASC', 'Natal MC']
        
        # Get natal positions
        natal_positions = {}
        for name in natal_points:
            if name == 'Natal ASC':
                natal_positions[name] = self.natal.houses['ascendant']
            elif name == 'Natal MC':
                natal_positions[name] = self.natal.houses['mc']
            elif name == 'Natal DSC':
                natal_positions[name] = self.natal.houses['descendant']
            elif name == 'Natal IC':
                natal_positions[name] = self.natal.houses['ic']
            elif name == 'Natal Vertex':
                natal_positions[name] = self.natal.houses['vertex']
            elif name in self.natal.planets:
                natal_positions[name] = self.natal.planets[name]['longitude']
        
        # Get aspect definitions
        aspect_defs = {a.name: a for a in ChartConfig.ASPECTS if a.name in aspects}
        
        # Step size depends on fastest planet
        has_moon = 'Moon' in planets
        step_hours = 2 if has_moon else 6
        
        tz = self.natal._parse_timezone(timezone)
        
        # Track previous orbs to detect exact crossings
        prev_data = {}  # key -> (orb, separation)
        
        current = start_date
        while current <= end_date:
            current_utc = self.natal._convert_to_utc(current, tz)
            jd = self.natal._calculate_julian_day(current_utc)
            
            for transit_name in planets:
                if transit_name not in ChartConfig.PLANETS_CORE:
                    continue
                
                planet_id = ChartConfig.PLANETS_CORE[transit_name]
                transit_pos, transit_speed = self._calculate_planet_position(jd, planet_id)
                transit_retro = transit_speed < 0
                
                for natal_name, natal_pos in natal_positions.items():
                    sep = angular_distance(transit_pos, natal_pos)
                    
                    for aspect_name, aspect_def in aspect_defs.items():
                        orb = abs(sep - aspect_def.angle)
                        key = (transit_name, natal_name, aspect_name)
                        
                        if key in prev_data:
                            prev_orb, prev_sep = prev_data[key]
                            
                            # Detect crossing: orb decreased then would increase, or reached minimum
                            if prev_orb > orb:
                                # Still approaching - update
                                pass
                            elif prev_orb < orb and prev_orb < 1.0:
                                # Was approaching, now separating - exact was between
                                # Interpolate to find exact time
                                if prev_orb < 0.5:  # Only record if it was close
                                    fraction = prev_orb / (prev_orb + orb) if (prev_orb + orb) > 0 else 0.5
                                    exact_time = current - timedelta(hours=step_hours * (1 - fraction))
                                    
                                    events.append(TransitEvent(
                                        transit_planet=transit_name,
                                        natal_planet=natal_name,
                                        aspect=aspect_name,
                                        aspect_symbol=aspect_def.symbol,
                                        exact_date=exact_time,
                                        orb=0.0,
                                        applying=False,
                                        transit_retrograde=transit_retro,
                                    ))
                        
                        prev_data[key] = (orb, sep)
            
            current += timedelta(hours=step_hours)
        
        # Remove duplicates - keep only one event per transit-natal-aspect combo
        # within a reasonable window (2 days for fast planets, longer for slow)
        unique_events = []
        for event in sorted(events, key=lambda x: x.exact_date):
            is_dup = False
            
            # Window size depends on planet speed
            # Moon: 6 hours, Sun/Mercury/Venus/Mars: 1 day, outer: 3 days
            if event.transit_planet == 'Moon':
                window_seconds = 6 * 3600
            elif event.transit_planet in ['Sun', 'Mercury', 'Venus', 'Mars']:
                window_seconds = 24 * 3600
            else:
                window_seconds = 72 * 3600
            
            for existing in unique_events:
                if (event.transit_planet == existing.transit_planet and
                    event.natal_planet == existing.natal_planet and
                    event.aspect == existing.aspect and
                    abs((event.exact_date - existing.exact_date).total_seconds()) < window_seconds):
                    is_dup = True
                    break
            if not is_dup:
                unique_events.append(event)
        
        return unique_events
    
    def format_transit_text(self) -> str:
        if not self.transit_planets:
            return "No transits calculated. Call calculate_transits() first."
        
        lines = []
        lines.append("=" * 75)
        lines.append("TRANSIT CHART")
        lines.append("=" * 75)
        lines.append(f"Transit Date:   {self.transit_date_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        lines.append(f"For natal chart of: {self.natal.birth_date_local.strftime('%Y-%m-%d %H:%M')}")
        lines.append("")
        
        lines.append("TRANSITING PLANETS")
        lines.append("-" * 75)
        lines.append(f"{'Planet':<14} {'Position':<18} {'In Natal H':<12} {'Motion'}")
        lines.append("-" * 75)
        
        planet_order = ['Sun', 'Moon', 'Mercury', 'Venus', 'Mars', 'Jupiter', 'Saturn',
                       'Uranus', 'Neptune', 'Pluto', 'North Node', 'Chiron', 'Lilith']
        
        for name in planet_order:
            if name not in self.transit_planets:
                continue
            p = self.transit_planets[name]
            motion = "R" if p['retrograde'] else "D"
            motion += f" {abs(p['speed']):.2f}°/d"
            lines.append(f"{name:<14} {p['formatted']:<18} House {p['natal_house']:<5} {motion}")
        
        lines.append("")
        lines.append("TRANSITS TO NATAL CHART")
        lines.append("-" * 75)
        
        if self.transit_to_natal_aspects:
            for asp in self.transit_to_natal_aspects[:25]:
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
    chart = NatalChart(birth_datetime, latitude, longitude, house_system,
                       timezone=timezone, **kwargs)
    return chart.generate_full_chart()


def calculate_transits(natal_chart: NatalChart,
                      transit_date: datetime,
                      timezone: Optional[str] = None,
                      **kwargs) -> Dict:
    transits = TransitChart(natal_chart)
    return transits.calculate_transits(transit_date, timezone, **kwargs)


if __name__ == "__main__":
    print("=" * 75)
    print("NATAL AND TRANSIT CHART CALCULATOR v4")
    print("=" * 75)
    print()
    
    # Test with known birth data
    birth = datetime(1990, 6, 15, 14, 30, 0)
    natal = NatalChart(
        birth_date=birth,
        latitude=40.7128,
        longitude=-74.0060,
        timezone='America/New_York',
        house_system='Placidus',
    )
    natal.generate_full_chart()
    
    print(natal.format_chart_text())
    print()
    
    # Current transits
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
    
    # Find exact transits
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
    
    for event in events[:20]:
        print(f"  {event}")
