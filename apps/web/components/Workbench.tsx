"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import ImageStage from "./ImageStage";
import ResultPanel from "./ResultPanel";
import PipelineStatus from "./PipelineStatus";
import { IS_MOCK, OCR_API_URL, runOcr } from "@/lib/ocrClient";
import { cropLines, validateImage } from "@/lib/image";
import { SAMPLES, loadSampleFile } from "@/lib/samples";
import {
  MODE_OPTIONS,
  MODEL_OPTIONS,
  type OcrMode,
  type OcrModel,
  type OcrResponse,
  type PipelineStep,
} from "@/lib/types";

export type RunStatus = "idle" | "running" | "done" | "error";

export interface EditableLine {
  id: string;
  original: string;
  text: string;
  confidence: number;
}

export default function Workbench() {
  const [file, setFile] = useState<File | null>(null);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [mode, setMode] = useState<OcrMode>("printed");
  const [model, setModel] = useState<OcrModel>("crnn");
  const [status, setStatus] = useState<RunStatus>("idle");
  const [step, setStep] = useState<PipelineStep | null>(null);
  const [result, setResult] = useState<OcrResponse | null>(null);
  const [lines, setLines] = useState<EditableLine[]>([]);
  const [crops, setCrops] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [focusRequest, setFocusRequest] = useState<{ id: string; n: number } | null>(null);
  const [showBoxes, setShowBoxes] = useState(true);
  const [lastRun, setLastRun] = useState<{ mode: OcrMode; model: OcrModel } | null>(null);
  const runId = useRef(0);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    return () => {
      if (imageUrl) URL.revokeObjectURL(imageUrl);
    };
  }, [imageUrl]);

  const recognize = useCallback(
    async (target: File, url: string, m: OcrMode, mdl: OcrModel) => {
      const id = ++runId.current;
      setStatus("running");
      setError(null);
      setResult(null);
      setLines([]);
      setCrops({});
      setActiveId(null);
      try {
        const res = await runOcr({ file: target, mode: m, model: mdl }, (s) => {
          if (runId.current === id) setStep(s);
        });
        if (runId.current !== id) return;
        setResult(res);
        setLines(
          res.lines.map((l) => ({
            id: l.id,
            original: l.text.normalize("NFC"),
            text: l.text.normalize("NFC"),
            confidence: l.confidence,
          })),
        );
        setLastRun({ mode: m, model: mdl });
        setStatus("done");
        setStep(null);
        cropLines(url, res.lines)
          .then((c) => runId.current === id && setCrops(c))
          .catch(() => undefined);
      } catch (e) {
        if (runId.current !== id) return;
        setError(e instanceof Error ? e.message : String(e));
        setStatus("error");
        setStep(null);
      }
    },
    [],
  );

  const acceptFile = useCallback(
    (next: File, nextMode?: OcrMode) => {
      const problem = validateImage(next);
      if (problem) {
        setError(problem);
        if (!file) setStatus("error");
        return;
      }
      const url = URL.createObjectURL(next);
      setFile(next);
      setImageUrl(url);
      const m = nextMode ?? mode;
      if (nextMode) setMode(nextMode);
      void recognize(next, url, m, model);
    },
    [file, mode, model, recognize],
  );

  // Dán ảnh bằng Ctrl+V ở bất kỳ đâu trên trang.
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const item = Array.from(e.clipboardData?.items ?? []).find((i) => i.type.startsWith("image/"));
      const pasted = item?.getAsFile();
      if (!pasted) return;
      e.preventDefault();
      const ext = pasted.type.split("/")[1] || "png";
      acceptFile(new File([pasted], `anh-dan.${ext}`, { type: pasted.type }));
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [acceptFile]);

  const pickSample = async (sampleId: string) => {
    const sample = SAMPLES.find((s) => s.id === sampleId);
    if (!sample) return;
    try {
      acceptFile(await loadSampleFile(sample), sample.mode);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const updateLine = (id: string, text: string) =>
    setLines((prev) => prev.map((l) => (l.id === id ? { ...l, text } : l)));

  const selectFromImage = (id: string) => {
    setActiveId(id);
    setFocusRequest((prev) => ({ id, n: (prev?.n ?? 0) + 1 }));
  };

  const settingsChanged =
    status === "done" && lastRun !== null && (lastRun.mode !== mode || lastRun.model !== model);
  const busy = status === "running";

  return (
    <div className="app">
      <header className="masthead">
        <div className="brand">
          <h1>OCR tiếng Việt</h1>
          <p>Nhận dạng đoạn văn chữ in và chữ viết tay. Nhóm 11, môn Học sâu và Ứng dụng.</p>
        </div>
        <div
          className={`connection ${IS_MOCK ? "is-mock" : "is-live"}`}
          title={
            IS_MOCK
              ? "Chưa cấu hình NEXT_PUBLIC_OCR_API_URL. Khung dòng được tìm bằng thuật toán đơn giản trên trình duyệt, văn bản là dữ liệu giữ chỗ."
              : `Đang gọi máy chủ OCR tại ${OCR_API_URL}`
          }
        >
          <span className="dot" aria-hidden />
          {IS_MOCK ? "Chế độ mô phỏng, chưa nối model" : `Máy chủ: ${OCR_API_URL.replace(/^https?:\/\//, "")}`}
        </div>
      </header>

      <section className="controls" aria-label="Thiết lập nhận dạng">
        <div className="control-group">
          <button type="button" className="btn" onClick={() => fileInput.current?.click()} disabled={busy}>
            Chọn ảnh từ máy
          </button>
          <input
            ref={fileInput}
            type="file"
            accept="image/jpeg,image/png,image/webp,image/bmp"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) acceptFile(f);
              e.target.value = "";
            }}
          />
          <label className="field">
            <span>Ảnh mẫu</span>
            <select
              value=""
              disabled={busy}
              onChange={(e) => {
                if (e.target.value) void pickSample(e.target.value);
              }}
            >
              <option value="">Chọn ảnh mẫu…</option>
              {SAMPLES.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="control-group">
          <div className="segmented" role="radiogroup" aria-label="Kiểu chữ">
            {MODE_OPTIONS.map((o) => (
              <button
                key={o.id}
                type="button"
                role="radio"
                aria-checked={mode === o.id}
                className={mode === o.id ? "on" : ""}
                onClick={() => setMode(o.id)}
                disabled={busy}
              >
                {o.label}
              </button>
            ))}
          </div>
          <label className="field">
            <span>Mô hình</span>
            <select value={model} onChange={(e) => setModel(e.target.value as OcrModel)} disabled={busy}>
              {MODEL_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            className="btn primary"
            disabled={!file || !imageUrl || busy}
            onClick={() => file && imageUrl && recognize(file, imageUrl, mode, model)}
          >
            {busy ? "Đang nhận dạng…" : status === "done" ? "Nhận dạng lại" : "Nhận dạng"}
          </button>
        </div>
      </section>

      {settingsChanged && (
        <p className="hint" role="status">
          Bạn đã đổi kiểu chữ hoặc mô hình. Bấm “Nhận dạng lại” để áp dụng.
        </p>
      )}

      <main className="workspace">
        <ImageStage
          imageUrl={imageUrl}
          fileName={file?.name ?? null}
          result={result}
          busy={busy}
          step={step}
          showBoxes={showBoxes}
          onToggleBoxes={() => setShowBoxes((v) => !v)}
          activeId={activeId}
          onHover={setActiveId}
          onSelect={selectFromImage}
          onFile={acceptFile}
          onPickFile={() => fileInput.current?.click()}
          onSample={pickSample}
        />
        <ResultPanel
          status={status}
          error={error}
          fileName={file?.name ?? null}
          result={result}
          lines={lines}
          crops={crops}
          activeId={activeId}
          focusRequest={focusRequest}
          onHover={setActiveId}
          onChange={updateLine}
          onRetry={() => file && imageUrl && recognize(file, imageUrl, mode, model)}
          onDismissError={() => setError(null)}
        />
      </main>

      <PipelineStatus status={status} step={step} result={result} lineCount={lines.length} />
    </div>
  );
}
