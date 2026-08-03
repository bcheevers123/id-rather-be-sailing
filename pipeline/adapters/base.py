from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Offering:
    id: str
    course_id: str
    provider_id: str
    start_date: str
    end_date: str
    timezone: str
    duration_days: float | None
    price: float | None
    currency: str | None
    vat_included: bool | None
    delivery_format: str
    availability: str | None
    booking_url: str | None
    source_url: str
    last_verified: str
    freshness_status: str = "verified"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "course_id": self.course_id,
            "provider_id": self.provider_id,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "timezone": self.timezone,
            "duration_days": self.duration_days,
            "price": self.price,
            "currency": self.currency,
            "vat_included": self.vat_included,
            "delivery_format": self.delivery_format,
            "availability": self.availability,
            "booking_url": self.booking_url,
            "source_url": self.source_url,
            "last_verified": self.last_verified,
            "freshness_status": self.freshness_status,
        }


class BaseAdapter(ABC):
    @abstractmethod
    def fetch(self, provider: dict) -> list[Offering]:
        """Fetch offerings for the given provider. Returns empty list on any failure."""
