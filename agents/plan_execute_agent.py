import json
from typing import Dict, Any, List
from harness.constraints import BookingConstraint
from harness.completion_sensor import CompletionSensor
from tools import flight_tools

class PlanThenExecuteAgent:
    def __init__(self, constraints: BookingConstraint):
        self.constraints = constraints

    def generate_static_plan(self) -> List[Dict[str, Any]]:
        return [
            {"step": 1, "tool": "search_flights", "args": {"origin": self.constraints.origin, "dest": self.constraints.dest, "date": self.constraints.date}},
            {"step": 2, "tool": "check_seat", "args": {"flight_id": "VN122"}},
            {"step": 3, "tool": "book_seat", "args": {"flight_id": "VN122", "seat_number": "12A"}},
            {"step": 4, "tool": "pay", "args": {"booking_code": "BK_VN122_12A"}},
        ]

    def run(self) -> Dict[str, Any]:
        plan = self.generate_static_plan()
        trace = []
        booking_code = None

        for item in plan:
            tool_name = item["tool"]
            args = item["args"]
            fn = getattr(flight_tools, tool_name)
            obs_raw = fn.invoke(args)
            obs = json.loads(obs_raw)
            trace.append({"step": item["step"], "tool": tool_name, "args": args, "obs": obs})

            if obs.get("status") in ["failed", "not_found"] or (tool_name == "check_seat" and not obs.get("available_seats")):
                return {
                    "status": "PLAN_BROKEN",
                    "failed_step": item["step"],
                    "reason": f"Kế hoạch gãy tại bước {tool_name} do dữ liệu thực tế thay đổi.",
                    "trace": trace,
                    "turns": len(trace)
                }

            if tool_name == "book_seat" and obs.get("status") == "held":
                booking_code = obs.get("booking_code")

        success, msg = CompletionSensor.verify(booking_code, self.constraints)
        return {
            "status": "SUCCESS" if success else "SENSOR_FAILED",
            "reason": msg,
            "trace": trace,
            "turns": len(trace)
        }