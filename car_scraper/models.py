from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any
from utils.formatters import clean_price, clean_mileage

class CarListing(BaseModel):
    # Required fields
    make: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    year: int = Field(..., ge=1990, le=2026)
    price: int
    mileage: int
    fuel_type: str
    transmission: str
    location: str
    listing_url: str
    posted_date: str

    # Optional fields
    title: Optional[str] = None
    body_type: Optional[str] = None
    dealer_or_private: Optional[str] = None
    doors: Optional[int] = None
    horsepower: Optional[int] = None
    first_registration: Optional[str] = None
    condition: Optional[str] = None

    @field_validator('price', mode='before')
    @classmethod
    def parse_price(cls, v: Any) -> Any:
        return clean_price(v) if isinstance(v, str) else v

    @field_validator('mileage', mode='before')
    @classmethod
    def parse_mileage(cls, v: Any) -> Any:
        return clean_mileage(v) if isinstance(v, str) else v
