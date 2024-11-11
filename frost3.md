@dataclass
class FrostConfig:
    """Konfigurasjon for Frost API og datainnhenting"""
    
    ELEMENTS = {
        'air_temperature': {
            'unit': 'degC',
            'level': {'height_above_ground': 2},
            'resolutions': ['PT1H', 'PT10M']
        },
        'surface_snow_thickness': {
            'unit': 'cm',
            'level': None,
            'resolutions': ['PT1H', 'PT10M', 'P1D']
        },
        'sum(precipitation_amount PT1H)': {
            'unit': 'mm',
            'level': None,
            'resolutions': ['PT1H']
        },
        'wind_from_direction': {
            'unit': 'degrees',
            'level': {'height_above_ground': 10},
            'resolutions': ['PT1H']
        },
        'max(wind_speed_of_gust PT1H)': {
            'unit': 'm/s',
            'level': {'height_above_ground': 10},
            'resolutions': ['PT1H']
        },
        'surface_temperature': {
            'unit': 'degC',
            'level': {'height_above_ground': 0},
            'resolutions': ['PT1H', 'PT10M']
        },
        'relative_humidity': {
            'unit': 'percent',
            'level': {'height_above_ground': 2},
            'resolutions': ['PT1H']
        },
        'dew_point_temperature': {
            'unit': 'degC',
            'level': None,
            'resolutions': ['PT1H']
        }
    }
    
    # Metadata om målingene
    PERFORMANCE_CATEGORIES = ['C']  # Fra responsen
    EXPOSURE_CATEGORIES = ['2']     # Fra responsen
    QUALITY_CODES = {0: 'God'}      # Fra responsen