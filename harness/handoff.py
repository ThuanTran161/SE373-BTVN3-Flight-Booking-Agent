from dataclasses import dataclass
from typing import List, Dict, Any

@dataclass
class HandoffReport:
    status: str
    current_stage: str
    actions_taken: List[Dict[str, Any]]
    failed_attempts: List[str]
    specific_question: str

    def format_terminal(self) -> str:
        return (
            f"\n========= BÀN GIAO CHO CON NGƯỜI (HANDOFF) =========\n"
            f"[Trạng thái]        : {self.status}\n"
            f"[Giai đoạn dừng]    : {self.current_stage}\n"
            f"[Số bước đã thử]    : {len(self.actions_taken)} bước\n"
            f"[Thất bại/Cảnh báo] : {', '.join(self.failed_attempts) if self.failed_attempts else 'Không có'}\n"
            f"[Câu hỏi cụ thể]    : {self.specific_question}\n"
            f"===================================================\n"
        )