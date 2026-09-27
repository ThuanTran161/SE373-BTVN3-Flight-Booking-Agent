from harness.constraints import BookingConstraint
from tools.flight_tools import reset_mock_db
from agents.react_agent import ReActAgent


def main():
    print(">>> KHỞI CHẠY KIỂM THỬ AGENT ĐẶT VÉ MÁY BAY <<<")
    reset_mock_db()

    constraints = BookingConstraint(
        origin="SGN", dest="DAD", date="2026-10-07",
        max_price=2000000, depart_before="12:00"
    )

    # Chạy ReAct có kích hoạt lớp kiểm quyền PermissionGuard
    agent = ReActAgent(constraints=constraints, enable_guard=True)
    res = agent.run()

    print(f"\nKết quả thực thi Agent: {res['status']}")
    if "report" in res:
        print(res["report"].format_terminal())
    else:
        print(f"Thành công! Mã vé: {res.get('booking_code')} trong {res.get('turns')} vòng.")


if __name__ == "__main__":
    main()