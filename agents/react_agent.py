import json
import sys
from typing import Dict, Any, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from harness.constraints import BookingConstraint
from harness.permission import PermissionGuard
from harness.loop_detector import LoopDetector
from harness.completion_sensor import CompletionSensor
from harness.handoff import HandoffReport
from tools.flight_tools import (
    search_flights,
    check_seat_availability,
    calculate_baggage_fee,
    book_ticket,
    AGENT_TOOLS
)
from config import get_model


class ReActAgent:


    def __init__(
        self,
        constraints: BookingConstraint,
        max_turns: int = 10,
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

        # Khởi tạo Chat Model từ cấu hình
        base_model = get_model(temperature=0.0)
        self.model = base_model.bind_tools(self.tools)

    def _build_system_prompt(self) -> str:
        return (
            "Bạn là Agent chuyên nghiệp hỗ trợ đặt vé máy bay tự động (ReAct Flight Booking Assistant).\n"
            "Mục tiêu của bạn là giúp khách hàng tìm kiếm, chọn chuyến bay, tính phí hành lý (nếu có) và chốt đặt vé hợp lệ.\n"
            "Quy trình tiêu chuẩn:\n"
            "1. Sử dụng tool 'search_flights' để tìm các chuyến bay theo ngày và chặng bay yêu cầu.\n"
            "2. Phân tích kết quả: kiểm tra giờ bay (dep_time), giá tiền cơ bản và chính sách hoàn hủy.\n"
            "3. Sử dụng 'check_seat_availability' để kiểm tra ghế trống cụ thể.\n"
            "4. Nếu có yêu cầu hành lý ký gửi (> 0 kg), gọi 'calculate_baggage_fee' để kiểm tra chi phí phụ trội.\n"
            "5. Đảm bảo tổng chi phí (giá vé + phí hành lý) <= ngân sách tối đa.\n"
            "6. Sử dụng 'book_ticket' để thực hiện đặt vé và nhận booking_code.\n"
            "Lưu ý: Nếu một chuyến bay hết ghế hoặc vượt ngân sách, hãy tự động suy luận để thử chuyến bay khả thi khác.\n"
            "Hãy luôn suy nghĩ kỹ lưỡng trước khi quyết định gọi công cụ."
        )

    def run(self) -> Dict[str, Any]:
        system_msg = SystemMessage(content=self._build_system_prompt())
        user_msg = HumanMessage(
            content=f"Yêu cầu đặt vé của tôi như sau:\n{self.constraints.to_natural_language()}\n"
                    "Hãy tìm và chốt đặt vé giúp tôi."
        )

        messages = [system_msg, user_msg]
        history: List[Dict[str, Any]] = []
        turn = 0
        booking_code = None
        context_meta: Dict[str, Any] = {}

        while turn < self.max_turns:
            turn += 1

            # 1. LLM Reasoning
            ai_msg = self.model.invoke(messages)
            thought = ai_msg.content or "Suy luận hành động kế tiếp..."
            messages.append(ai_msg)

            # Nếu không có tool calls nào được sinh ra -> Agent muốn kết thúc câu trả lời
            if not ai_msg.tool_calls:
                history.append({"turn": turn, "thought": thought, "action": "FINISH", "args": {}, "obs": "No further tool call"})
                break

            # 2. Xử lý từng tool call được sinh ra từ LLM
            for tc in ai_msg.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                call_id = tc.get("id", f"call_{turn}")

                # --- HARNESS 1: Kiểm tra Lặp (Loop Detector) ---
                loop_res = self.loop_detector.check(tool_name, tool_args, progress_metric=len(history))
                if loop_res == "LOOP":
                    report = HandoffReport(
                        status="PHÁT HIỆN LẶP (LOOP_DETECTED)",
                        current_stage=f"Vòng {turn} tại tool '{tool_name}'",
                        actions_taken=history,
                        failed_attempts=[f"Lặp lại hành vi {tool_name} với cùng tham số: {tool_args}"],
                        specific_question="Agent đang lặp vô ích. Cần con người can thiệp lựa chọn chuyến bay."
                    )
                    return {
                        "status": "ABORT_LOOP",
                        "report": report,
                        "turns": turn,
                        "trace": history,
                        "booking_code": booking_code
                    }

                # --- HARNESS 2: Kiểm quyền (Permission Guard) ---
                if self.enable_guard:
                    allowed, guard_msg = self.permission_guard.check_permission(tool_name, tool_args, context_meta)
                    if not allowed:
                        if self.interactive:
                            approved = self.permission_guard.request_approval_interactive(guard_msg)
                            if not approved:
                                report = HandoffReport(
                                    status="TỪ CHỐI BỞI NGƯỜI DÙNG (REJECTED)",
                                    current_stage=f"Vòng {turn} trước khi gọi '{tool_name}'",
                                    actions_taken=history,
                                    failed_attempts=[f"Người dùng từ chối cấp quyền: {guard_msg}"],
                                    specific_question="Hành động đã bị hủy an toàn theo ý muốn người dùng."
                                )
                                return {
                                    "status": "REJECTED_BY_USER",
                                    "report": report,
                                    "turns": turn,
                                    "trace": history,
                                    "booking_code": booking_code
                                }
                        else:
                            # Không phải interactive và không auto_approve -> Ngắt luồng yêu cầu phê duyệt
                            report = HandoffReport(
                                status="CẦN PHÊ DUYỆT (WAIT_APPROVAL)",
                                current_stage=f"Vòng {turn} tại tool '{tool_name}'",
                                actions_taken=history,
                                failed_attempts=[],
                                specific_question=f"{guard_msg} Bạn có đồng ý thực thi không?"
                            )
                            return {
                                "status": "WAIT_APPROVAL",
                                "report": report,
                                "turns": turn,
                                "trace": history,
                                "booking_code": booking_code
                            }

                # --- Thực thi Tool thực tế ---
                fn = self.tool_map.get(tool_name)
                if not fn:
                    obs_str = json.dumps({"status": "error", "message": f"Tool '{tool_name}' không tồn tại."})
                else:
                    try:
                        obs_str = fn.invoke(tool_args)
                    except Exception as e:
                        obs_str = json.dumps({"status": "error", "message": str(e)})

                try:
                    obs = json.loads(obs_str)
                except Exception:
                    obs = {"raw_output": obs_str}

                # Cập nhật context_meta phục vụ Harness
                if tool_name == "check_seat_availability" and obs.get("status") == "success":
                    context_meta["current_price"] = obs.get("base_price", 0)
                    context_meta["refundable"] = obs.get("refundable", True)
                elif tool_name == "book_ticket" and obs.get("status") == "success":
                    booking_code = obs.get("booking_code")

                # Lưu vào trace & messages
                history.append({
                    "turn": turn,
                    "thought": thought,
                    "action": tool_name,
                    "args": tool_args,
                    "obs": obs
                })
                messages.append(ToolMessage(content=obs_str, tool_call_id=call_id))

            # Nếu đã book_ticket thành công, tiếp tục để model xác nhận hoặc break
            if booking_code:
                break

        # --- HARNESS 3: Tiêu chí hoàn thành kiểm bằng code (Completion Sensor) ---
        success, reason = CompletionSensor.verify(booking_code, self.constraints)
        if success:
            return {
                "status": "SUCCESS",
                "booking_code": booking_code,
                "turns": turn,
                "trace": history,
                "reason": reason
            }

        # Nếu chưa thành công nhưng đã hết số vòng cho phép -> Bàn giao (Handoff)
        if turn >= self.max_turns:
            report = HandoffReport(
                status="HẾT LƯỢT GỌI (OUT_OF_BUDGET)",
                current_stage=f"Đã đạt mức tối đa {self.max_turns} vòng",
                actions_taken=history,
                failed_attempts=["Agent chưa chốt được vé trong số bước quy định."],
                specific_question="Cần nhân viên can thiệp xử lý tiếp yêu cầu của khách hàng."
            )
            return {
                "status": "OUT_OF_BUDGET",
                "report": report,
                "turns": turn,
                "trace": history,
                "booking_code": booking_code
            }

        return {
            "status": "SENSOR_FAILED",
            "reason": reason,
            "turns": turn,
            "trace": history,
            "booking_code": booking_code
        }
