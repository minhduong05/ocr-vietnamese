import { mockOcr } from "./mockOcr";
import type { OcrRequest, OcrResponse, PipelineStep } from "./types";

export const OCR_API_URL = (process.env.NEXT_PUBLIC_OCR_API_URL ?? "").trim().replace(/\/+$/, "");

/** Không cấu hình backend thì chạy chế độ mô phỏng. */
export const IS_MOCK = OCR_API_URL === "";

function assertResponse(data: unknown): asserts data is OcrResponse {
  const d = data as OcrResponse;
  if (
    !d ||
    typeof d !== "object" ||
    !d.image ||
    typeof d.image.width !== "number" ||
    !Array.isArray(d.lines) ||
    d.lines.some((l) => typeof l.text !== "string" || !Array.isArray(l.polygon))
  ) {
    throw new Error("Phản hồi của máy chủ OCR không đúng định dạng OcrResponse (xem lib/types.ts).");
  }
}

export async function runOcr(
  req: OcrRequest,
  onStep: (step: PipelineStep) => void,
): Promise<OcrResponse> {
  if (IS_MOCK) return mockOcr(req, onStep);

  onStep("detect");
  const body = new FormData();
  body.append("image", req.file);
  body.append("mode", req.mode);
  body.append("model", req.model);

  let res: Response;
  try {
    res = await fetch(`${OCR_API_URL}/api/v1/ocr`, { method: "POST", body });
  } catch {
    throw new Error(
      `Không kết nối được máy chủ OCR tại ${OCR_API_URL}. Kiểm tra backend đã chạy và cho phép CORS.`,
    );
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail ?? j);
    } catch {
      /* giữ statusText */
    }
    throw new Error(`Máy chủ OCR trả lỗi ${res.status}: ${detail}`);
  }
  onStep("recognize");
  const data: unknown = await res.json();
  assertResponse(data);
  onStep("merge");
  return data;
}
