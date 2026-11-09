# Web demo: nhận dạng đoạn văn tiếng Việt

Frontend Next.js (React + TypeScript) cho phần 3 của đề xuất: người dùng tải ảnh đoạn văn,
xem khung từng dòng trên ảnh, sửa văn bản nhận dạng, rồi sao chép hoặc tải TXT/JSON.

Hiện web chạy **chế độ mô phỏng**: chưa gọi model. Khung dòng được tìm bằng một thuật toán đơn giản
ngay trên trình duyệt (phân ngưỡng Otsu + chiếu ngang, xem `lib/lineDetect.ts`); văn bản là văn bản
đúng của ảnh mẫu, hoặc chữ giữ chỗ với ảnh bạn tải lên.

## Chạy

Cần Node.js 20.9 trở lên.

```bash
cd apps/web
npm install
npm run dev        # http://localhost:3000
```

Bản build: `npm run build && npm start`. Kiểm tra kiểu: `npm run typecheck`.

## Tính năng

- Tải ảnh bằng nút chọn tệp, kéo thả vào khung, hoặc dán bằng Ctrl+V. Có 2 ảnh mẫu trong `public/samples/`.
- Chọn kiểu chữ (chữ in / chữ viết tay) và mô hình (CRNN, CNN + Transformer, CNN + Transformer + Sparse MoE).
- Ảnh hiện khung từng dòng, đánh số theo thứ tự đọc. Rê chuột hoặc bấm vào khung sẽ làm nổi dòng tương ứng ở danh sách, và ngược lại.
- Mỗi dòng có ảnh cắt, ô sửa văn bản, độ tin cậy; dòng dưới 80% được tô vàng. Có nút khôi phục bản gốc.
- Tab Toàn văn để sửa cả đoạn. Sao chép, tải `.txt`, tải `.json` (kèm toạ độ, độ tin cậy và bản đã sửa).
- Thanh tiến trình theo 4 bước của pipeline: tìm vùng chữ, ghép theo dòng, nhận dạng, ghép văn bản; kèm thời gian từng phần.

## Nối với backend thật

Tạo `apps/web/.env.local`:

```bash
NEXT_PUBLIC_OCR_API_URL=http://localhost:8000
```

Khởi động lại `npm run dev`. Web sẽ gửi:

```
POST {NEXT_PUBLIC_OCR_API_URL}/api/v1/ocr      (multipart/form-data)
  image  tệp ảnh
  mode   "printed" | "handwritten"
  model  "crnn" | "transformer" | "sparse_moe"
```

và chờ JSON đúng kiểu `OcrResponse` trong `lib/types.ts`:

```json
{
  "image": { "width": 1400, "height": 980 },
  "lines": [
    {
      "id": "line-1",
      "polygon": [[110, 90], [480, 90], [480, 150], [110, 150]],
      "text": "Truyện Kiều",
      "confidence": 0.96
    }
  ],
  "timing": { "detection_ms": 120, "recognition_ms": 340, "total_ms": 470 },
  "model": { "name": "crnn", "mode": "printed", "version": "v1" }
}
```

- `polygon` là 4 góc theo toạ độ pixel của ảnh gốc (sau khi xoay theo EXIF), theo chiều kim đồng hồ từ góc trên trái.
- `lines` đã sắp theo thứ tự đọc; `text` chuẩn hoá NFC.
- Lỗi trả về mã HTTP khác 2xx với `{"detail": "..."}` (mặc định của FastAPI); web sẽ hiện nội dung `detail`.
- Backend cần bật CORS cho địa chỉ web, ví dụ `CORSMiddleware(allow_origins=["http://localhost:3000"])`.

## Cấu trúc

```text
app/
  layout.tsx          # font Be Vietnam Pro + Literata (tự host, có bộ ký tự tiếng Việt)
  page.tsx
  globals.css         # token màu, giao diện sáng/tối
components/
  Workbench.tsx       # trạng thái chung: ảnh, thiết lập, kết quả, các dòng đã sửa
  ImageStage.tsx      # vùng ảnh: kéo thả, khung dòng, đánh số
  ResultPanel.tsx     # danh sách dòng, toàn văn, sao chép/tải xuống
  PipelineStatus.tsx  # 4 bước pipeline và thời gian
lib/
  types.ts            # hợp đồng API giữa web và backend
  ocrClient.ts        # chọn mô phỏng hoặc gọi backend theo NEXT_PUBLIC_OCR_API_URL
  mockOcr.ts          # bộ OCR mô phỏng
  lineDetect.ts       # tìm dòng đơn giản cho chế độ mô phỏng
  image.ts            # cắt ảnh dòng, kiểm tra tệp, tải xuống
  samples.ts          # ảnh mẫu và văn bản đúng
public/samples/       # ảnh mẫu
```

Ảnh mẫu `truyen-kieu.png` là 8 câu mở đầu Truyện Kiều (Nguyễn Du, thuộc phạm vi công cộng);
`thong-bao.jpg` là thông báo giả lập, có nền không đều và nhiễu như ảnh chụp.
