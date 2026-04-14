import re

def clean_price(price_str: str) -> int:
    """Removes non-numeric characters (like € and commas) and returns an int."""
    if not price_str:
        return None
    # Provide logic: '€ 15.500,-' -> '15500'
    cleaned = re.sub(r'[^\d]', '', str(price_str))
    try:
        return int(cleaned) if cleaned else None
    except ValueError:
        return None

def clean_mileage(mileage_str: str) -> int:
    """Removes formatting and 'km' to return an int."""
    if not mileage_str:
        return None
    cleaned = re.sub(r'[^\d]', '', str(mileage_str))
    try:
        return int(cleaned) if cleaned else None
    except ValueError:
        return None
