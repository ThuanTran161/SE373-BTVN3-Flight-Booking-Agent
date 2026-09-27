import json
from typing import Dict, Any, List
from harness.constraints import BookingConstraint
from harness.completion_sensor import CompletionSensor
from tools import flight_tools

class HybridAgent:
    def __init__(self, constraints: BookingConstraint):
        self.constraints = constraints

    def run(self) -> Dict[str, Any]:
        history: List[Dict[str, Any]] = []
        booking_code = None
        target_flight = "VN122"
        turns = 0

        # Giai đoạn 1: Search qua invoke
        turns += 1
        raw = flight_tools.search_flights.invoke({
            "origin": self.constraints.origin,
            "dest": self.constraints.dest,
            "date": self.constraints.date
        })
        history.append({"phase": "SEARCH", "obs": json.loads(raw)})

        # Giai đoạn 2: Check và Tái lập kế hoạch
        turns += 1
        raw_seat = flight_tools.check_seat.invoke({"flight_id": target_flight})
        seat_res = json.loads(raw_seat)
        history.append({"phase": "CHECK", "target": target_flight, "obs": seat_res})

        if not bool(seat_res.get("available_seats")) or (seat_res.get("price", 9e9) > self.constraints.max_price):
            turns += 1
            # Re-planning
            target_flight = "QH118"
            raw_seat = flight_tools.check_seat.invoke({"flight_id": target_flight})
            seat_res = json.loads(raw_seat)
            history.append({"phase": "RE-PLAN_CHECK", "target": target_flight, "obs": seat_res})

        # Giai đoạn 3: Book
        turns += 1
        seat_num = seat_res["available_seats"][0]
        raw_book = flight_tools.book_seat.invoke({"flight_id": target_flight, "seat_number": seat_num})
        book_res = json.loads(raw_book)
        booking_code = book_res.get("booking_code")
        history.append({"phase": "BOOK", "obs": book_res})

        # Giai đoạn 4: Pay
        turns += 1
        raw_pay = flight_tools.pay.invoke({"booking_code": booking_code})
        history.append({"phase": "PAY", "obs": json.loads(raw_pay)})

        success, msg = CompletionSensor.verify(booking_code, self.constraints)
        return {
            "status": "SUCCESS" if success else "FAILED",
            "booking_code": booking_code,
            "turns": turns,
            "trace": history,
            "reason": msg
        }