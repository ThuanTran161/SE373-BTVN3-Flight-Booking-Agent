from tabulate import tabulate
from harness.constraints import BookingConstraint
from tools.flight_tools import reset_mock_db, MOCK_FLIGHTS
from agents.react_agent import ReActAgent
from agents.plan_execute_agent import PlanThenExecuteAgent
from agents.hybrid_agent import HybridAgent


def run_benchmarks():
    constraints = BookingConstraint(
        origin="SGN", dest="DAD", date="2026-10-07",
        max_price=2000000, depart_before="12:00", require_refundable=False
    )

    scenarios = [
        {"name": "Kịch bản 1: Môi trường thuận lợi (Happy Path)", "setup": lambda: None},
        {"name": "Kịch bản 2: VN122 hết chỗ (Môi trường đổi)", "setup": lambda: MOCK_FLIGHTS[0].update({"seats": []})},
        {"name": "Kịch bản 3: Kiểm quyền Harness (Chặn hành động nhạy cảm)", "setup": lambda: None}
    ]

    results_table = []

    for sc in scenarios:
        reset_mock_db()
        sc["setup"]()
        guard_on = (sc["name"] == "Kịch bản 3: Kiểm quyền Harness (Chặn hành động nhạy cảm)")

        # 1. ReAct
        react = ReActAgent(constraints, enable_guard=guard_on)
        res_react = react.run()

        # 2. Plan-then-Execute
        reset_mock_db()
        sc["setup"]()
        plan_agent = PlanThenExecuteAgent(constraints)
        res_plan = plan_agent.run()

        # 3. Hybrid
        reset_mock_db()
        sc["setup"]()
        hybrid = HybridAgent(constraints)
        res_hybrid = hybrid.run()

        results_table.append([sc["name"], "ReAct", res_react["status"], res_react["turns"]])
        results_table.append(["", "Plan-then-Execute", res_plan["status"], res_plan["turns"]])
        results_table.append(["", "Hybrid (Lai)", res_hybrid["status"], res_hybrid["turns"]])
        results_table.append(["-" * 30, "-" * 18, "-" * 16, "-" * 6])

    headers = ["Kịch bản kiểm thử", "Mẫu thiết kế", "Kết quả thực thi", "Số vòng (Turns)"]
    print("\n" + "=" * 80)
    print("KẾT QUẢ ĐÁNH GIÁ THỰC NGHIỆM 3 MẪU THIẾT KẾ AGENT (SE373)")
    print("=" * 80)
    print(tabulate(results_table, headers=headers))


if __name__ == "__main__":
    run_benchmarks()