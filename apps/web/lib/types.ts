/**
 * Hợp đồng dữ liệu giữa web và backend OCR (apps/api).
 * Backend FastAPI cần trả về đúng cấu trúc OcrResponse ở endpoint:
 *   POST {NEXT_PUBLIC_OCR_API_URL}/api/v1/ocr   (multipart/form-data)
 *   - image: tệp ảnh đoạn văn
 *   - mode:  "printed" | "handwritten"
 *   - model: "crnn" | "transformer" | "sparse_moe"
 */

export type OcrMode = "printed" | "handwritten";
export type OcrModel = "crnn" | "transformer" | "sparse_moe";

/** Điểm [x, y] theo pixel của ảnh gốc. */
export type Point = [number, number];

export interface OcrLine {
  id: string;
  /** Tứ giác bao dòng chữ (4 điểm, theo chiều kim đồng hồ từ góc trên trái), toạ độ ảnh gốc. */
  polygon: Point[];
  /** Văn bản recognizer đọc được, đã chuẩn hoá NFC. */
  text: string;
  /** Độ tin cậy 0..1. */
  confidence: number;
}

export interface OcrResponse {
  image: { width: number; height: number };
  /** Các dòng đã sắp theo thứ tự đọc. */
  lines: OcrLine[];
  timing: { detection_ms: number; recognition_ms: number; total_ms: number };
  model: { name: OcrModel; mode: OcrMode; version?: string };
  /** true nếu kết quả do bộ mô phỏng tạo ra, không phải model thật. */
  mock?: boolean;
}

export interface OcrRequest {
  file: File;
  mode: OcrMode;
  model: OcrModel;
}

/** Các bước của pipeline nhận dạng đoạn văn, theo slide đề xuất. */
export type PipelineStep = "detect" | "group" | "recognize" | "merge";

export const PIPELINE_STEPS: { id: PipelineStep; label: string }[] = [
  { id: "detect", label: "Tìm vùng chữ" },
  { id: "group", label: "Ghép theo dòng" },
  { id: "recognize", label: "Nhận dạng" },
  { id: "merge", label: "Ghép văn bản" },
];

export const MODEL_OPTIONS: { id: OcrModel; label: string }[] = [
  { id: "crnn", label: "CRNN (CNN + BiLSTM + CTC)" },
  { id: "transformer", label: "CNN + Transformer" },
  { id: "sparse_moe", label: "CNN + Transformer + Sparse MoE" },
];

export const MODE_OPTIONS: { id: OcrMode; label: string }[] = [
  { id: "printed", label: "Chữ in" },
  { id: "handwritten", label: "Chữ viết tay" },
];
