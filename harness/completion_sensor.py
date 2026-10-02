import json
from typing import Tuple, Optional
from harness.constraints import BookingConstraint
from tools.flight_tools import get_booking


class CompletionSensor:


    @staticmethod
    def verify(booking_code: Optional[str], constraints: BookingConstraint) -> Tuple[bool, str]:
        if not booking_code:
            return False, "Không có mã đặt chỗ (booking_code is empty)."

        raw = get_booking(booking_code)
        res = json.loads(raw)
        if res.get("status") != "found":
            return False, f"Mã đặt chỗ '{booking_code}' không tồn tại trong hệ thống (Mock DB)."

        b = res["data"]
        is_confirmed = (b.get("status") == "confirmed")
        is_paid = (b.get("paid") is True)
        total_price = b.get("total_price", b.get("price", float("inf")))
        is_price_ok = (total_price <= constraints.max_price)
        is_date_ok = (b.get("date") == constraints.date)
        is_time_ok = (b.get("dep_time", "99:99") <= constraints.depart_before)
        is_route_ok = (
            b.get("origin", "").upper() == constraints.origin.upper() and
            b.get("dest", "").upper() == constraints.dest.upper()
        )

        if not (is_confirmed and is_paid):
            return False, f"Vé '{booking_code}' chưa được xác nhận hoàn tất hoặc chưa thanh toán thành công."

        if not is_route_ok:
            return False, f"Tuyến bay không khớp: Thực tế {b.get('origin')}->{b.get('dest')}, yêu cầu {constraints.origin}->{constraints.dest}."

        if not is_date_ok:
            return False, f"Ngày bay không khớp: Thực tế {b.get('date')}, yêu cầu {constraints.date}."

        if not is_time_ok:
            return False, f"Giờ bay {b.get('dep_time')} trễ hơn thời điểm yêu cầu ({constraints.depart_before})."

        if not is_price_ok:
            return False, f"Tổng chi phí {total_price:,.0f} VND vượt quá ngân sách trần ({constraints.max_price:,.0f} VND)."

        if constraints.require_refundable and not b.get("refundable", False):
            return False, "Vé được đặt không hỗ trợ hoàn hủy theo yêu cầu của khách hàng."

        if constraints.baggage_kg > 0 and b.get("baggage_kg", 0) < constraints.baggage_kg:
            return False, f"Hành lý ký gửi ({b.get('baggage_kg', 0)} kg) chưa đủ mức yêu cầu ({constraints.baggage_kg} kg)."

        return True, (
            f"XÁC MINH HỢP LỆ (100% PASS): Đã xác nhận vé {booking_code} cho {b.get('passenger_name')}, "
            f"chuyến {b.get('flight_id')} ngày {b.get('date')} lúc {b.get('dep_time')}, "
            f"tổng tiền {total_price:,.0f} VND."
        )
