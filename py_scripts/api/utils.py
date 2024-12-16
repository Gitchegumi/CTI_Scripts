PLATFORM_URL = "https://platform.citytradersimperium.com"

def clean_positions(positions):
    """Remove unnecessary nested 'positions' field."""
    for position in positions:
        if "positions" in position:
            del position["positions"]
    return positions