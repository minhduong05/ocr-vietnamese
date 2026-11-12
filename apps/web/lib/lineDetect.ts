/**
 * Bộ tìm dòng đơn giản dùng cho CHẾ ĐỘ MÔ PHỎNG (không phải detector thật).
 * Phân ngưỡng Otsu, chiếu ngang để tìm các dải có mực, rồi lấy biên trái/phải của mỗi dải.
 * Đủ tốt với ảnh văn bản thẳng, nền sáng; ảnh nghiêng hoặc nhiều cột sẽ cần DBNet/PP-OCR.
 */

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

const MAX_SIDE = 1400;
const MAX_LINES = 60;

function otsu(hist: Float64Array, total: number): number {
  let sumAll = 0;
  for (let i = 0; i < 256; i++) sumAll += i * hist[i];
  let sumB = 0;
  let wB = 0;
  let best = 0;
  let threshold = 127;
  for (let t = 0; t < 256; t++) {
    wB += hist[t];
    if (wB === 0) continue;
    const wF = total - wB;
    if (wF === 0) break;
    sumB += t * hist[t];
    const mB = sumB / wB;
    const mF = (sumAll - sumB) / wF;
    const between = wB * wF * (mB - mF) * (mB - mF);
    if (between > best) {
      best = between;
      threshold = t;
    }
  }
  return threshold;
}

function median(values: number[]): number {
  const s = [...values].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)];
}

export function detectLines(source: CanvasImageSource, width: number, height: number): Box[] {
  const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
  const w = Math.max(1, Math.round(width * scale));
  const h = Math.max(1, Math.round(height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) return [{ x: 0, y: 0, w: width, h: height }];
  ctx.drawImage(source, 0, 0, w, h);
  const { data } = ctx.getImageData(0, 0, w, h);

  const gray = new Uint8Array(w * h);
  const hist = new Float64Array(256);
  let sum = 0;
  for (let i = 0; i < w * h; i++) {
    const g = (data[4 * i] * 299 + data[4 * i + 1] * 587 + data[4 * i + 2] * 114) / 1000;
    const v = g | 0;
    gray[i] = v;
    hist[v]++;
    sum += v;
  }
  const threshold = otsu(hist, w * h);
  const darkTextOnLight = sum / (w * h) >= threshold;

  const ink = new Uint8Array(w * h);
  const rows = new Float64Array(h);
  for (let y = 0; y < h; y++) {
    let count = 0;
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      const isInk = darkTextOnLight ? gray[i] < threshold : gray[i] > threshold;
      if (isInk) {
        ink[i] = 1;
        count++;
      }
    }
    rows[y] = count / w;
  }

  let maxRow = 0;
  for (let y = 0; y < h; y++) maxRow = Math.max(maxRow, rows[y]);
  const rowThreshold = Math.max(0.002, maxRow * 0.06);

  let runs: [number, number][] = [];
  let start = -1;
  for (let y = 0; y <= h; y++) {
    const on = y < h && rows[y] > rowThreshold;
    if (on && start < 0) start = y;
    if (!on && start >= 0) {
      runs.push([start, y]);
      start = -1;
    }
  }
  if (runs.length === 0) return [{ x: 0, y: 0, w: width, h: height }];

  // Gộp các mảnh gần nhau (dấu thanh, dấu mũ tách khỏi thân chữ) rồi bỏ các vệt quá mảnh.
  const m = median(runs.map(([a, b]) => b - a));
  const merged: [number, number][] = [];
  for (const run of runs) {
    const last = merged[merged.length - 1];
    if (last && run[0] - last[1] < 0.45 * m) last[1] = run[1];
    else merged.push([run[0], run[1]]);
  }
  const m2 = median(merged.map(([a, b]) => b - a));
  runs = merged.filter(([a, b]) => b - a >= 0.3 * m2).slice(0, MAX_LINES);

  const boxes: Box[] = [];
  for (const [y0, y1] of runs) {
    const runH = y1 - y0;
    let left = -1;
    let right = -1;
    for (let x = 0; x < w; x++) {
      let c = 0;
      for (let y = y0; y < y1; y++) c += ink[y * w + x];
      if (c > 0) {
        if (left < 0) left = x;
        right = x;
      }
    }
    if (left < 0) continue;
    const py = Math.round(runH * 0.14);
    const px = Math.round(runH * 0.25);
    const bx0 = Math.max(0, left - px);
    const by0 = Math.max(0, y0 - py);
    const bx1 = Math.min(w, right + 1 + px);
    const by1 = Math.min(h, y1 + py);
    boxes.push({
      x: Math.round(bx0 / scale),
      y: Math.round(by0 / scale),
      w: Math.round((bx1 - bx0) / scale),
      h: Math.round((by1 - by0) / scale),
    });
  }
  return boxes.length ? boxes : [{ x: 0, y: 0, w: width, h: height }];
}
