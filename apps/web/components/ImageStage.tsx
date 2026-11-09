"use client";

import { useState } from "react";
import type { OcrResponse, PipelineStep } from "@/lib/types";
import { boundsOf } from "@/lib/image";
import { SAMPLES } from "@/lib/samples";

interface Props {
  imageUrl: string | null;
  fileName: string | null;
  result: OcrResponse | null;
  busy: boolean;
  step: PipelineStep | null;
  showBoxes: boolean;
  onToggleBoxes: () => void;
  activeId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
  onFile: (file: File) => void;
  onPickFile: () => void;
  onSample: (id: string) => void;
}

export default function ImageStage(props: Props) {
  const { imageUrl, result, busy, step, showBoxes, activeId } = props;
  const [dragging, setDragging] = useState(false);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) props.onFile(f);
  };

  const dims = result?.image;
  const scanning = busy && (step === "detect" || step === "group");

  return (
    <section
      className={`stage ${dragging ? "is-dragging" : ""}`}
      aria-label="Ảnh đầu vào"
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false);
      }}
      onDrop={onDrop}
    >
      <div className="stage-bar">
        <span className="stage-title">{props.fileName ?? "Chưa có ảnh"}</span>
        {result && (
          <label className="toggle">
            <input type="checkbox" checked={showBoxes} onChange={props.onToggleBoxes} />
            Hiện khung dòng
          </label>
        )}
      </div>

      <div className="paper">
        {!imageUrl ? (
          <div className="empty">
            <h2>Thả ảnh đoạn văn vào đây</h2>
            <p>Hoặc dán ảnh bằng Ctrl+V, chọn tệp từ máy, hay thử một ảnh mẫu. Hỗ trợ JPG, PNG, WEBP, tối đa 10 MB.</p>
            <div className="empty-actions">
              <button type="button" className="btn primary" onClick={props.onPickFile}>
                Chọn ảnh từ máy
              </button>
              {SAMPLES.map((s) => (
                <button key={s.id} type="button" className="btn" onClick={() => props.onSample(s.id)}>
                  Thử ảnh “{s.label}”
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="figure">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={imageUrl} alt="Ảnh đoạn văn cần nhận dạng" draggable={false} />
            {scanning && <div className="scan" aria-hidden />}
            {dims && showBoxes && (
              <>
                <svg
                  className="boxes"
                  viewBox={`0 0 ${dims.width} ${dims.height}`}
                  preserveAspectRatio="none"
                  aria-hidden
                >
                  {result!.lines.map((l) => (
                    <polygon
                      key={l.id}
                      points={l.polygon.map((p) => p.join(",")).join(" ")}
                      className={l.id === activeId ? "active" : ""}
                      vectorEffect="non-scaling-stroke"
                    />
                  ))}
                </svg>
                {result!.lines.map((l, i) => {
                  const b = boundsOf(l.polygon);
                  return (
                    <button
                      key={l.id}
                      type="button"
                      className={`box-hit ${l.id === activeId ? "active" : ""}`}
                      style={{
                        left: `${(b.x / dims.width) * 100}%`,
                        top: `${(b.y / dims.height) * 100}%`,
                        width: `${(b.w / dims.width) * 100}%`,
                        height: `${(b.h / dims.height) * 100}%`,
                      }}
                      aria-label={`Dòng ${i + 1}: ${l.text}`}
                      onMouseEnter={() => props.onHover(l.id)}
                      onMouseLeave={() => props.onHover(null)}
                      onClick={() => props.onSelect(l.id)}
                    >
                      <span className="badge">{i + 1}</span>
                    </button>
                  );
                })}
              </>
            )}
          </div>
        )}
      </div>
      {dragging && <div className="drop-hint">Thả ảnh để nhận dạng</div>}
    </section>
  );
}
