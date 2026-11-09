import type { OcrLine, Point } from "./types";

export function boundsOf(polygon: Point[]) {
  const xs = polygon.map((p) => p[0]);
  const ys = polygon.map((p) => p[1]);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("Không đọc được ảnh"));
    img.src = src;
  });
}

/** Cắt ảnh từng dòng để hiện cạnh ô sửa văn bản. */
export async function cropLines(src: string, lines: OcrLine[]): Promise<Record<string, string>> {
  const img = await loadImage(src);
  const out: Record<string, string> = {};
  const targetH = 72;
  for (const line of lines) {
    const b = boundsOf(line.polygon);
    if (b.w < 1 || b.h < 1) continue;
    const s = Math.min(targetH / b.h, 1200 / b.w);
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(b.w * s));
    canvas.height = Math.max(1, Math.round(b.h * s));
    const ctx = canvas.getContext("2d");
    if (!ctx) continue;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(img, b.x, b.y, b.w, b.h, 0, 0, canvas.width, canvas.height);
    out[line.id] = canvas.toDataURL("image/jpeg", 0.85);
  }
  return out;
}

export const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/bmp"];
export const MAX_FILE_MB = 10;

export function validateImage(file: File): string | null {
  if (!ACCEPTED_TYPES.includes(file.type)) {
    return `Tệp “${file.name}” không phải ảnh JPG, PNG, WEBP hoặc BMP.`;
  }
  if (file.size > MAX_FILE_MB * 1024 * 1024) {
    return `Ảnh nặng ${(file.size / 1024 / 1024).toFixed(1)} MB, vượt giới hạn ${MAX_FILE_MB} MB.`;
  }
  return null;
}

export function downloadText(filename: string, content: string, type = "text/plain;charset=utf-8") {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
