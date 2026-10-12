# Vietnamese OCR Project (ocr-vietnamese)

Dự án nhận dạng chữ tiếng Việt (Vietnamese Optical Character Recognition) phục vụ nghiên cứu và huấn luyện mô hình học sâu.

## Cấu trúc thư mục

```text
ocr-vietnamese/
  README.md
  requirements.in
  requirements-lock.txt
  configs/
    data/
    crnn/
    dense/
    moe/
    experiments/
  src/
    data/           # manifest.py, dataset.py, collate.py, sampler.py, transforms.py
    text/           # normalize.py, vocab.py, ctc_codec.py, ar_codec.py
    models/         # cnn.py, crnn.py, dense_transformer.py, sparse_moe.py
    training/       # engine.py, losses.py, checkpoint.py, scheduler.py
    decoding/       # ctc_greedy.py, ctc_beam.py, ar_greedy.py, ar_beam.py
    evaluation/     # metrics.py, evaluator.py, latency.py, error_analysis.py
  scripts/          # prepare_data.py, train.py, evaluate.py, benchmark.py, export_predictions.py
  tools/
    data/           # import_uit.py, import_vintext.py, import_mcocr.py, render_vnondb.py
                    # audit.py, split.py, deduplicate.py, generate_synthetic.py
  tests/            # test_data.py, test_codec.py, test_ctc.py, test_masks.py, test_moe.py
  data/
    raw/            # Dữ liệu thô tải về (ngoài Git)
    processed/      # Dữ liệu sau xử lý / cắt dòng (ngoài Git)
    manifests/      # Manifest jsonl / csv phục vụ nạp dữ liệu
    vocab/          # Bộ từ vựng / bảng chữ cái tiếng Việt
  runs/             # Log huấn luyện, metrics, predictions, checkpoints theo từng run_id
  reports/
    dataset_card/
    experiment_registry/
    results/
    error_gallery/
```

## Lưu ý về Quản lý Dữ liệu và Mã nguồn
- **Dataset và Checkpoints**: Các tệp dung lượng lớn đặt ngoài Git (đã được cấu hình trong `.gitignore`).
- **Git Repository**: Chỉ lưu mã nguồn, tệp cấu hình (configs), manifest được phép chia sẻ, mã băm kiểm tra (checksum) và tài liệu hướng dẫn tải dữ liệu.
- **Giao diện CLI**: Các lệnh trong thư mục `scripts/` và `tools/` tạo thành giao diện CLI của dự án, nhóm tự xây dựng độc lập.
