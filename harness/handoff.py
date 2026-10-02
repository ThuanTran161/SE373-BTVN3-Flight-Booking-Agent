from typing import List, Dict, Any
from pydantic import BaseModel, Field


class HandoffReport(BaseModel):
    """Báo cáo chuyển giao cho nhân viên hỗ trợ con người."""
    status: str = Field(description="Mã trạng thái kích hoạt bàn giao")
    current_stage: str = Field(description="Giai đoạn/Vòng lặp xảy ra sự cố")
    actions_taken: List[Dict[str, Any]] = Field(default_factory=list, description="Lịch sử các bước đã thực hiện")
    failed_attempts: List[str] = Field(default_factory=list, description="Các cảnh báo hoặc lần thử thất bại")
    specific_question: str = Field(description="Câu hỏi hoặc yêu cầu hành động gửi đến con người")

    def format_terminal(self) -> str:
        """Định dạng báo cáo để hiển thị rõ ràng trên màn hình Terminal."""
        sep = "=" * 62
        lines = [
            f"\n{sep}",
            "    BÁO CÁO BÀN GIAO CHO CON NGƯỜI (HUMAN HANDOFF REPORT)    ",
            sep,
            f" [Trạng thái]        : {self.status}",
            f" [Giai đoạn dừng]    : {self.current_stage}",
            f" [Số bước đã thử]    : {len(self.actions_taken)} bước",
            f" [Lý do can thiệp]   : {', '.join(self.failed_attempts) if self.failed_attempts else 'Không có'}",
            f" [Yêu cầu cụ thể]    : {self.specific_question}",
            sep,
        ]
        return "\n".join(lines)
