"use client";

import { PIPELINE_STEPS, MODEL_OPTIONS, type OcrResponse, type PipelineStep } from "@/lib/types";
import type { RunStatus } from "./Workbench";

interface Props {
  status: RunStatus;
  step: PipelineStep | null;
  result: OcrResponse | null;
  lineCount: number;
}

function ms(v: number) {
  return v >= 1000 ? `${(v / 1000).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} giây` : `${v} ms`;
}

export default function PipelineStatus({ status, step, result, lineCount }: Props) {
  const current = step ? PIPELINE_STEPS.findIndex((s) => s.id === step) : -1;

  return (
    <footer className="pipeline" aria-label="Tiến trình xử lý">
      <ol>
        {PIPELINE_STEPS.map((s, i) => {
          let state = "pending";
          if (status === "done") state = "done";
          else if (status === "running") state = i < current ? "done" : i === current ? "active" : "pending";
          return (
            <li key={s.id} className={state} aria-current={state === "active" ? "step" : undefined}>
              <span className="num">{i + 1}</span>
              {s.label}
            </li>
          );
        })}
      </ol>
      {status === "done" && result && (
        <p className="timing">
          {lineCount} dòng. Tìm và ghép dòng {ms(result.timing.detection_ms)}, nhận dạng{" "}
          {ms(result.timing.recognition_ms)}, tổng {ms(result.timing.total_ms)}.{" "}
          <span className="model-name">
            {MODEL_OPTIONS.find((m) => m.id === result.model.name)?.label ?? result.model.name}
            {result.mock ? " (mô phỏng)" : ""}
          </span>
        </p>
      )}
    </footer>
  );
}
