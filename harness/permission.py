from typing import Tuple, Dict, Any, Optional, Callable


class PermissionGuard:


    def __init__(self, price_limit: int = 2000000, auto_approve: bool = False):
        self.price_limit = price_limit
        self.auto_approve = auto_approve

    def check_permission(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context_meta: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str]:

        context_meta = context_meta or {}

        # Nếu đang ở chế độ auto_approve (cho benchmark tự động), luôn cho phép
        if self.auto_approve:
            return True, "AUTO_APPROVED"

        # 1. Hành động thanh toán trực tiếp
        if tool_name == "pay":
            return False, "Hành động thanh toán tài chính (pay) là nhạy cảm, bắt buộc con người phê duyệt."

        # 2. Hành động chốt đặt vé (book_ticket hoặc book_seat)
        if tool_name in ["book_ticket", "book_seat"]:
            current_price = context_meta.get("current_price", 0)
            refundable = context_meta.get("refundable", True)

            # Cảnh báo 1: Vé không hoàn tiền
            if not refundable:
                return (
                    False,
                    f"CẢNH BÁO: Chuyến bay '{args.get('flight_id')}' là vé KHÔNG HOÀN TIỀN (non-refundable). Cần xác nhận."
                )

            # Cảnh báo 2: Giá vượt hạn mức ngân sách
            if current_price > self.price_limit:
                return (
                    False,
                    f"CẢNH BÁO: Tổng chi phí dự kiến ({current_price:,.0f} VND) vượt trần ngân sách ({self.price_limit:,.0f} VND)."
                )

            # Cảnh báo 3: Hành động chốt vé tiêu tốn tài chính
            return (
                False,
                f"XÁC NHẬN ĐẶT VÉ: Chuẩn bị chốt vé chuyến {args.get('flight_id')} (Ghế {args.get('seat_number')}) cho hành khách {args.get('passenger_name', 'khách')}."
            )

        return True, "APPROVED"

    def request_approval_interactive(self, question: str) -> bool:
        """Hỏi ý kiến trực tiếp người dùng qua terminal CLI."""
        if self.auto_approve:
            return True
        try:
            choice = input(f"\n[KIỂM QUYỀN]: {question}\nBạn có đồng ý thực thi không? (y/n): ").strip().lower()
            return choice in ["y", "yes", "dong y", "ok"]
        except (EOFError, KeyboardInterrupt):
            return False
