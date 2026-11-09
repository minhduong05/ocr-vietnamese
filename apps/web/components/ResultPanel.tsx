"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { EditableLine, RunStatus } from "./Workbench";
import type { OcrResponse } from "@/lib/types";
import { downloadText } from "@/lib/image";

const LOW_CONFIDENCE = 0.8;

interface Props {
  status: RunStatus;
  error: string | null;
  fileName: string | null;
  result: OcrResponse | null;
  lines: EditableLine[];
  crops: Record<string, string>;
  activeId: string | null;
  focusRequest: { id: string; n: number } | null;
  onHover: (id: string | null) => void;
  onChange: (id: string, text: string) => void;
  onRetry: () => void;
  onDismissError: () => void;
}

type Tab = "lines" | "text";

export default function ResultPanel(props: Props) {
  const { status, error, result, lines, crops, activeId } = props;
  const [tab, setTab] = useState<Tab>("lines");
  const [manualText, setManualText] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const fieldRefs = useRef<Record<string, HTMLTextAreaElement | null>>({});

  const joined = useMemo(() => lines.map((l) => l.text).join("\n"), [lines]);
  const fullText = manualText ?? joined;
  const textDiverged = manualText !== null && manualText !== joined;

  // Kết quả mới thì bỏ bản sửa toàn văn cũ.
  useEffect(() => {
    setManualText(null);
  }, [result]);

  // Bấm vào khung trên ảnh: mở tab từng dòng và đưa con trỏ vào dòng đó.
  useEffect(() => {
    if (!props.focusRequest) return;
    setTab("lines");
    const id = props.focusRequest.id;
    requestAnimationFrame(() => {
      const el = fieldRefs.current[id];
      el?.scrollIntoView({ block: "nearest", behavior: "smooth" });
      el?.focus({ preventScroll: true });
    });
  }, [props.focusRequest]);

  useEffect(() => {
    if (!toast) return;
    const t = setTimeout(() => setToast(null), 2200);
    return () => clearTimeout(t);
  }, [toast]);

  const baseName = (props.fileName ?? "ket-qua").replace(/\.[^.]+$/, "");
  const lowCount = lines.filter((l) => l.confidence < LOW_CONFIDENCE).length;
  const editedCount = lines.filter((l) => l.text !== l.original).length;
  const hasResult = status === "done" && result !== null;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(fullText);
      setToast("Đã sao chép toàn văn");
    } catch {
      setToast("Trình duyệt chặn sao chép. Hãy chọn văn bản và nhấn Ctrl+C.");
    }
  };

  const downloadJson = () => {
    if (!result) return;
    const payload = {
      ...result,
      lines: result.lines.map((l) => {
        const edited = lines.find((e) => e.id === l.id);
        return { ...l, text_edited: edited?.text ?? l.text };
      }),
      full_text: fullText,
    };
    downloadText(`${baseName}.json`, JSON.stringify(payload, null, 2), "application/json");
    setToast(`Đã tải ${baseName}.json`);
  };

  return (
    <section className="panel" aria-label="Kết quả nhận dạng">
      <div className="panel-bar">
        <div className="tabs" role="tablist" aria-label="Cách xem kết quả">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "lines"}
            className={tab === "lines" ? "on" : ""}
            onClick={() => setTab("lines")}
          >
            Từng dòng{hasResult ? ` (${lines.length})` : ""}
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "text"}
            className={tab === "text" ? "on" : ""}
            onClick={() => setTab("text")}
          >
            Toàn văn
          </button>
        </div>
        <div className="actions">
          <button type="button" className="btn small" disabled={!hasResult} onClick={copy}>
            Sao chép
          </button>
          <button
            type="button"
            className="btn small"
            disabled={!hasResult}
            onClick={() => {
              downloadText(`${baseName}.txt`, fullText);
              setToast(`Đã tải ${baseName}.txt`);
            }}
          >
            Tải TXT
          </button>
          <button type="button" className="btn small quiet" disabled={!hasResult} onClick={downloadJson}>
            Tải JSON
          </button>
        </div>
      </div>

      {error && (
        <div className="alert" role="alert">
          <p>{error}</p>
          <div>
            {status === "error" && props.fileName && (
              <button type="button" className="btn small" onClick={props.onRetry}>
                Thử lại
              </button>
            )}
            <button type="button" className="btn small quiet" onClick={props.onDismissError}>
              Ẩn thông báo
            </button>
          </div>
        </div>
      )}

      <div className="panel-body">
        {status === "idle" && !error && (
          <p className="placeholder">Văn bản nhận dạng được sẽ hiện ở đây, mỗi dòng kèm ảnh cắt để bạn đối chiếu và sửa.</p>
        )}

        {status === "running" && (
          <ul className="skeleton" aria-label="Đang nhận dạng">
            {[0.9, 0.7, 0.82, 0.6, 0.75].map((w, i) => (
              <li key={i} style={{ width: `${w * 100}%` }} />
            ))}
          </ul>
        )}

        {hasResult && lines.length === 0 && (
          <p className="placeholder">Không tìm thấy dòng chữ nào trong ảnh. Thử ảnh rõ hơn hoặc nền sáng hơn.</p>
        )}

        {hasResult && tab === "lines" && lines.length > 0 && (
          <ol className="lines">
            {lines.map((l, i) => {
              const low = l.confidence < LOW_CONFIDENCE;
              const edited = l.text !== l.original;
              return (
                <li
                  key={l.id}
                  className={`line ${l.id === activeId ? "active" : ""}`}
                  onMouseEnter={() => props.onHover(l.id)}
                  onMouseLeave={() => props.onHover(null)}
                >
                  <span className="badge" aria-hidden>
                    {i + 1}
                  </span>
                  <div className="line-main">
                    {crops[l.id] ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img className="crop" src={crops[l.id]} alt={`Ảnh cắt dòng ${i + 1}`} />
                    ) : (
                      <div className="crop crop-empty" aria-hidden />
                    )}
                    <textarea
                      ref={(el) => {
                        fieldRefs.current[l.id] = el;
                      }}
                      value={l.text}
                      rows={1}
                      spellCheck={false}
                      aria-label={`Văn bản dòng ${i + 1}`}
                      onFocus={() => props.onHover(l.id)}
                      onChange={(e) => props.onChange(l.id, e.target.value)}
                    />
                    <div className="line-meta">
                      <span
                        className={`confidence ${low ? "low" : ""}`}
                        title={low ? "Độ tin cậy thấp, nên kiểm tra lại dòng này" : "Độ tin cậy của recognizer"}
                      >
                        <span className="meter" aria-hidden>
                          <span style={{ width: `${Math.round(l.confidence * 100)}%` }} />
                        </span>
                        {Math.round(l.confidence * 100)}% tin cậy
                      </span>
                      {edited && (
                        <button type="button" className="link" onClick={() => props.onChange(l.id, l.original)}>
                          Khôi phục bản gốc
                        </button>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}

        {hasResult && tab === "text" && lines.length > 0 && (
          <div className="fulltext">
            {textDiverged && (
              <p className="hint">
                Toàn văn đang khác các dòng vì bạn đã sửa trực tiếp ở đây.{" "}
                <button type="button" className="link" onClick={() => setManualText(null)}>
                  Lấy lại từ các dòng
                </button>
              </p>
            )}
            <textarea
              value={fullText}
              spellCheck={false}
              aria-label="Toàn văn"
              onChange={(e) => setManualText(e.target.value)}
            />
          </div>
        )}
      </div>

      {hasResult && lines.length > 0 && (
        <p className="panel-foot">
          {lowCount > 0
            ? `${lowCount} dòng có độ tin cậy dưới ${LOW_CONFIDENCE * 100}%, được tô vàng để bạn kiểm tra.`
            : "Tất cả các dòng đều có độ tin cậy từ 80% trở lên."}
          {editedCount > 0 && ` Bạn đã sửa ${editedCount} dòng.`}
        </p>
      )}

      <div className="toast" role="status" aria-live="polite">
        {toast}
      </div>
    </section>
  );
}
