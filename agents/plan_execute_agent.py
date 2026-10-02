import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import SystemMessage, HumanMessage
from harness.constraints import BookingConstraint
from harness.permission import PermissionGuard
from harness.loop_detector import LoopDetector
from harness.completion_sensor import CompletionSensor
from harness.handoff import HandoffReport
from tools.flight_tools import AGENT_TOOLS
from config import get_model


class PlanStep(BaseModel):
    step_id: int = Field(description="Số thứ tự bước")
    tool_name: str = Field(description="Tên tool cần gọi (search_flights, check_seat_availability, calculate_baggage_fee, book_ticket)")
    purpose: str = Field(description="Mục tiêu của bước này")


class ExecutionPlan(BaseModel):
    plan_summary: str = Field(description="Tóm tắt kế hoạch tổng thể")
    steps: List[PlanStep] = Field(description="Danh sách các bước thực hiện tuần tự")


class PlanThenExecuteAgent:


    def __init__(
        self,
        constraints: BookingConstraint,
        max_replan: int = 3,
        enable_guard: bool = True,
        auto_approve: bool = False,
        interactive: bool = False
    ):
        self.constraints = constraints
        self.max_replan = max_replan
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

        self.planner_model = get_model(temperature=0.0)
        self.executor_model = get_model(temperature=0.0).bind_tools(self.tools)

    def _generate_initial_plan(self) -> ExecutionPlan:
        """Sử dụng LLM để sinh kế hoạch ban đầu."""
        planner_prompt = (
            "Bạn là Flight Planner AI. Hãy lập một kế hoạch thực thi tuần tự gồm các bước để đặt vé máy bay.\n"
            "Các tool khả dụng:\n"
            "- search_flights: tìm chuyến bay theo điểm đi, điểm đến, ngày bay.\n"
            "- check_seat_availability: kiểm tra ghế trống và giá vé của chuyến bay.\n"
            "- calculate_baggage_fee: tính phí hành lý ký gửi nếu khách yêu cầu hành lý.\n"
            "- book_ticket: chốt đặt vé cuối cùng.\n\n"
            f"Ràng buộc của khách hàng:\n{self.constraints.to_natural_language()}\n\n"
            "Hãy trả về kế hoạch dạng JSON chuẩn khớp với schema sau:\n"
            "{\n"
            '  "plan_summary": "Tóm tắt...",\n'
            '  "steps": [\n'
            '    {"step_id": 1, "tool_name": "search_flights", "purpose": "..."},\n'
            '    {"step_id": 2, "tool_name": "check_seat_availability", "purpose": "..."},\n'
            '    ...\n'
            "  ]\n"
            "}\n"
            "Chỉ trả về JSON thuần túy, không kèm giải thích bên ngoài."
        )

        resp = self.planner_model.invoke([HumanMessage(content=planner_prompt)])
        cleaned = resp.content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        try:
            plan_data = json.loads(cleaned)
            return ExecutionPlan(**plan_data)
        except Exception:
            # Fallback plan nếu model không trả đúng định dạng JSON
            steps = [
                PlanStep(step_id=1, tool_name="search_flights", purpose=f"Tìm chuyến {self.constraints.origin}->{self.constraints.dest}"),
                PlanStep(step_id=2, tool_name="check_seat_availability", purpose="Kiểm tra ghế trống chuyến bay phù hợp"),
            ]
            if self.constraints.baggage_kg > 0:
                steps.append(PlanStep(step_id=3, tool_name="calculate_baggage_fee", purpose="Tính cước hành lý ký gửi"))
            steps.append(PlanStep(step_id=len(steps) + 1, tool_name="book_ticket", purpose="Chốt đặt vé"))
            return ExecutionPlan(plan_summary="Kế hoạch đặt vé máy bay", steps=steps)

    def _replan(self, current_trace: List[Dict[str, Any]], failed_reason: str) -> ExecutionPlan:
        """Sử dụng LLM Re-planner để điều chỉnh lại kế hoạch khi gặp sự cố."""
        replan_prompt = (
            "Bạn là Flight Re-Planner AI. Kế hoạch trước đó gặp trở ngại:\n"
            f"Lý do: {failed_reason}\n"
            f"Lịch sử thực thi trước đó:\n{json.dumps(current_trace, ensure_ascii=False, indent=2)}\n\n"
            f"Ràng buộc ban đầu:\n{self.constraints.to_natural_language()}\n\n"
            "Hãy đề xuất kế hoạch mới cho các bước còn lại để hoàn thành mục tiêu (ví dụ: kiểm tra chuyến bay khác còn chỗ).\n"
            "Trả về JSON định dạng y hệt kế hoạch ban đầu (plan_summary và danh sách steps)."
        )
        resp = self.planner_model.invoke([HumanMessage(content=replan_prompt)])
        cleaned = resp.content.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()

        try:
            plan_data = json.loads(cleaned)
            return ExecutionPlan(**plan_data)
        except Exception:
            return ExecutionPlan(
                plan_summary="Kế hoạch thử chuyến bay khác",
                steps=[
                    PlanStep(step_id=1, tool_name="check_seat_availability", purpose="Thử kiểm tra chuyến bay dự phòng"),
                    PlanStep(step_id=2, tool_name="book_ticket", purpose="Chốt vé chuyến dự phòng")
                ]
            )

    def run(self) -> Dict[str, Any]:
        trace: List[Dict[str, Any]] = []
        booking_code = None
        replan_count = 0
        total_turns = 0
        context_meta: Dict[str, Any] = {}

        # 1. Sinh kế hoạch ban đầu
        current_plan = self._generate_initial_plan()

        while replan_count <= self.max_replan:
            step_idx = 0
            while step_idx < len(current_plan.steps):
                step = current_plan.steps[step_idx]
                total_turns += 1

                # Executor: Dùng LLM quyết định tham số chính xác cho bước hiện tại dựa trên toàn bộ trace
                exec_prompt = (
                    "Bạn là Step Executor AI.\n"
                    f"Ràng buộc gốc của khách hàng:\n{self.constraints.to_natural_language()}\n"
                    f"Bước hiện tại cần làm: [{step.tool_name}] - {step.purpose}\n"
                    f"Lịch sử thực thi và kết quả các bước trước:\n{json.dumps(trace, ensure_ascii=False, indent=2)}\n\n"
                    f"Hãy gọi đúng tool '{step.tool_name}' với các tham số chính xác nhất dựa trên kết quả đã quan sát được."
                )

                exec_resp = self.executor_model.invoke([HumanMessage(content=exec_prompt)])

                if not exec_resp.tool_calls:
                    # Model không sinh tool call -> fallback tham số cơ bản
                    if step.tool_name == "search_flights":
                        tool_args = {"origin": self.constraints.origin, "dest": self.constraints.dest, "date": self.constraints.date}
                    elif step.tool_name == "calculate_baggage_fee":
                        tool_args = {"flight_id": context_meta.get("flight_id", "QH118"), "baggage_kg": self.constraints.baggage_kg}
                    else:
                        tool_args = {}
                else:
                    tc = exec_resp.tool_calls[0]
                    tool_args = tc["args"]

                # --- HARNESS 1: Kiểm tra Lặp (Loop Detector) ---
                loop_res = self.loop_detector.check(step.tool_name, tool_args, progress_metric=len(trace))
                if loop_res == "LOOP":
                    report = HandoffReport(
                        status="PHÁT HIỆN LẶP (LOOP_DETECTED)",
                        current_stage=f"Bước '{step.tool_name}' trong kế hoạch",
                        actions_taken=trace,
                        failed_attempts=[f"Lặp tool '{step.tool_name}' với tham số: {tool_args}"],
                        specific_question="Agent đang lặp lại bước này. Chuyển sang con người can thiệp."
                    )
                    return {
                        "status": "ABORT_LOOP",
                        "report": report,
                        "turns": total_turns,
                        "trace": trace,
                        "booking_code": booking_code
                    }

                # --- HARNESS 2: Kiểm quyền (Permission Guard) ---
                if self.enable_guard:
                    allowed, guard_msg = self.permission_guard.check_permission(step.tool_name, tool_args, context_meta)
                    if not allowed:
                        if self.interactive:
                            approved = self.permission_guard.request_approval_interactive(guard_msg)
                            if not approved:
                                report = HandoffReport(
                                    status="TỪ CHỐI BỞI NGƯỜI DÙNG (REJECTED)",
                                    current_stage=f"Tại bước '{step.tool_name}'",
                                    actions_taken=trace,
                                    failed_attempts=[f"Người dùng từ chối cấp quyền: {guard_msg}"],
                                    specific_question="Thao tác dừng lại an toàn theo chỉ định người dùng."
                                )
                                return {
                                    "status": "REJECTED_BY_USER",
                                    "report": report,
                                    "turns": total_turns,
                                    "trace": trace,
                                    "booking_code": booking_code
                                }
                        else:
                            report = HandoffReport(
                                status="CẦN PHÊ DUYỆT (WAIT_APPROVAL)",
                                current_stage=f"Tại bước nhạy cảm '{step.tool_name}'",
                                actions_taken=trace,
                                failed_attempts=[],
                                specific_question=f"{guard_msg} Bạn có đồng ý thực thi không?"
                            )
                            return {
                                "status": "WAIT_APPROVAL",
                                "report": report,
                                "turns": total_turns,
                                "trace": trace,
                                "booking_code": booking_code
                            }

                # Thực thi Tool
                tool_fn = self.tool_map.get(step.tool_name)
                if not tool_fn:
                    obs = {"status": "error", "message": f"Không tìm thấy tool {step.tool_name}"}
                else:
                    try:
                        raw_obs = tool_fn.invoke(tool_args)
                        obs = json.loads(raw_obs)
                    except Exception as e:
                        obs = {"status": "error", "message": str(e)}

                step_record = {
                    "step_id": step.step_id,
                    "tool": step.tool_name,
                    "args": tool_args,
                    "obs": obs
                }
                trace.append(step_record)

                # Cập nhật context_meta
                if step.tool_name == "check_seat_availability" and obs.get("status") == "success":
                    context_meta["flight_id"] = obs.get("flight_id")
                    context_meta["current_price"] = obs.get("base_price", 0)
                    context_meta["refundable"] = obs.get("refundable", True)
                elif step.tool_name == "book_ticket" and obs.get("status") == "success":
                    booking_code = obs.get("booking_code")

                # Kiểm tra xem bước thực hiện có bị lỗi/gãy kế hoạch không để kích hoạt Re-planner
                needs_replan = False
                fail_reason = ""
                if obs.get("status") in ["failed", "not_found", "empty", "error"]:
                    needs_replan = True
                    fail_reason = f"Tool {step.tool_name} trả về trạng thái thất bại: {obs.get('message') or obs.get('reason')}"
                elif step.tool_name == "check_seat_availability" and not obs.get("available_seats"):
                    needs_replan = True
                    fail_reason = f"Chuyến bay {obs.get('flight_id')} đã hết ghế trống."
                elif step.tool_name == "check_seat_availability" and obs.get("base_price", 0) > self.constraints.max_price:
                    needs_replan = True
                    fail_reason = f"Giá vé cơ bản ({obs.get('base_price'):,.0f} VND) đã vượt trần ngân sách ({self.constraints.max_price:,.0f} VND)."

                if needs_replan:
                    replan_count += 1
                    if replan_count > self.max_replan:
                        report = HandoffReport(
                            status="VƯỢT QUÁ SỐ LẦN TÁI LẬP KẾ HOẠCH (MAX_REPLAN)",
                            current_stage=f"Tại bước {step.tool_name}",
                            actions_taken=trace,
                            failed_attempts=[fail_reason],
                            specific_question="Kế hoạch bị gãy nhiều lần do môi trường thay đổi. Chuyển sang con người."
                        )
                        return {
                            "status": "PLAN_BROKEN",
                            "report": report,
                            "turns": total_turns,
                            "trace": trace,
                            "booking_code": booking_code
                        }

                    # LLM Re-planning
                    current_plan = self._replan(trace, fail_reason)
                    break  # thoát vòng lặp step để chạy theo plan mới

                step_idx += 1

            if booking_code:
                break

        # --- HARNESS 3: Tiêu chí hoàn thành kiểm bằng code (Completion Sensor) ---
        success, reason = CompletionSensor.verify(booking_code, self.constraints)
        return {
            "status": "SUCCESS" if success else "SENSOR_FAILED",
            "reason": reason,
            "booking_code": booking_code,
            "turns": total_turns,
            "trace": trace
        }
