# Meme Sound Auto-Inserter — User Feedback & Light Editor Design Spec
**Date**: 2026-06-12
**Author**: AI Design Session
**Status**: Approved by user

---

## Overview

Phần này định nghĩa luồng tương tác và hệ thống backend để thu thập đánh giá (feedback) của người dùng về chất lượng của các meme sound được tự động chèn. Dữ liệu này sẽ được lưu trữ qua `use_count` và `accept_rate` để đánh giá hiệu quả hệ thống.

**Target users**: Content creators sử dụng tính năng Meme Sound Inserter.
**Platform**: Web app (Light Editor).

---

## Section 1: User Flow & Giao diện (UI)

Khi video được xử lý xong, hệ thống không chỉ cung cấp nút tải xuống mà sẽ cung cấp một **Light Editor** cho phép người dùng xem lại và chỉnh sửa kết quả.

### UI Components:
1. **Video Preview**: Trình phát video kết quả.
2. **Timeline List**: Danh sách các sound đã chèn theo trình tự thời gian (VD: `00:15 - Bruh Sound Effect`).
3. **Thao tác trên Sound**:
   - `[Xóa]`: Gạch bỏ/xóa sound khỏi danh sách. (Feedback: Rejected).
   - `[Đổi]`: Mở modal Replace. (Feedback: Rejected sound cũ, Accepted sound mới).
4. **Modal Replace**:
   - **Gợi ý (Smart Suggestions)**: Dựa vào context của video highlight, dùng ChromaDB hiển thị Top 3-5 sounds phù hợp.
   - **Tìm kiếm**: Thanh tìm kiếm để query bất kỳ sound nào trong hệ thống.
5. **Nút Export & Chốt Feedback**: Nút "Tải Video" (hoặc Save). Khi click, UI khóa lại, gửi yêu cầu re-render (nếu có thay đổi) và tải về.

---

## Section 2: Architecture & API Changes

Để hỗ trợ Editor và thu thập Feedback, hệ thống backend cần bổ sung và cập nhật các API.

### 1. Mở rộng dữ liệu trả về từ Celery Task
Thay vì chỉ trả url, task sẽ trả về danh sách `placements` đã được dùng để render:
```json
{
  "output_url": "/download/{job_id}",
  "placements": [
    {
      "placement_id": "p1",
      "sound_id": "bruh_1",
      "name": "Bruh Effect",
      "insert_ms": 15000,
      "highlight_context": "Người chơi trượt chân"
    }
  ]
}
```

### 2. Thêm Endpoint Gợi Ý và Tìm Kiếm
*   `GET /sounds/suggest?context={text}`: Gọi ChromaDB để lấy top 5 sounds dựa trên ngữ nghĩa của context.
*   `GET /sounds/search?q={query}`: Query SQL (`LIKE %query%`) tìm sound trong database SQLite.

### 3. API Finalize (Ghi nhận Feedback & Re-render)
*   **Endpoint**: `POST /finalize`
*   **Payload**:
```json
{
  "job_id": "1234-5678",
  "actions": [
    {"sound_id": "bruh_1", "status": "keep"},
    {"old_sound_id": "wow", "new_sound_id": "oh_no", "status": "replace"},
    {"sound_id": "metal_pipe", "status": "delete"}
  ],
  "final_placements": [ ... ]
}
```
*   **Logic Backend**:
    1. Đọc mảng `actions`, gọi hàm `update_sound_stats()` (có sẵn trong `models.py`) để tính lại `use_count` và `accept_rate`.
    2. Nếu `actions` chỉ chứa `keep` → Trả về `{"status": "ready", "url": "/download/job_id"}`.
    3. Nếu có thay đổi (Xóa/Đổi) → Tạo Celery Task `rerender_video`. Task này bỏ qua mọi bước phân tích AI, chỉ sử dụng ffmpeg trộn lại file video gốc và âm thanh dựa trên `final_placements`. Trả về `{"task_id": "..."}` để UI hiện progress.
