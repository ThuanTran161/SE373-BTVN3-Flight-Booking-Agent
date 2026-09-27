import json
from typing import Dict, Any
from langchain_core.tools import tool

# Mock Database
MOCK_FLIGHTS = [
    {
        "flight_id": "VN122", "airline": "Vietnam Airlines",
        "origin": "SGN", "dest": "DAD", "date": "2026-10-07",
        "dep_time": "08:30", "price": 1850000, "refundable": False,
        "seats": ["12A", "12B"]
    },
    {
        "flight_id": "VJ604", "airline": "Vietjet Air",
        "origin": "SGN", "dest": "DAD", "date": "2026-10-07",
        "dep_time": "11:15", "price": 2300000, "refundable": True,
        "seats": ["15C"]
    },
    {
        "flight_id": "QH118", "airline": "Bamboo Airways",
        "origin": "SGN", "dest": "DAD", "date": "2026-10-07",
        "dep_time": "10:00", "price": 1750000, "refundable": True,
        "seats": ["05D", "05E"]
    }
]

MOCK_BOOKINGS: Dict[str, Dict[str, Any]] = {}


@tool
def search_flights(origin: str, dest: str, date: str) -> str:
    """Tìm kiếm danh sách chuyến bay theo nơi đi, nơi đến và ngày bay (YYYY-MM-DD)."""
    matches = [f for f in MOCK_FLIGHTS if f["origin"] == origin and f["dest"] == dest and f["date"] == date]
    if not matches:
        return json.dumps({"status": "empty", "matched": 0, "flights": []})
    return json.dumps({"status": "success", "matched": len(matches), "flights": matches})


@tool
def check_seat(flight_id: str) -> str:
    """Kiểm tra tình trạng ghế trống, giá vé và chính sách hoàn huỷ của chuyến bay."""
    for f in MOCK_FLIGHTS:
        if f["flight_id"] == flight_id:
            return json.dumps({
                "status": "success",
                "flight_id": flight_id,
                "available_seats": f["seats"],
                "price": f["price"],
                "refundable": f["refundable"],
                "dep_time": f["dep_time"]
            })
    return json.dumps({"status": "not_found", "flight_id": flight_id, "hint": "Sai mã chuyến bay"})


@tool
def book_seat(flight_id: str, seat_number: str) -> str:
    """Giữ chỗ chuyến bay và tạo mã đặt chỗ tạm thời."""
    flight = next((f for f in MOCK_FLIGHTS if f["flight_id"] == flight_id), None)
    if not flight or seat_number not in flight["seats"]:
        return json.dumps({"status": "failed", "reason": "seat_unavailable"})

    booking_code = f"BK_{flight_id}_{seat_number}"
    MOCK_BOOKINGS[booking_code] = {
        "booking_code": booking_code,
        "flight_id": flight_id,
        "seat": seat_number,
        "price": flight["price"],
        "date": flight["date"],
        "dep_time": flight["dep_time"],
        "refundable": flight["refundable"],
        "status": "held",
        "paid": False
    }
    flight["seats"].remove(seat_number)
    return json.dumps({"status": "held", "booking_code": booking_code, "price": flight["price"]})


@tool
def pay(booking_code: str, card_type: str = "corp_card") -> str:
    """Thực hiện thanh toán tiền vé máy bay qua cổng thanh toán."""
    if booking_code not in MOCK_BOOKINGS:
        return json.dumps({"status": "error", "message": "booking_not_found"})
    MOCK_BOOKINGS[booking_code]["status"] = "confirmed"
    MOCK_BOOKINGS[booking_code]["paid"] = True
    return json.dumps({"status": "paid", "booking_code": booking_code, "paid": True})


def get_booking(booking_code: str) -> str:
    """Hàm phụ trợ cho Harness Sensor đọc dữ liệu trạng thái."""
    if booking_code in MOCK_BOOKINGS:
        return json.dumps({"status": "found", "data": MOCK_BOOKINGS[booking_code]})
    return json.dumps({"status": "not_found"})


def reset_mock_db():
    """Reset trạng thái dữ liệu khi chạy test."""
    global MOCK_FLIGHTS, MOCK_BOOKINGS
    MOCK_BOOKINGS.clear()
    MOCK_FLIGHTS[0]["seats"] = ["12A", "12B"]
    MOCK_FLIGHTS[1]["seats"] = ["15C"]
    MOCK_FLIGHTS[2]["seats"] = ["05D", "05E"]