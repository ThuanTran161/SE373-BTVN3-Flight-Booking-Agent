import sys
import json

# Ensure UTF-8 output encoding for Windows terminal
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from harness.constraints import BookingConstraint
from harness.permission import PermissionGuard
from harness.loop_detector import LoopDetector
from harness.completion_sensor import CompletionSensor
from harness.handoff import HandoffReport
from tools import flight_tools


def test_all():
    print("==================================================")
    print("   BẮT ĐẦU KIỂM THỬ ĐỘC LẬP TỪNG LỚP HARNESS")
    print("==================================================")

    # 1. KIỂM THỬ LỚP RÀNG BUỘC DỮ LIỆU
    constraint = BookingConstraint(
        origin="SGN", dest="DAD", date="2026-10-07",
        max_price=2200000, depart_before="12:00", baggage_kg=15
    )
    print("\n[1] Lớp Ràng buộc dữ liệu (Constraints):")
    print(f"    -> Đã khởi tạo mục tiêu dạng Pydantic: {constraint.model_dump()}")
    assert constraint.max_price == 2200000, "Lỗi khởi tạo trần giá!"
    assert constraint.baggage_kg == 15, "Lỗi khởi tạo hành lý!"

    # 2. KIỂM THỬ LỚP KIỂM QUYỀN (PERMISSION GUARD)
    guard = PermissionGuard(price_limit=2000000, auto_approve=False)
    print("\n[2] Lớp Kiểm quyền (Permission Guard):")

    # Test 2.1: Tool nhạy cảm thanh toán (pay) -> BẮT BUỘC BỊ CHẶN
    allowed_pay, msg_pay = guard.check_permission("pay", {}, {})
    print(f"    - Thử gọi 'pay': Cho phép = {allowed_pay} | Lý do: {msg_pay}")
    assert allowed_pay is False, "LỖI: Tool thanh toán không bị chặn!"

    # Test 2.2: Vé không hoàn tiền -> BẮT BUỘC BỊ CHẶN XIN PHÊ DUYỆT
    allowed_book, msg_book = guard.check_permission(
        "book_ticket",
        {"flight_id": "VN122", "seat_number": "12A"},
        {"current_price": 1850000, "refundable": False}
    )
    print(f"    - Thử đặt vé non-refundable: Cho phép = {allowed_book} | Lý do: {msg_book}")
    assert allowed_book is False, "LỖI: Vé không hoàn tiền không bị chặn!"

    # Test 2.3: Chế độ auto_approve -> PHẢI CHO QUA TỰ ĐỘNG
    guard_auto = PermissionGuard(auto_approve=True)
    allowed_auto, _ = guard_auto.check_permission("book_ticket", {"flight_id": "QH118"})
    print(f"    - Thử đặt vé khi auto_approve=True: Cho phép = {allowed_auto}")
    assert allowed_auto is True, "LỖI: Auto approve không hoạt động!"

    # 3. KIỂM THỬ BỘ PHÁT HIỆN LẶP (LOOP DETECTOR)
    detector = LoopDetector(repeat_k=2)
    print("\n[3] Bộ phát hiện Lặp (Loop Detector):")

    res1 = detector.check("search_flights", {"origin": "SGN", "dest": "DAD"})
    print(f"    - Vòng 1 gọi 'search_flights': {res1}")
    assert res1 is None, "Vòng 1 không được báo lặp!"

    res2 = detector.check("search_flights", {"origin": "SGN", "dest": "DAD"})
    print(f"    - Vòng 2 gọi lại đúng tham số: {res2}")
    assert res2 == "LOOP", "LỖI: Không phát hiện được hành động lặp!"

    # 4. KIỂM THỬ TIÊU CHÍ HOÀN THÀNH BẰNG CODE (COMPLETION SENSOR)
    print("\n[4] Tiêu chí hoàn thành (Completion Sensor):")
    flight_tools.reset_mock_db()

    # Test 4.1: Kiểm tra mã vé ảo không tồn tại -> PHẢI BÁO THẤT BẠI
    success_fake, msg_fake = CompletionSensor.verify("BK_KHONG_TON_TAI", constraint)
    print(f"    - Kiểm tra mã vé rác: Thành công = {success_fake} | Chi tiết: {msg_fake}")
    assert success_fake is False, "LỖI: Sensor chấp nhận mã vé không có thật!"

    # Test 4.2: Đặt vé thật và kiểm chứng
    book_res = flight_tools.book_ticket.invoke({
        "flight_id": "QH118",
        "seat_number": "05D",
        "passenger_name": "Nguyen Van A",
        "baggage_kg": 15
    })
    book_data = json.loads(book_res)
    real_code = book_data["booking_code"]

    success_real, msg_real = CompletionSensor.verify(real_code, constraint)
    print(f"    - Kiểm tra vé QH118 đã đặt: Thành công = {success_real} | Chi tiết: {msg_real}")
    assert success_real is True, f"LỖI: Vé hợp lệ nhưng sensor không công nhận! ({msg_real})"

    # 5. KIỂM THỬ LỚP BÀN GIAO (HANDOFF)
    print("\n[5] Lớp Bàn giao (Handoff Report):")
    report = HandoffReport(
        status="KIỂM THỬ BÀN GIAO",
        current_stage="Kiểm thử đơn vị",
        actions_taken=[{"tool": "search_flights", "args": {"origin": "SGN"}}],
        failed_attempts=["Đã thử chuyến bay nhưng không khớp"],
        specific_question="Bạn có muốn tăng ngân sách để tiếp tục tìm kiếm không?"
    )
    terminal_output = report.format_terminal()
    print("    - Định dạng xuất terminal hợp lệ:")
    print(terminal_output)
    assert "BÁO CÁO BÀN GIAO" in terminal_output

    print("\n==================================================")
    print(">>> TẤT CẢ CÁC LỚP BẢO VỆ ĐÃ VƯỢT QUA KIỂM THỬ (100% PASS) <<<")
    print("==================================================")


if __name__ == "__main__":
    test_all()
