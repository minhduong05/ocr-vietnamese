# Nhóm 11 - OCR tiếng Việt

Theo [slide đề xuất](docs/proposal/Nhom11_De_xuat_OCR.pptx): so sánh CRNN, Transformer,
Sparse MoE trên chữ in; chọn một model để fine-tune chữ viết tay, sau đó tích hợp demo.

## Cấu trúc

```text
src/
  common/                  # Phần dùng chung
    data.py                # Đọc dữ liệu
    preprocess.py          # Tiền xử lý ảnh và nhãn
    metrics.py             # CER, WER, exact match
  models/
    crnn/                  # Người phụ trách CRNN
      model.py
      train.py
      config.yaml
    transformer/           # Người phụ trách Transformer
      model.py
      train.py
      config.yaml
    sparse_moe/            # Người phụ trách Sparse MoE
      model.py
      router.py            # Top-1, 3 expert theo đề xuất
      train.py
      config.yaml
  pipeline/
    detector.py            # Detector pretrained và cắt dòng
    recognizer.py          # Nhận dạng dòng, ghép đoạn văn
scripts/
  prepare_data.py
  finetune.py               # Fine-tune model được chọn
  evaluate.py
  build_eda_pdf_report.py   # Mã tạo PDF đã có
configs/data.yaml          # Cấu hình dữ liệu chung
apps/api/main.py           # Backend FastAPI
apps/web/                  # Frontend React
notebooks/eda/             # Hai notebook EDA đã có
docs/proposal/             # Slide đề xuất
data/                      # Dataset local, ngoài Git
runs/                      # Checkpoint và log local, ngoài Git
reports/                   # Các kết quả phân tích đã có
output/pdf/                # Báo cáo PDF đã tạo
```

## Cách chia việc

- Ba người làm trong ba thư mục model riêng, bao gồm code train và config của mình.
- Người làm dữ liệu/tích hợp phụ trách `common/`, `pipeline/` và các script chung.
- Chốt cùng dữ liệu/split và cách tính metric để so sánh công bằng.
- Mỗi người một nhánh Git; tránh sửa file của model khác. Thay đổi phần chung thì trao đổi trước.
- Giữ checkpoint chữ in riêng; stage 2 chỉ fine-tune model được chọn trên ba nguồn viết tay.

Các file khung mới chỉ có chú thích, chưa cài đặt model hoặc quy trình train.
Dữ liệu, notebook EDA và báo cáo hiện có được giữ lại.
