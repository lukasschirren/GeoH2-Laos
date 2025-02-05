DISPLAY_MAPPINGS = {
    'generation': {
        'display_to_internal': {
            "Optimistic": "total_generation",
            "Conservative": "net_generation"
        },
        'internal_to_display': {
            "total_generation": "Optimistic",
            "net_generation": "Conservative"
        }
    },
    'hydro': {
        'display_to_internal': {
            "High": "wet",
            "Low": "dry",
            "5 Year Average": "atlite"
        },
        'internal_to_display': {
            "wet": "High",
            "dry": "Low",
            "atlite": "5 Year Average"
        }
    },
    'year': {
        'display_to_internal': {
            "2025": "25",
            "2030": "30"
        },
        'internal_to_display': {
            "25": "2025",
            "30": "2030"
        }
    }
}