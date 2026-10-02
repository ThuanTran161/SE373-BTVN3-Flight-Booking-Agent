import sys
import json

# Ensure UTF-8 output encoding for Windows terminal
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from harness.constraints import BookingConstraint
from tools.flight_tools import reset_mock_db
from agents.react_agent import ReActAgent
from agents.plan_execute_agent import PlanThenExecuteAgent
from agents.hybrid_agent import HybridAgent


def print_banner():
    print("=" * 70)
    print("      HỆ THỐNG ĐẶT VÉ MÁY BAY THÔNG MINH - AGENTIC AI (SE373)      ")
    print("                   (Agent = Model + Harness)                      ")
    print("=" * 70)


def main():
    print_banner()
    reset_mock_db()

    print("\n[CHỌN MẪU THIẾT KẾ AGENT]:")
    print("1. ReAct Agent (Thought -> Action -> Observation Loop)")
    print("2. Plan-then-Execute (LLM Planner -> Step Executor -> Re-planner)")
    print("3. Hybrid (Lai - High-level Coordinator + Micro ReAct Sub-agents)")

    choice = input("\nNhập lựa chọn của bạn (1/2/3, mặc định 1): ").strip() or "1"

    print("\n--- NHẬP THÔNG TIN RÀNG BUỘC ĐẶT VÉ ---")
    origin = input("Điểm khởi hành (VD: SGN): ").strip().upper() or "SGN"
    dest = input("Điểm đến (VD: DAD): ").strip().upper() or "DAD"
    date = input("Ngày bay (VD: 2026-10-07): ").strip() or "2026-10-07"
    budget_raw = input("Ngân sách tối đa (VND, VD: 2200000): ").strip() or "2200000"
    baggage_raw = input("Hành lý ký gửi bổ sung (kg, VD: 15): ").strip() or "15"
    passenger = input("Tên hành khách (VD: Tran Minh Thuan): ").strip() or "Tran Minh Thuan"

    constraints = BookingConstraint(
        origin=origin,
        dest=dest,
        date=date,
        max_price=int(budget_raw),
        depart_before="12:00",
        passenger_name=passenger,
        baggage_kg=int(baggage_raw)
    )

    print("\n" + "-" * 70)
    print("Thông số đã thiết lập:")
    print(constraints.to_natural_language())
    print("-" * 70)

    # Khởi tạo Agent tương ứng với cờ interactive=True
    if choice == "2":
        print("\n>>> Đang khởi chạy: Plan-then-Execute Agent...")
        agent = PlanThenExecuteAgent(constraints=constraints, enable_guard=True, interactive=True)
    elif choice == "3":
        print("\n>>> Đang khởi chạy: Hybrid Agent (Lai)...")
        agent = HybridAgent(constraints=constraints, enable_guard=True, interactive=True)
    else:
        print("\n>>> Đang khởi chạy: ReAct Agent...")
        agent = ReActAgent(constraints=constraints, enable_guard=True, interactive=True)

    try:
        res = agent.run()
    except Exception as e:
        print(f"\n[LỖI THỰC THI]: {e}")
        return

    print("\n" + "=" * 70)
    print(f"KẾT QUẢ THỰC THI: {res.get('status')}")
    print(f"Tổng số vòng tương tác (Turns): {res.get('turns')}")
    print("=" * 70)

    if "report" in res:
        print(res["report"].format_terminal())
    elif res.get("status") == "SUCCESS":
        print(f"\n CHÚC MỪNG! ĐÃ ĐẶT VÉ THÀNH CÔNG!")
        print(f" Mã đặt chỗ (Booking Code): {res.get('booking_code')}")
        print(f" Chi tiết kiểm chứng độc lập: {res.get('reason')}")
    else:
        print(f"\n[!] Thất bại: {res.get('reason')}")

    # In tóm tắt Trace các bước
    trace = res.get("trace", [])
    if trace:
        print("\n--- NHẬT KÝ BƯỚC CHẠY (EXECUTION TRACE) ---")
        for i, step in enumerate(trace, 1):
            tool_name = step.get("action") or step.get("tool") or "UNKNOWN"
            thought = step.get("thought", "")
            if thought:
                print(f"Bước {i} [Thought]: {thought[:100]}...")
            print(f"Bước {i} [Action ]: {tool_name} -> Args: {step.get('args')}")


if __name__ == "__main__":
    main()
