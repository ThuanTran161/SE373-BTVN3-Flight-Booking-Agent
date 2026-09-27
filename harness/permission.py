from typing import Tuple, Dict, Any


class PermissionGuard:
    def __init__(self, price_limit: int = 2000000):
        self.price_limit = price_limit

    def check_permission(self, tool_name: str, args: Dict[str, Any], context_meta: Dict[str, Any]) -> Tuple[bool, str]:
        if tool_name == "pay":
            return False, "Hành động thanh toán tài chính (pay) cần con người duyệt."

        if tool_name == "book_seat":
            price = context_meta.get("current_price", 0)
            refundable = context_meta.get("refundable", True)
            if price > self.price_limit:
                return False, f"Giá vé ({price:,.0f}đ) vượt hạn mức ({self.price_limit:,.0f}đ)."
            if not refundable:
                return False, "Vé không hoàn tiền (non-refundable). Cần phê duyệt trước khi đặt chỗ."

        return True, "APPROVED"