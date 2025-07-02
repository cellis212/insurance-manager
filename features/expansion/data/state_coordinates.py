"""Geographic coordinates for US states.

Contains latitude and longitude for each state's geographic center,
used for calculating distances in expansion cost calculations.
"""

from typing import Dict, Tuple

# State geographic centers (latitude, longitude)
# Source: US Census Bureau geographic centers
STATE_COORDINATES: Dict[str, Tuple[float, float]] = {
    "AL": (32.806671, -86.791130),     # Alabama
    "AK": (61.370716, -152.404419),    # Alaska
    "AZ": (33.729759, -111.431221),    # Arizona
    "AR": (34.969704, -92.373123),     # Arkansas
    "CA": (36.116203, -119.681564),    # California
    "CO": (39.059811, -105.311104),    # Colorado
    "CT": (41.597782, -72.755371),     # Connecticut
    "DE": (39.318523, -75.507141),     # Delaware
    "DC": (38.907192, -77.036873),     # District of Columbia
    "FL": (27.766279, -81.686783),     # Florida
    "GA": (33.040619, -83.643074),     # Georgia
    "HI": (21.094318, -157.498337),    # Hawaii
    "ID": (44.240459, -114.478828),    # Idaho
    "IL": (40.349457, -88.986137),     # Illinois
    "IN": (39.849426, -86.258278),     # Indiana
    "IA": (42.011539, -93.210526),     # Iowa
    "KS": (38.526600, -96.726486),     # Kansas
    "KY": (37.668140, -84.670067),     # Kentucky
    "LA": (31.169546, -91.867805),     # Louisiana
    "ME": (44.693947, -69.381927),     # Maine
    "MD": (39.063946, -76.802101),     # Maryland
    "MA": (42.230171, -71.530106),     # Massachusetts
    "MI": (43.326618, -84.536095),     # Michigan
    "MN": (45.694454, -93.900192),     # Minnesota
    "MS": (32.741646, -89.678696),     # Mississippi
    "MO": (38.456085, -92.288368),     # Missouri
    "MT": (46.921925, -110.454353),    # Montana
    "NE": (41.125370, -98.268082),     # Nebraska
    "NV": (38.313515, -117.055374),    # Nevada
    "NH": (43.452492, -71.563896),     # New Hampshire
    "NJ": (40.298904, -74.521011),     # New Jersey
    "NM": (34.840515, -106.248482),    # New Mexico
    "NY": (42.165726, -74.948051),     # New York
    "NC": (35.630066, -79.806419),     # North Carolina
    "ND": (47.528912, -99.784012),     # North Dakota
    "OH": (40.388783, -82.764915),     # Ohio
    "OK": (35.565342, -96.928917),     # Oklahoma
    "OR": (43.804133, -120.554201),    # Oregon
    "PA": (40.590752, -77.209755),     # Pennsylvania
    "RI": (41.680893, -71.511780),     # Rhode Island
    "SC": (33.856892, -80.945007),     # South Carolina
    "SD": (44.299782, -99.438828),     # South Dakota
    "TN": (35.747845, -86.692345),     # Tennessee
    "TX": (31.054487, -97.563461),     # Texas
    "UT": (40.150032, -111.862434),    # Utah
    "VT": (44.045876, -72.710686),     # Vermont
    "VA": (37.769337, -78.169968),     # Virginia
    "WA": (47.400902, -121.490494),    # Washington
    "WV": (38.491226, -80.954570),     # West Virginia
    "WI": (44.268543, -89.616508),     # Wisconsin
    "WY": (42.755966, -107.302490),    # Wyoming
}

# State regions for regional bonuses/penalties
STATE_REGIONS: Dict[str, str] = {
    # Northeast
    "CT": "Northeast", "ME": "Northeast", "MA": "Northeast", 
    "NH": "Northeast", "RI": "Northeast", "VT": "Northeast",
    "NJ": "Northeast", "NY": "Northeast", "PA": "Northeast",
    
    # Southeast
    "AL": "Southeast", "AR": "Southeast", "FL": "Southeast",
    "GA": "Southeast", "KY": "Southeast", "LA": "Southeast",
    "MS": "Southeast", "NC": "Southeast", "SC": "Southeast",
    "TN": "Southeast", "VA": "Southeast", "WV": "Southeast",
    
    # Midwest
    "IL": "Midwest", "IN": "Midwest", "IA": "Midwest",
    "KS": "Midwest", "MI": "Midwest", "MN": "Midwest",
    "MO": "Midwest", "NE": "Midwest", "ND": "Midwest",
    "OH": "Midwest", "SD": "Midwest", "WI": "Midwest",
    
    # Southwest
    "AZ": "Southwest", "NM": "Southwest", "OK": "Southwest", "TX": "Southwest",
    
    # West
    "AK": "West", "CA": "West", "CO": "West", "HI": "West",
    "ID": "West", "MT": "West", "NV": "West", "OR": "West",
    "UT": "West", "WA": "West", "WY": "West",
    
    # Other
    "DC": "Mid-Atlantic", "DE": "Mid-Atlantic", "MD": "Mid-Atlantic"
}

# State border adjacencies for expansion bonuses
STATE_ADJACENCIES: Dict[str, set] = {
    "AL": {"FL", "GA", "MS", "TN"},
    "AK": set(),  # No land borders
    "AZ": {"CA", "CO", "NM", "NV", "UT"},
    "AR": {"LA", "MO", "MS", "OK", "TN", "TX"},
    "CA": {"AZ", "NV", "OR"},
    "CO": {"AZ", "KS", "NE", "NM", "OK", "UT", "WY"},
    "CT": {"MA", "NY", "RI"},
    "DE": {"MD", "NJ", "PA"},
    "DC": {"MD", "VA"},
    "FL": {"AL", "GA"},
    "GA": {"AL", "FL", "NC", "SC", "TN"},
    "HI": set(),  # No land borders
    "ID": {"MT", "NV", "OR", "UT", "WA", "WY"},
    "IL": {"IN", "IA", "KY", "MO", "WI"},
    "IN": {"IL", "KY", "MI", "OH"},
    "IA": {"IL", "MN", "MO", "NE", "SD", "WI"},
    "KS": {"CO", "MO", "NE", "OK"},
    "KY": {"IL", "IN", "MO", "OH", "TN", "VA", "WV"},
    "LA": {"AR", "MS", "TX"},
    "ME": {"NH"},
    "MD": {"DC", "DE", "PA", "VA", "WV"},
    "MA": {"CT", "NH", "NY", "RI", "VT"},
    "MI": {"IN", "OH", "WI"},
    "MN": {"IA", "ND", "SD", "WI"},
    "MS": {"AL", "AR", "LA", "TN"},
    "MO": {"AR", "IA", "IL", "KS", "KY", "NE", "OK", "TN"},
    "MT": {"ID", "ND", "SD", "WY"},
    "NE": {"CO", "IA", "KS", "MO", "SD", "WY"},
    "NV": {"AZ", "CA", "ID", "OR", "UT"},
    "NH": {"MA", "ME", "VT"},
    "NJ": {"DE", "NY", "PA"},
    "NM": {"AZ", "CO", "OK", "TX"},
    "NY": {"CT", "MA", "NJ", "PA", "VT"},
    "NC": {"GA", "SC", "TN", "VA"},
    "ND": {"MN", "MT", "SD"},
    "OH": {"IN", "KY", "MI", "PA", "WV"},
    "OK": {"AR", "CO", "KS", "MO", "NM", "TX"},
    "OR": {"CA", "ID", "NV", "WA"},
    "PA": {"DE", "MD", "NJ", "NY", "OH", "WV"},
    "RI": {"CT", "MA"},
    "SC": {"GA", "NC"},
    "SD": {"IA", "MN", "MT", "ND", "NE", "WY"},
    "TN": {"AL", "AR", "GA", "KY", "MO", "MS", "NC", "VA"},
    "TX": {"AR", "LA", "NM", "OK"},
    "UT": {"AZ", "CO", "ID", "NV", "WY"},
    "VT": {"MA", "NH", "NY"},
    "VA": {"DC", "KY", "MD", "NC", "TN", "WV"},
    "WA": {"ID", "OR"},
    "WV": {"KY", "MD", "OH", "PA", "VA"},
    "WI": {"IA", "IL", "MI", "MN"},
    "WY": {"CO", "ID", "MT", "NE", "SD", "UT"},
} 