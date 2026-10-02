import json
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from harness.constraints import BookingConstraint
from harness.permission import PermissionGuard
from harness.loop_detector import LoopDetector
from harness.completion_sensor import CompletionSensor
from harness.handoff import HandoffReport
from tools.flight_tools import AGENT_TOOLS
from config import get_model


class HybridAgent:

    def __init__(
        self,
        constraints: BookingConstraint,
        max_turns: int = 12,
        enable_guard: bool = True,
        auto_approve: bool = False,
        interactive: bool = False
    ):
        self.constraints = constraints
        self.max_turns = max_turns
        self.enable_guard = enable_guard
        self.auto_approve = auto_approve
        self.interactive = interactive

        self.permission_guard = PermissionGuard(
            price_limit=constraints.max_price,
            auto_approve=auto_approve
        )
        self.loop_detector = LoopDetector(repeat_k=2)

        self.tools = AGENT_TOOLS
        self.tool_map = {t.name: t for t in self.tools}

        base_model = get_model(temperature=0.0)
        self.model = base_model.bind_tools(self.tools)

    def _run_sub_goal(
        self,
        sub_goal_name: str,
        goal_instructions: str,
        shared_state: Dict[str, Any],
        history: List[Dict[str, Any]],
        current_turns: int
    ) -> Dict[str, Any]:
        """Thực thi một chặng bằng ReAct cục bộ."""
        prompt = (
            f"Bạn là Sub-Agent chuyên trách chặng: [{sub_goal_name}].\n"
            f"Ràng buộc gốc:\n{self.constraints.to_natural_language()}\n\n"
            f"Trạng thái đã thu thập được từ các chặng trước:\n{json.dumps(shared_state, ensure_ascii=False, indent=2)}\n\n"
            f"Nhiệm vụ cụ thể của chặng này: {goal_instructions}\n"
            "Hãy suy luận và sử dụng các công cụ cần thiết để hoàn thành nhiệm vụ của chặng."
        )

        messages = [
            SystemMessage(content="Bạn là một ReAct Sub-Agent tự chủ, chịu trách nhiệm giải quyết trọn vẹn mục tiêu của chặng."),
            HumanMessage(content=prompt)
        ]

        sub_turns = 0
        while sub_turns < 4 and current_turns + sub_turns < self.max_turns:
            sub_turns += 1
            ai_msg = self.model.invoke(messages)
            messages.append(ai_msg)

            if not ai_msg.tool_calls:
                break

            for tc in ai_msg.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                call_id = tc.get("id", f"call_sub_{sub_turns}")

                # Harness 1: Kiểm lặp
                loop_res = self.loop_detector.check(tool_name, tool_args, progress_metric=len(history))
                if loop_res == "LOOP":
                    return {"status": "LOOP", "turns": sub_turns, "tool": tool_name, "args": tool_args}

                # Harness 2: Kiểm quyền
                if self.enable_guard:
                    allowed, guard_msg = self.permission_guard.check_permission(tool_name, tool_args, shared_state)
                    if not allowed:
                        if self.interactive:
                            approved = self.permission_guard.request_approval_interactive(guard_msg)
                            if not approved:
                                return {"status": "REJECTED_BY_USER", "turns": sub_turns, "guard_msg": guard_msg}
                        else:
                            return {"status": "WAIT_APPROVAL", "turns": sub_turns, "guard_msg": guard_msg}

                # Thực thi tool
                fn = self.tool_map.get(tool_name)
                try:
                    obs_str = fn.invoke(tool_args)
                    obs = json.loads(obs_str)
                except Exception as e:
                    obs_str = json.dumps({"status": "error", "message": str(e)})
                    obs = {"status": "error", "message": str(e)}

                # Ghi nhận trạng thái chia sẻ
                if tool_name == "search_flights" and obs.get("status") == "success":
                    shared_state["found_flights"] = obs.get("flights", [])
                elif tool_name == "check_seat_availability" and obs.get("status") == "success":
                    shared_state["selected_flight_id"] = obs.get("flight_id")
                    shared_state["current_price"] = obs.get("base_price", 0)
                    shared_state["refundable"] = obs.get("refundable", True)
                    shared_state["available_seats"] = obs.get("available_seats", [])
                elif tool_name == "calculate_baggage_fee" and obs.get("status") == "success":
                    shared_state["baggage_fee"] = obs.get("baggage_fee", 0)
                elif tool_name == "book_ticket" and obs.get("status") == "success":
                    shared_state["booking_code"] = obs.get("booking_code")

                history.append({
                    "sub_goal": sub_goal_name,
                    "thought": ai_msg.content,
                    "action": tool_name,
                    "args": tool_args,
                    "obs": obs
                })
                messages.append(ToolMessage(content=obs_str, tool_call_id=call_id))

        return {"status": "DONE", "turns": sub_turns}

    def run(self) -> Dict[str, Any]:
        trace: List[Dict[str, Any]] = []
        shared_state: Dict[str, Any] = {}
        total_turns = 0

        # Định nghĩa 3 chặng chiến lược cấp cao (Milestones)
        milestones = [
            {
                "name": "Chặng 1: Tìm kiếm & Khám phá Chuyến bay",
                "instructions": (
                    f"Gọi tool 'search_flights' để tìm tất cả các chuyến từ {self.constraints.origin} "
                    f"đến {self.constraints.dest} ngày {self.constraints.date}."
                )
            },
            {
                "name": "Chặng 2: Xác minh Ghế trống & Hành lý",
                "instructions": (
                    "Chọn chuyến bay tối ưu nhất thỏa mãn giờ bay và giá vé. "
                    "Gọi 'check_seat_availability' để kiểm tra ghế trống. "
                    + (f"Sau đó gọi 'calculate_baggage_fee' cho {self.constraints.baggage_kg} kg hành lý."
                       if self.constraints.baggage_kg > 0 else "")
                )
            },
            {
                "name": "Chặng 3: Chốt Đặt vé & Xuất Mã Đặt chỗ",
                "instructions": (
                    f"Sử dụng tool 'book_ticket' để đặt vé cho hành khách {self.constraints.passenger_name} "
                    f"với số ghế còn trống và hành lý đã xác minh."
                )
            }
        ]

        for m in milestones:
            res = self._run_sub_goal(
                sub_goal_name=m["name"],
                goal_instructions=m["instructions"],
                shared_state=shared_state,
                history=trace,
                current_turns=total_turns
            )
            total_turns += res.get("turns", 1)

            if res.get("status") == "LOOP":
                report = HandoffReport(
                    status="PHÁT HIỆN LẶP (LOOP_DETECTED)",
                    current_stage=m["name"],
                    actions_taken=trace,
                    failed_attempts=[f"Lặp công cụ {res.get('tool')} với {res.get('args')}"],
                    specific_question="ReAct Sub-agent phát hiện vòng lặp. Bàn giao cho nhân viên xử lý."
                )
                return {"status": "ABORT_LOOP", "report": report, "turns": total_turns, "trace": trace}

            if res.get("status") == "WAIT_APPROVAL":
                report = HandoffReport(
                    status="CẦN PHÊ DUYỆT (WAIT_APPROVAL)",
                    current_stage=m["name"],
                    actions_taken=trace,
                    failed_attempts=[],
                    specific_question=f"{res.get('guard_msg')} Bạn có đồng ý thực thi không?"
                )
                return {"status": "WAIT_APPROVAL", "report": report, "turns": total_turns, "trace": trace}

            if res.get("status") == "REJECTED_BY_USER":
                report = HandoffReport(
                    status="TỪ CHỐI BỞI NGƯỜI DÙNG (REJECTED)",
                    current_stage=m["name"],
                    actions_taken=trace,
                    failed_attempts=["Người dùng từ chối cấp quyền."],
                    specific_question="Đã dừng đặt vé an toàn theo ý muốn người dùng."
                )
                return {"status": "REJECTED_BY_USER", "report": report, "turns": total_turns, "trace": trace}

            if total_turns >= self.max_turns:
                report = HandoffReport(
                    status="HẾT LƯỢT GỌI (OUT_OF_BUDGET)",
                    current_stage=f"Chạm trần {self.max_turns} vòng",
                    actions_taken=trace,
                    failed_attempts=["Quá số lượt thực thi mà chưa hoàn thành."],
                    specific_question="Cần can thiệp người dùng."
                )
                return {"status": "OUT_OF_BUDGET", "report": report, "turns": total_turns, "trace": trace}

        booking_code = shared_state.get("booking_code")
        success, reason = CompletionSensor.verify(booking_code, self.constraints)
        return {
            "status": "SUCCESS" if success else "SENSOR_FAILED",
            "booking_code": booking_code,
            "turns": total_turns,
            "trace": trace,
            "reason": reason
        }
