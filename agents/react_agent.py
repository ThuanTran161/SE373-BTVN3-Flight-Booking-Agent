import json
from typing import Dict, Any, List
from harness.constraints import BookingConstraint
from harness.permission import PermissionGuard
from harness.loop_detector import LoopDetector
from harness.completion_sensor import CompletionSensor
from harness.handoff import HandoffReport
from tools import flight_tools


class ReActAgent:
    def __init__(self, constraints: BookingConstraint, max_turns: int = 10, enable_guard: bool = True):
        self.constraints = constraints
        self.max_turns = max_turns
        self.enable_guard = enable_guard
        self.permission_guard = PermissionGuard(price_limit=constraints.max_price)
        self.loop_detector = LoopDetector()

    def run(self) -> Dict[str, Any]:
        history: List[Dict[str, Any]] = []
        turn = 0
        booking_code = None
        context_meta = {}
        last_found_flights = []

        while turn < self.max_turns:
            turn += 1
            thought, action, args = self._step_policy(turn, history, last_found_flights, booking_code)

            if action == "FINISH":
                success, reason = CompletionSensor.verify(booking_code, self.constraints)
                if success:
                    return {"status": "SUCCESS", "booking_code": booking_code, "turns": turn, "trace": history}
                return {"status": "SENSOR_FAILED", "reason": reason, "turns": turn}

            # Harness Kiểm quyền
            if self.enable_guard:
                allowed, msg = self.permission_guard.check_permission(action, args, context_meta)
                if not allowed:
                    report = HandoffReport(
                        status="CẦN PHÊ DUYỆT",
                        current_stage=f"Vòng {turn} tại tool '{action}'",
                        actions_taken=history,
                        failed_attempts=[],
                        specific_question=f"{msg} Bạn có đồng ý thực thi không?"
                    )
                    return {"status": "WAIT_APPROVAL", "report": report, "turns": turn}

            # Harness Kiểm tra lặp
            loop_res = self.loop_detector.check(action, args, progress_metric=len(history))
            if loop_res == "LOOP":
                report = HandoffReport(
                    status="PHÁT HIỆN LẶP (LOOP)",
                    current_stage=f"Vòng {turn}",
                    actions_taken=history,
                    failed_attempts=[f"Lặp lại hành vi {action} với {args}"],
                    specific_question="Agent đang lặp vô ích. Bạn muốn can thiệp chọn chuyến nào?"
                )
                return {"status": "ABORT_LOOP", "report": report, "turns": turn}

            # Gọi Tool qua chuẩn LangChain invoke
            fn = getattr(flight_tools, action)
            obs_raw = fn.invoke(args)
            obs = json.loads(obs_raw)

            if action == "search_flights" and obs.get("status") == "success":
                last_found_flights = obs.get("flights", [])
            elif action == "check_seat" and obs.get("status") == "success":
                context_meta["current_price"] = obs.get("price")
                context_meta["refundable"] = obs.get("refundable")
            elif action == "book_seat" and obs.get("status") == "held":
                booking_code = obs.get("booking_code")

            history.append({"turn": turn, "thought": thought, "action": action, "args": args, "obs": obs})

        report = HandoffReport(
            status="HẾT NGÂN SÁCH LƯỢT GỌI",
            current_stage=f"Đã chạm trần {self.max_turns} vòng",
            actions_taken=history,
            failed_attempts=["Chưa hoàn tất trong ngân sách cho phép"],
            specific_question="Cần can thiệp người dùng."
        )
        return {"status": "OUT_OF_BUDGET", "report": report, "turns": turn}

    def _step_policy(self, turn: int, history: List, flights: List, booking_code: str):
        if not history:
            return ("Chưa có thông tin chuyến bay, cần tìm kiếm.", "search_flights",
                    {"origin": self.constraints.origin, "dest": self.constraints.dest, "date": self.constraints.date})

        last = history[-1]
        if last["action"] == "search_flights":
            valid = [f for f in flights if
                     f["price"] <= self.constraints.max_price and f["dep_time"] <= self.constraints.depart_before]
            target = valid[0] if valid else flights[0]
            return (f"Chọn chuyến {target['flight_id']} để kiểm tra ghế.", "check_seat",
                    {"flight_id": target["flight_id"]})

        if last["action"] == "check_seat":
            if last["obs"].get("available_seats"):
                seat = last["obs"]["available_seats"][0]
                flight_id = last["obs"]["flight_id"]
                return (f"Ghế {seat} còn trống, tiến hành đặt.", "book_seat",
                        {"flight_id": flight_id, "seat_number": seat})
            return ("Hết ghế, cần tìm chuyến khác.", "search_flights",
                    {"origin": self.constraints.origin, "dest": self.constraints.dest, "date": self.constraints.date})

        if last["action"] == "book_seat":
            if last["obs"].get("status") == "held":
                return ("Đã giữ chỗ, chuyển sang thanh toán.", "pay", {"booking_code": booking_code})
            return ("Đặt chỗ thất bại, thử lại.", "search_flights",
                    {"origin": self.constraints.origin, "dest": self.constraints.dest, "date": self.constraints.date})

        if last["action"] == "pay":
            return ("Đã thanh toán thành công, kết thúc.", "FINISH", {})

        return ("Hoàn tất.", "FINISH", {})