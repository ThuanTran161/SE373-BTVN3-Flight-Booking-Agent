from dataclasses import dataclass

@dataclass
class BookingConstraint:
    origin: str
    dest: str
    date: str
    max_price: int
    depart_before: str
    require_refundable: bool = False