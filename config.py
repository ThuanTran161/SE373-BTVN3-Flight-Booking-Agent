import os
import sys
import json
import re
from pathlib import Path
from typing import List, Optional, Any
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatResult, ChatGeneration

# Load .env file from project root
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)


class MockReasoningModel(BaseChatModel):
    def bind_tools(self, tools: Any, **kwargs: Any):
        return self

    @property
    def _llm_type(self) -> str:
        return "mock-reasoning-llm"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        **kwargs: Any
    ) -> ChatResult:
        text_content = ""
        for m in messages:
            if isinstance(m, (HumanMessage, ToolMessage)):
                text_content += "\n" + str(m.content)


        if "Flight Planner AI" in text_content or ("kế hoạch" in text_content.lower() and "Step Executor" not in text_content):
            if "Re-Planner" in text_content or "trở ngại" in text_content or "gãy" in text_content:
                plan_json = json.dumps({
                    "plan_summary": "Kế hoạch thích ứng: Chuyển sang chuyến bay thay thế VN122",
                    "steps": [
                        {"step_id": 1, "tool_name": "check_seat_availability", "purpose": "Kiểm tra ghế trống chuyến dự phòng VN122"},
                        {"step_id": 2, "tool_name": "calculate_baggage_fee", "purpose": "Tính phụ phí hành lý ký gửi cho VN122"},
                        {"step_id": 3, "tool_name": "book_ticket", "purpose": "Chốt đặt vé chuyến VN122"}
                    ]
                }, ensure_ascii=False)
            else:
                plan_json = json.dumps({
                    "plan_summary": "Kế hoạch tuần tự đặt vé máy bay SGN -> DAD",
                    "steps": [
                        {"step_id": 1, "tool_name": "search_flights", "purpose": "Tìm kiếm các chuyến bay theo ngày và tuyến đường"},
                        {"step_id": 2, "tool_name": "check_seat_availability", "purpose": "Kiểm tra ghế trống và giá vé chuyến tối ưu"},
                        {"step_id": 3, "tool_name": "calculate_baggage_fee", "purpose": "Tính phụ phí hành lý ký gửi"},
                        {"step_id": 4, "tool_name": "book_ticket", "purpose": "Chốt đặt vé và lấy mã đặt chỗ"}
                    ]
                }, ensure_ascii=False)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=plan_json))])


        if "Step Executor AI" in text_content:
            target_match = re.search(r"Bước hiện tại cần làm: \[(\w+)\]", text_content)
            target_tool = target_match.group(1) if target_match else "search_flights"

            # Phân tích xem QH118 đã bị hết ghế trong trace chưa
            qh118_sold_out = ('"flight_id": "QH118"' in text_content and '"available_seats": []' in text_content)
            current_fid = "VN122" if qh118_sold_out else "QH118"
            current_seat = "12A" if current_fid == "VN122" else "05D"

            if target_tool == "search_flights":
                thought = "Thực hiện tìm kiếm danh sách chuyến bay theo kế hoạch."
                tool_calls = [{
                    "name": "search_flights",
                    "args": {"origin": "SGN", "dest": "DAD", "date": "2026-10-07"},
                    "id": "exec_search",
                    "type": "tool_call"
                }]
            elif target_tool == "check_seat_availability":
                thought = f"Kiểm tra ghế trống chuyến {current_fid} theo bước được phân công."
                tool_calls = [{
                    "name": "check_seat_availability",
                    "args": {"flight_id": current_fid},
                    "id": f"exec_seat_{current_fid}",
                    "type": "tool_call"
                }]
            elif target_tool == "calculate_baggage_fee":
                thought = f"Tính phụ phí 15kg hành lý cho chuyến {current_fid}."
                tool_calls = [{
                    "name": "calculate_baggage_fee",
                    "args": {"flight_id": current_fid, "baggage_kg": 15},
                    "id": f"exec_baggage_{current_fid}",
                    "type": "tool_call"
                }]
            elif target_tool == "book_ticket":
                thought = f"Tiến hành chốt đặt vé chuyến {current_fid}, ghế {current_seat}."
                tool_calls = [{
                    "name": "book_ticket",
                    "args": {
                        "flight_id": current_fid,
                        "seat_number": current_seat,
                        "passenger_name": "Nguyen Van A",
                        "baggage_kg": 15
                    },
                    "id": f"exec_book_{current_fid}",
                    "type": "tool_call"
                }]
            else:
                thought = "Hoàn thành bước kế hoạch."
                tool_calls = []

            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=thought, tool_calls=tool_calls))])


        if "Sub-Agent chuyên trách chặng" in text_content:
            tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
            called_in_sub = []
            for m in messages:
                if isinstance(m, AIMessage) and m.tool_calls:
                    for tc in m.tool_calls:
                        called_in_sub.append(tc["name"])

            qh118_sold_out = ('"flight_id": "QH118"' in text_content and '"available_seats": []' in text_content)
            current_fid = "VN122" if qh118_sold_out else "QH118"
            current_seat = "12A" if current_fid == "VN122" else "05D"

            if "Chặng 1" in text_content:
                if "search_flights" not in called_in_sub:
                    return ChatResult(generations=[ChatGeneration(message=AIMessage(
                        content="Khám phá các chuyến bay SGN -> DAD.",
                        tool_calls=[{
                            "name": "search_flights",
                            "args": {"origin": "SGN", "dest": "DAD", "date": "2026-10-07"},
                            "id": "hybrid_c1_search",
                            "type": "tool_call"
                        }]
                    ))])
                return ChatResult(generations=[ChatGeneration(message=AIMessage(
                    content="Đã tìm thấy các chuyến bay khả dụng. Hoàn thành chặng 1.",
                    tool_calls=[]
                ))])

            elif "Chặng 2" in text_content:
                if "check_seat_availability" not in called_in_sub:
                    return ChatResult(generations=[ChatGeneration(message=AIMessage(
                        content=f"Kiểm tra ghế trống chuyến tối ưu {current_fid}.",
                        tool_calls=[{
                            "name": "check_seat_availability",
                            "args": {"flight_id": current_fid},
                            "id": f"hybrid_c2_seat_{current_fid}",
                            "type": "tool_call"
                        }]
                    ))])
                # Nếu vừa check mà hết ghế, check tiếp chuyến phụ
                if qh118_sold_out and current_fid == "QH118":
                    return ChatResult(generations=[ChatGeneration(message=AIMessage(
                        content="Chuyến QH118 hết chỗ, chuyển sang kiểm tra VN122.",
                        tool_calls=[{
                            "name": "check_seat_availability",
                            "args": {"flight_id": "VN122"},
                            "id": "hybrid_c2_seat_VN122",
                            "type": "tool_call"
                        }]
                    ))])
                if "calculate_baggage_fee" not in called_in_sub and "15" in text_content:
                    return ChatResult(generations=[ChatGeneration(message=AIMessage(
                        content=f"Tính phụ phí 15kg hành lý cho chuyến {current_fid}.",
                        tool_calls=[{
                            "name": "calculate_baggage_fee",
                            "args": {"flight_id": current_fid, "baggage_kg": 15},
                            "id": f"hybrid_c2_baggage_{current_fid}",
                            "type": "tool_call"
                        }]
                    ))])
                return ChatResult(generations=[ChatGeneration(message=AIMessage(
                    content="Đã xác nhận ghế trống và chi phí hành lý. Hoàn thành chặng 2.",
                    tool_calls=[]
                ))])

            elif "Chặng 3" in text_content:
                if "book_ticket" not in called_in_sub:
                    return ChatResult(generations=[ChatGeneration(message=AIMessage(
                        content=f"Chốt đặt vé cho chuyến {current_fid} ghế {current_seat}.",
                        tool_calls=[{
                            "name": "book_ticket",
                            "args": {
                                "flight_id": current_fid,
                                "seat_number": current_seat,
                                "passenger_name": "Nguyen Van A",
                                "baggage_kg": 15
                            },
                            "id": f"hybrid_c3_book_{current_fid}",
                            "type": "tool_call"
                        }]
                    ))])
                return ChatResult(generations=[ChatGeneration(message=AIMessage(
                    content="Đã chốt vé thành công!",
                    tool_calls=[]
                ))])


        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
        called_tools = []
        for m in messages:
            if isinstance(m, AIMessage) and m.tool_calls:
                for tc in m.tool_calls:
                    called_tools.append(tc["name"])

        checked_flight_id = None
        available_seats = []
        baggage_calculated = False
        booked_ticket = False

        for tm in tool_messages:
            try:
                data = json.loads(tm.content)
                if "available_seats" in data:
                    checked_flight_id = data.get("flight_id")
                    available_seats = data.get("available_seats", [])
                if "baggage_fee" in data:
                    baggage_calculated = True
                if "booking_code" in data:
                    booked_ticket = True
            except Exception:
                pass

        # Bước 1: Chưa search -> search_flights
        if "search_flights" not in called_tools:
            thought = "Tôi cần tìm kiếm các chuyến bay từ SGN đến DAD vào ngày 2026-10-07."
            tool_calls = [{
                "name": "search_flights",
                "args": {"origin": "SGN", "dest": "DAD", "date": "2026-10-07"},
                "id": "react_search_1",
                "type": "tool_call"
            }]
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=thought, tool_calls=tool_calls))])

        # Bước 2: Chưa check ghế -> check_seat_availability QH118
        if not checked_flight_id:
            target = "QH118"
            thought = f"Chuyến bay {target} có giờ bay 10:00 và giá tốt. Tôi sẽ kiểm tra ghế trống."
            tool_calls = [{
                "name": "check_seat_availability",
                "args": {"flight_id": target},
                "id": "react_seat_1",
                "type": "tool_call"
            }]
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=thought, tool_calls=tool_calls))])

        # Bước 3: Nếu hết ghế -> chuyển sang VN122 (Dynamic Fault Recovery)
        if not available_seats:
            alt_target = "VN122" if checked_flight_id == "QH118" else "VJ604"
            thought = f"Chuyến bay {checked_flight_id} hiện tại đã hết ghế. Tôi đổi sang kiểm tra chuyến thay thế {alt_target}."
            tool_calls = [{
                "name": "check_seat_availability",
                "args": {"flight_id": alt_target},
                "id": f"react_seat_alt_{alt_target}",
                "type": "tool_call"
            }]
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=thought, tool_calls=tool_calls))])

        # Bước 4: Có ghế, tính hành lý nếu chưa tính
        if "calculate_baggage_fee" not in called_tools and "15" in text_content:
            thought = f"Chuyến {checked_flight_id} còn các ghế {available_seats}. Khách yêu cầu 15kg hành lý, tôi tính phụ phí."
            tool_calls = [{
                "name": "calculate_baggage_fee",
                "args": {"flight_id": checked_flight_id, "baggage_kg": 15},
                "id": "react_baggage_1",
                "type": "tool_call"
            }]
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=thought, tool_calls=tool_calls))])

        # Bước 5: Chốt đặt vé book_ticket
        if not booked_ticket:
            seat_to_book = available_seats[0] if available_seats else "05D"
            thought = (
                f"Mọi điều kiện đều đạt: Chuyến {checked_flight_id}, ghế {seat_to_book}, chi phí hợp lệ. "
                "Tiến hành chốt đặt vé máy bay."
            )
            tool_calls = [{
                "name": "book_ticket",
                "args": {
                    "flight_id": checked_flight_id,
                    "seat_number": seat_to_book,
                    "passenger_name": "Nguyen Van A",
                    "baggage_kg": 15 if "15" in text_content else 0
                },
                "id": "react_book_1",
                "type": "tool_call"
            }]
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=thought, tool_calls=tool_calls))])

        # Bước 6: Hoàn tất
        thought = "Vé máy bay đã được đặt thành công và xác nhận trong hệ thống. Hoàn tất tác vụ!"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=thought, tool_calls=[]))])


def get_model(temperature: float = 0.0):

    provider = os.getenv("LLM_PROVIDER", "google").lower()
    model_name = os.getenv("MODEL_NAME")
    force_mock = os.getenv("USE_MOCK_LLM", "false").lower() in ["1", "true", "yes"]

    if force_mock:
        return MockReasoningModel()

    if provider == "google":
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if api_key and api_key != "your_google_api_key_here":
            from langchain_google_genai import ChatGoogleGenerativeAI
            target_model = model_name or "gemini-2.0-flash"
            return ChatGoogleGenerativeAI(
                model=target_model,
                google_api_key=api_key,
                temperature=temperature,
            )
        else:
            return MockReasoningModel()

    elif provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key and api_key != "your_openai_api_key_here":
            from langchain_openai import ChatOpenAI
            target_model = model_name or "gpt-4o-mini"
            return ChatOpenAI(
                model=target_model,
                openai_api_key=api_key,
                temperature=temperature,
            )
        else:
            return MockReasoningModel()

    return MockReasoningModel()
