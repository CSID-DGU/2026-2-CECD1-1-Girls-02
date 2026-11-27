import { INQUIRY_STATUS } from "../lib/constants";

/** label을 주면 그 문구를 쓴다 (고객 화면은 API의 statusLabel). */
export default function InquiryStatusBadge({ status, label }) {
  const info = INQUIRY_STATUS[status] ?? { label: status, tone: "received" };
  return <span className={`inquiry-status ${info.tone}`}>{label ?? info.label}</span>;
}
