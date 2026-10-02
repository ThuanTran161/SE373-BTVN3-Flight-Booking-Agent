import sys
import time
from typing import Dict, Any, List

# Ensure UTF-8 output encoding for Windows terminal
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from tabulate import tabulate
from harness.constraints import BookingConstraint
from tools.flight_tools import reset_mock_db, set_flight_seats
from agents.react_agent import ReActAgent
from agents.plan_execute_agent import PlanThenExecuteAgent
from agents.hybrid_agent import HybridAgent


def run_benchmarks():
    print("=" * 85)
    print("   BẮT ĐẦU CHƯƠNG TRÌNH ĐÁNH GIÁ THỰC NGHIỆM 3 MẪU THIẾT KẾ AGENT (SE373)")
    print("=" * 85)

    base_constraints = BookingConstraint(
        origin="SGN",
        dest="DAD",
        date="2026-10-07",
        max_price=2300000,
        depart_before="12:00",
        passenger_name="Nguyen Van A",
        baggage_kg=15,
        require_refundable=False
    )

    scenarios = [
        {
            "name": "Kịch bản 1: Môi trường thuận lợi (Happy Path)",
            "description": "Đặt vé SGN-DAD, kèm 15kg hành lý, ngân sách 2.3tr. Mọi chuyến đều còn ghế.",
            "setup": lambda: None,
            "auto_approve": True
        },
        {
            "name": "Kịch bản 2: Biến động ghế (Dynamic Environment)",
            "description": "Chuyến giá tốt QH118 bị hết ghế đột ngột, Agent phải thích ứng chọn chuyến VN122.",
            "setup": lambda: set_flight_seats("QH118", []),
            "auto_approve": True
        },
        {
            "name": "Kịch bản 3: Kích hoạt Kiểm quyền Harness (Permission Guard)",
            "description": "Chạy với auto_approve=False để kiểm tra bắt chặn hành động đặt vé nhạy cảm.",
            "setup": lambda: None,
            "auto_approve": False
        }
    ]

    results_table = []

    for sc_idx, sc in enumerate(scenarios, 1):
        print(f"\n>>> Đang chạy {sc['name']}...")
        print(f"    Mô tả: {sc['description']}")

        # Danh sách 3 Agent cần so sánh
        agent_factories = [
            ("ReAct Agent", lambda c, aa: ReActAgent(c, auto_approve=aa, enable_guard=True)),
            ("Plan-then-Execute", lambda c, aa: PlanThenExecuteAgent(c, auto_approve=aa, enable_guard=True)),
            ("Hybrid (Lai)", lambda c, aa: HybridAgent(c, auto_approve=aa, enable_guard=True))
        ]

        for idx, (agent_name, factory) in enumerate(agent_factories):
            # Công bằng tuyệt đối: Luôn reset Mock DB và áp dụng setup kịch bản trước mỗi lần chạy
            reset_mock_db()
            sc["setup"]()

            start_time = time.time()
            try:
                agent = factory(base_constraints, sc["auto_approve"])
                res = agent.run()
                elapsed = time.time() - start_time
                status = res.get("status", "UNKNOWN")
                turns = res.get("turns", 0)
                booking_code = res.get("booking_code") or "-"
                verified = "ĐẠT (PASS)" if status == "SUCCESS" else ("CHẶN AN TOÀN" if status == "WAIT_APPROVAL" else "CHƯA ĐẠT")
            except Exception as e:
                elapsed = time.time() - start_time
                status = f"ERROR: {type(e).__name__}"
                turns = 0
                booking_code = "-"
                verified = "LỖI HỆ THỐNG"
                print(f"    [!] Lỗi khi chạy {agent_name}: {e}")

            sc_label = sc["name"] if idx == 0 else ""
            results_table.append([
                sc_label,
                agent_name,
                status,
                turns,
                f"{elapsed:.2f}s",
                booking_code,
                verified
            ])

        results_table.append(["-" * 28, "-" * 18, "-" * 15, "-" * 6, "-" * 7, "-" * 15, "-" * 14])

    headers = [
        "Kịch bản kiểm thử",
        "Mẫu thiết kế Agent",
        "Trạng thái thực thi",
        "Số vòng",
        "Thời gian",
        "Mã đặt chỗ",
        "Kiểm chứng Harness"
    ]

    print("\n" + "=" * 105)
    print("                      BẢNG TỔNG HỢP SO SÁNH THỰC NGHIỆM (BENCHMARK REPORT)")
    print("=" * 105)
    print(tabulate(results_table, headers=headers, tablefmt="grid"))
    print("\n[CHÚ THÍCH]:")
    print("- 'ĐẠT (PASS)': Vượt qua tiêu chí kiểm chứng bằng code độc lập của CompletionSensor.")
    print("- 'CHẶN AN TOÀN': Lớp PermissionGuard đã ngắt luồng thành công trước khi gọi tool nhạy cảm book_ticket.")
    print("- 'Số vòng (Turns)': Số lượt tương tác Tool & suy luận của Agent.")


if __name__ == "__main__":
    run_benchmarks()
