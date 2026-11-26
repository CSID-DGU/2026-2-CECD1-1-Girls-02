import { INQUIRY_STATUS } from "../data/mockInquiries";

export default function InquiryStatusBadge({ status }) {
  const statusInfo = INQUIRY_STATUS[status] ?? { label: status, tone: "received" };
  return <span className={`inquiry-status ${statusInfo.tone}`}>{statusInfo.label}</span>;
}
