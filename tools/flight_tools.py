import json
import copy
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import tool

# Initial Mock Flights Database
INITIAL_MOCK_FLIGHTS = [
    {
        "flight_id": "VN122",
        "airline": "Vietnam Airlines",
        "origin": "SGN",
        "dest": "DAD",
        "date": "2026-10-07",
        "dep_time": "08:30",
        "price": 1850000,
        "refundable": False,
        "seats": ["12A", "12B"],
        "baggage_rate_per_kg": 25000
    },
    {
        "flight_id": "VJ604",
        "airline": "Vietjet Air",
        "origin": "SGN",
        "dest": "DAD",
        "date": "2026-10-07",
        "dep_time": "11:15",
        "price": 2300000,
        "refundable": True,
        "seats": ["15C"],
        "baggage_rate_per_kg": 20000
    },
    {
        "flight_id": "QH118",
        "airline": "Bamboo Airways",
        "origin": "SGN",
        "dest": "DAD",
        "date": "2026-10-07",
        "dep_time": "10:00",
        "price": 1750000,
        "refundable": True,
        "seats": ["05D", "05E"],
        "baggage_rate_per_kg": 22000
    },
    {
        "flight_id": "VN214",
        "airline": "Vietnam Airlines",
        "origin": "HAN",
        "dest": "SGN",
        "date": "2026-10-08",
        "dep_time": "09:00",
        "price": 1900000,
        "refundable": True,
        "seats": ["14A", "14B"],
        "baggage_rate_per_kg": 25000
    },
    {
        "flight_id": "VJ180",
        "airline": "Vietjet Air",
        "origin": "DAD",
        "dest": "SGN",
        "date": "2026-10-10",
        "dep_time": "14:00",
        "price": 1600000,
        "refundable": True,
        "seats": ["18A", "18C"],
        "baggage_rate_per_kg": 20000
    }
]

# Runtime state
MOCK_FLIGHTS: List[Dict[str, Any]] = copy.deepcopy(INITIAL_MOCK_FLIGHTS)
MOCK_BOOKINGS: Dict[str, Dict[str, Any]] = {}


# --- Pydantic Argument Schemas for Tools ---

class SearchFlightsInput(BaseModel):
    origin: str = Field(description="Mã sân bay khởi hành (ví dụ: SGN, HAN, DAD)")
    dest: str = Field(description="Mã sân bay điểm đến (ví dụ: DAD, SGN, HAN)")
    date: str = Field(description="Ngày khởi hành theo định dạng YYYY-MM-DD (ví dụ: 2026-10-07)")


class CheckSeatInput(BaseModel):
    flight_id: str = Field(description="Mã hiệu chuyến bay (ví dụ: VN122, QH118, VJ604)")


class CalculateBaggageInput(BaseModel):
    flight_id: str = Field(description="Mã hiệu chuyến bay (ví dụ: VN122, QH118)")
    baggage_kg: int = Field(default=0, ge=0, description="Khối lượng hành lý ký gửi bổ sung tính bằng kg")


class BookTicketInput(BaseModel):
    flight_id: str = Field(description="Mã hiệu chuyến bay cần đặt (ví dụ: VN122, QH118)")
    seat_number: str = Field(description="Số ghế đã chọn (ví dụ: 05D, 12A)")
    passenger_name: str = Field(default="Nguyen Van A", description="Họ và tên hành khách đi máy bay")
    baggage_kg: int = Field(default=0, ge=0, description="Khối lượng hành lý ký gửi (kg)")


# --- Mock Tools Definitions ---

@tool(args_schema=SearchFlightsInput)
def search_flights(origin: str, dest: str, date: str) -> str:
    """Tìm kiếm danh sách chuyến bay theo điểm khởi hành, điểm đến và ngày bay (YYYY-MM-DD)."""
    origin_clean = origin.strip().upper()
    dest_clean = dest.strip().upper()
    date_clean = date.strip()

    matches = [
        f for f in MOCK_FLIGHTS
        if f["origin"] == origin_clean and f["dest"] == dest_clean and f["date"] == date_clean
    ]
    if not matches:
        return json.dumps({
            "status": "empty",
            "matched": 0,
            "message": f"Không tìm thấy chuyến bay từ {origin_clean} đến {dest_clean} ngày {date_clean}.",
            "flights": []
        }, ensure_ascii=False)

    return json.dumps({
        "status": "success",
        "matched": len(matches),
        "flights": matches
    }, ensure_ascii=False)


@tool(args_schema=CheckSeatInput)
def check_seat_availability(flight_id: str) -> str:
    """Kiểm tra tình trạng ghế còn trống, giá vé cơ bản, thời gian bay và chính sách hoàn hủy của một chuyến bay."""
    fid = flight_id.strip().upper()
    flight = next((f for f in MOCK_FLIGHTS if f["flight_id"] == fid), None)
    if not flight:
        return json.dumps({
            "status": "not_found",
            "flight_id": fid,
            "message": f"Không tìm thấy chuyến bay có mã {fid}."
        }, ensure_ascii=False)

    return json.dumps({
        "status": "success",
        "flight_id": fid,
        "airline": flight["airline"],
        "available_seats": flight["seats"],
        "seat_count": len(flight["seats"]),
        "base_price": flight["price"],
        "dep_time": flight["dep_time"],
        "refundable": flight["refundable"]
    }, ensure_ascii=False)


@tool(args_schema=CalculateBaggageInput)
def calculate_baggage_fee(flight_id: str, baggage_kg: int) -> str:
    """Tính cước phí hành lý ký gửi theo hãng bay và khối lượng hành lý (kg)."""
    fid = flight_id.strip().upper()
    flight = next((f for f in MOCK_FLIGHTS if f["flight_id"] == fid), None)
    if not flight:
        return json.dumps({
            "status": "not_found",
            "flight_id": fid,
            "message": f"Không tìm thấy chuyến bay {fid} để tính phí hành lý."
        }, ensure_ascii=False)

    if baggage_kg <= 0:
        return json.dumps({
            "status": "success",
            "flight_id": fid,
            "baggage_kg": 0,
            "baggage_fee": 0,
            "message": "Không có hành lý ký gửi thêm (0 VND)."
        }, ensure_ascii=False)

    rate = flight.get("baggage_rate_per_kg", 20000)
    fee = int(baggage_kg * rate)
    return json.dumps({
        "status": "success",
        "flight_id": fid,
        "airline": flight["airline"],
        "baggage_kg": baggage_kg,
        "rate_per_kg": rate,
        "baggage_fee": fee
    }, ensure_ascii=False)


@tool(args_schema=BookTicketInput)
def book_ticket(flight_id: str, seat_number: str, passenger_name: str = "Nguyen Van A", baggage_kg: int = 0) -> str:
    """Thực hiện chốt vé máy bay chính thức và trừ tiền. Đây là hành động nhạy cảm cần phê duyệt."""
    fid = flight_id.strip().upper()
    seat = seat_number.strip().upper()

    flight = next((f for f in MOCK_FLIGHTS if f["flight_id"] == fid), None)
    if not flight:
        return json.dumps({
            "status": "failed",
            "reason": "flight_not_found",
            "message": f"Không tìm thấy chuyến bay {fid}."
        }, ensure_ascii=False)

    if seat not in flight["seats"]:
        return json.dumps({
            "status": "failed",
            "reason": "seat_unavailable",
            "message": f"Ghế {seat} không còn trống trên chuyến {fid}. Các ghế hiện có: {flight['seats']}"
        }, ensure_ascii=False)

    # Tính phí hành lý
    baggage_rate = flight.get("baggage_rate_per_kg", 20000)
    baggage_fee = int(baggage_kg * baggage_rate) if baggage_kg > 0 else 0
    total_price = flight["price"] + baggage_fee

    booking_code = f"BK_{fid}_{seat}"
    booking_record = {
        "booking_code": booking_code,
        "flight_id": fid,
        "airline": flight["airline"],
        "passenger_name": passenger_name,
        "seat": seat,
        "origin": flight["origin"],
        "dest": flight["dest"],
        "date": flight["date"],
        "dep_time": flight["dep_time"],
        "ticket_price": flight["price"],
        "baggage_kg": baggage_kg,
        "baggage_fee": baggage_fee,
        "total_price": total_price,
        "refundable": flight["refundable"],
        "status": "confirmed",
        "paid": True
    }

    # Ghi nhận vào Mock Database
    MOCK_BOOKINGS[booking_code] = booking_record
    flight["seats"].remove(seat)

    return json.dumps({
        "status": "success",
        "booking_code": booking_code,
        "flight_id": fid,
        "passenger_name": passenger_name,
        "seat": seat,
        "date": flight["date"],
        "dep_time": flight["dep_time"],
        "total_price": total_price,
        "paid": True,
        "message": f"Đặt vé thành công! Mã đặt chỗ: {booking_code}, tổng thanh toán: {total_price:,.0f} VND."
    }, ensure_ascii=False)


# --- Backward compatibility aliases for existing tests ---
@tool
def check_seat(flight_id: str) -> str:
    """Tương thích ngược: Kiểm tra ghế."""
    return check_seat_availability.invoke({"flight_id": flight_id})


@tool
def book_seat(flight_id: str, seat_number: str) -> str:
    """Tương thích ngược: Đặt giữ chỗ."""
    return book_ticket.invoke({"flight_id": flight_id, "seat_number": seat_number})


@tool
def pay(booking_code: str) -> str:
    """Tương thích ngược: Xác nhận thanh toán mã vé."""
    if booking_code not in MOCK_BOOKINGS:
        return json.dumps({"status": "error", "message": "booking_not_found"}, ensure_ascii=False)
    MOCK_BOOKINGS[booking_code]["status"] = "confirmed"
    MOCK_BOOKINGS[booking_code]["paid"] = True
    return json.dumps({"status": "paid", "booking_code": booking_code, "paid": True}, ensure_ascii=False)


def get_booking(booking_code: str) -> str:
    """Hàm phụ trợ cho Harness Sensor đọc dữ liệu trạng thái."""
    if booking_code in MOCK_BOOKINGS:
        return json.dumps({"status": "found", "data": MOCK_BOOKINGS[booking_code]}, ensure_ascii=False)
    return json.dumps({"status": "not_found"}, ensure_ascii=False)


def set_flight_seats(flight_id: str, seats: List[str]):
    """Điều chỉnh ghế còn trống của một chuyến bay trong Mock DB ."""
    for f in MOCK_FLIGHTS:
        if f["flight_id"] == flight_id:
            f["seats"] = list(seats)


def reset_mock_db():
    """Reset trạng thái Mock Database về ban đầu."""
    global MOCK_BOOKINGS
    MOCK_BOOKINGS.clear()
    MOCK_FLIGHTS.clear()
    MOCK_FLIGHTS.extend(copy.deepcopy(INITIAL_MOCK_FLIGHTS))


# Danh sách các tool tiêu chuẩn cho Agent
AGENT_TOOLS = [
    search_flights,
    check_seat_availability,
    calculate_baggage_fee,
    book_ticket
]
