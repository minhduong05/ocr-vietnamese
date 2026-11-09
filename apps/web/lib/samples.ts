import type { OcrMode } from "./types";

export interface SampleImage {
  id: string;
  file: string;
  label: string;
  mode: OcrMode;
  /** Văn bản đúng của ảnh mẫu; bộ mô phỏng dùng nó làm "kết quả nhận dạng". */
  lines: string[];
}

export const SAMPLES: SampleImage[] = [
  {
    id: "truyen-kieu",
    file: "truyen-kieu.png",
    label: "Truyện Kiều",
    mode: "printed",
    lines: [
      "Truyện Kiều",
      "Trăm năm trong cõi người ta,",
      "Chữ tài chữ mệnh khéo là ghét nhau.",
      "Trải qua một cuộc bể dâu,",
      "Những điều trông thấy mà đau đớn lòng.",
      "Lạ gì bỉ sắc tư phong,",
      "Trời xanh quen thói má hồng đánh ghen.",
      "Cảo thơm lần giở trước đèn,",
      "Phong tình cổ lục còn truyền sử xanh.",
    ],
  },
  {
    id: "thong-bao",
    file: "thong-bao.jpg",
    label: "Ảnh chụp thông báo",
    mode: "printed",
    lines: [
      "THÔNG BÁO",
      "Lịch bảo vệ bài tập lớn môn Học sâu và Ứng dụng",
      "Thời gian: 8 giờ 30, thứ Sáu ngày 18/12/2026",
      "Địa điểm: phòng 402, nhà D3",
      "Mỗi nhóm trình bày 15 phút và trả lời câu hỏi.",
      "Đề nghị các nhóm nộp mã nguồn trước 23 giờ ngày 16/12.",
    ],
  },
];

export async function loadSampleFile(sample: SampleImage): Promise<File> {
  const res = await fetch(`/samples/${sample.file}`);
  if (!res.ok) throw new Error(`Không tải được ảnh mẫu ${sample.file}`);
  const blob = await res.blob();
  return new File([blob], sample.file, { type: blob.type || "image/png" });
}
