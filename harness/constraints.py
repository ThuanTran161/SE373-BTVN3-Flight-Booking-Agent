from typing import Optional
from pydantic import BaseModel, Field


class BookingConstraint(BaseModel):
    """Lớp ràng buộc dữ liệu đầu vào cho quy trình đặt vé máy bay."""
    origin: str = Field(default="SGN", description="Mã sân bay xuất phát (VD: SGN, HAN)")
    dest: str = Field(default="DAD", description="Mã sân bay đích (VD: DAD, SGN)")
    date: str = Field(default="2026-10-07", description="Ngày bay YYYY-MM-DD")
    max_price: int = Field(default=2000000, description="Ngân sách tối đa (VND)")
    depart_before: str = Field(default="12:00", description="Thời điểm khởi hành muộn nhất (HH:MM)")
    passenger_name: str = Field(default="Nguyen Van A", description="Tên hành khách")
    baggage_kg: int = Field(default=0, ge=0, description="Khối lượng hành lý ký gửi (kg)")
    require_refundable: bool = Field(default=False, description="Yêu cầu vé có thể hoàn/hủy")

    def to_natural_language(self) -> str:
        """Chuyển đổi ràng buộc thành mô tả tự nhiên cho LLM Prompt."""
        details = [
            f"Điểm khởi hành: {self.origin}",
            f"Điểm đến: {self.dest}",
            f"Ngày bay: {self.date}",
            f"Thời gian khởi hành: trước {self.depart_before}",
            f"Ngân sách tối đa: {self.max_price:,.0f} VND",
            f"Hành khách: {self.passenger_name}",
        ]
        if self.baggage_kg > 0:
            details.append(f"Hành lý ký gửi: {self.baggage_kg} kg")
        if self.require_refundable:
            details.append("Yêu cầu chính sách: Vé có thể hoàn hủy (refundable)")
        return "\n".join(details)
