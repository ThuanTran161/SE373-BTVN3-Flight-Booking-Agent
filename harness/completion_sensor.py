import json
from typing import Tuple
from harness.constraints import BookingConstraint
from tools.flight_tools import get_booking

class CompletionSensor:
    @staticmethod
    def verify(booking_code: str, constraints: BookingConstraint) -> Tuple[bool, str]:
        if not booking_code:
            return False, "Không có mã đặt chỗ."

        raw = get_booking(booking_code)
        res = json.loads(raw)
        if res.get("status") != "found":
            return False, "Không tìm thấy dữ liệu đặt chỗ."

        b = res["data"]
        is_confirmed = (b.get("status") == "confirmed")
        is_paid = (b.get("paid") is True)
        is_price_ok = (b.get("price", float("inf")) <= constraints.max_price)
        is_date_ok = (b.get("date") == constraints.date)
        is_time_ok = (b.get("dep_time", "99:99") <= constraints.depart_before)

        if not (is_confirmed and is_paid):
            return False, "Vé chưa ở trạng thái xác nhận hoặc chưa trả tiền."
        if not is_price_ok:
            return False, f"Giá vé {b.get('price')}đ vượt quá trần {constraints.max_price}đ."
        if not (is_date_ok and is_time_ok):
            return False, "Chuyến bay không khớp ngày giờ."

        return True, "Hoàn tất hợp lệ: Đã xác nhận, đã trả tiền, chuẩn ràng buộc."