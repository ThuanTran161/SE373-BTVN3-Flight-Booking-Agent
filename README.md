# SE373 - Bài Tập Thực Hành Buổi 3: Agent Đặt Vé Máy Bay

- **Sinh viên:** Trần Minh Thuận
- **MSSV:** 24521746
- **Môn học:** Kỹ thuật xây dựng hệ thống Agentic AI (SE373)

---

## Báo cáo thực hành

📄 **Xem và tải báo cáo chi tiết tại đây:** [Báo cáo Thực hành Buổi 3 PDF](./BTTH_Buoi3_SE373_TranMinhThuan_24521746.pdf)

---

## Hướng dẫn chạy thử nghiệm

1. Cài đặt thư viện:
   ```bash
   pip install -r requirements.txt
   ```

2. Cấu hình API Key (Tùy chọn):
   - Đổi tên hoặc copy file `.env.example` thành `.env`:
     ```bash
     cp .env.example .env
     ```
   - Điền API Key của bạn (`GOOGLE_API_KEY` hoặc `OPENAI_API_KEY`).
   - *Lưu ý:* Hệ thống có tích hợp sẵn chế độ mô phỏng suy luận offline, có thể chạy thử nghiệm ngay cả khi chưa nạp API Key.

3. Chạy kiểm thử đơn vị độc lập 4 lớp Harness:
   ```bash
   python test_manual.py
   ```

4. Chạy Benchmark đánh giá thực nghiệm so sánh 3 mẫu thiết kế Agent (ReAct, Plan-then-Execute, Hybrid):
   ```bash
   python benchmark.py
   ```

5. Chạy Demo tương tác trực tiếp (Human-in-the-loop CLI):
   ```bash
   python main.py
   ```
