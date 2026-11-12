import { detectLines } from "./lineDetect";
import { SAMPLES } from "./samples";
import type { OcrLine, OcrRequest, OcrResponse, PipelineStep } from "./types";

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** Số giả ngẫu nhiên ổn định theo (seed, i) để độ tin cậy không đổi giữa các lần chạy. */
function pseudo(seed: number, i: number): number {
  const x = Math.sin(seed * 9301 + i * 49297) * 233280;
  return x - Math.floor(x);
}

/**
 * Bộ OCR mô phỏng: tìm dòng thật trên ảnh bằng chiếu ngang (lineDetect),
 * còn văn bản là văn bản mẫu (với ảnh mẫu) hoặc chữ giữ chỗ (với ảnh tải lên).
 */
export async function mockOcr(
  req: OcrRequest,
  onStep: (step: PipelineStep) => void,
): Promise<OcrResponse> {
  const t0 = performance.now();
  onStep("detect");
  const bitmap = await createImageBitmap(req.file);
  const { width, height } = bitmap;
  const boxes = detectLines(bitmap, width, height);
  bitmap.close();
  await sleep(380);

  onStep("group");
  await sleep(220);
  const t1 = performance.now();

  onStep("recognize");
  await sleep(Math.min(1400, 160 + boxes.length * 90));

  const sample = SAMPLES.find((s) => s.file === req.file.name);
  const seed = req.file.size % 997;
  const lines: OcrLine[] = boxes.map((b, i) => {
    let confidence = 0.86 + pseudo(seed, i) * 0.13;
    if (pseudo(seed + 1, i) < 0.18) confidence = 0.62 + pseudo(seed + 2, i) * 0.15;
    if (req.mode === "handwritten") confidence -= 0.06;
    return {
      id: `line-${i + 1}`,
      polygon: [
        [b.x, b.y],
        [b.x + b.w, b.y],
        [b.x + b.w, b.y + b.h],
        [b.x, b.y + b.h],
      ],
      text: sample?.lines[i] ?? `Văn bản mô phỏng của dòng ${i + 1}`,
      confidence: Math.max(0.3, Math.min(0.995, confidence)),
    };
  });
  const t2 = performance.now();

  onStep("merge");
  await sleep(140);
  const t3 = performance.now();

  return {
    image: { width, height },
    lines,
    timing: {
      detection_ms: Math.round(t1 - t0),
      recognition_ms: Math.round(t2 - t1),
      total_ms: Math.round(t3 - t0),
    },
    model: { name: req.model, mode: req.mode, version: "mock" },
    mock: true,
  };
}
