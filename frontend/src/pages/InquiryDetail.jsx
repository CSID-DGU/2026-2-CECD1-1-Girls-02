import { useEffect, useState } from "react";
import { getInquiryStatus } from "../api";
import { ErrorBox, Loading } from "../components/Common";
import InquiryStatusBadge from "../components/InquiryStatusBadge";
import { formatDateTime } from "../lib/format";
import { getMyInquiries } from "../lib/storage";

const TYPE_LABELS = { QUESTION: "문의", SUGGESTION: "제안", COMPLIMENT: "칭찬", COMPLAINT: "불만" };

export default function InquiryDetail({ inquiryId, onBack }) {
  const saved = getMyInquiries().find((item) => item.inquiryId === inquiryId);
  const [inquiry, setInquiry] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!saved) return;
    getInquiryStatus(saved.inquiryId, saved.receiptToken).then(setInquiry).catch(setError);
  }, [inquiryId]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!saved) {
    return <main className="inquiry-page workspace"><section className="empty-state panel"><span>!</span><h2>문의 정보를 찾을 수 없습니다.</h2><p>이 브라우저에서 접수한 문의만 조회할 수 있어요.</p><button className="primary" type="button" onClick={onBack}>문의 목록으로</button></section></main>;
  }

  const isAnswered = Boolean(inquiry?.finalAnswer);
  return <main className="inquiry-page workspace">
    <button className="back-button" type="button" onClick={onBack}>← 문의 목록으로</button>
    <section className="inquiry-detail panel">
      <ErrorBox error={error} />
      {!inquiry && !error && <Loading />}
      {inquiry && <>
        <div className="detail-heading"><div><p className="eyebrow">INQUIRY {inquiry.inquiryId}</p><h1>{inquiry.title}</h1></div><InquiryStatusBadge status={inquiry.status} label={inquiry.statusLabel} /></div>
        <dl className="detail-meta"><div><dt>문의 유형</dt><dd>{TYPE_LABELS[inquiry.inquiryType] ?? inquiry.inquiryType}</dd></div><div><dt>접수 일시</dt><dd>{formatDateTime(inquiry.createdAt)}</dd></div><div><dt>처리 상태</dt><dd>{inquiry.statusLabel}</dd></div></dl>
        <div className={`answer-section ${isAnswered ? "completed" : "waiting"}`}>
          <div className="answer-heading"><div><p className="eyebrow">FINAL ANSWER</p><h2>{isAnswered ? "담당자 최종 답변" : "답변을 준비하고 있습니다."}</h2></div>{inquiry.answeredAt && <time>{formatDateTime(inquiry.answeredAt)}</time>}</div>
          {isAnswered ? <p>{inquiry.finalAnswer}</p> : <p>담당자가 문의 내용을 확인 중입니다. 관리자 승인 전 AI 답변 초안은 고객 화면에 표시되지 않습니다.</p>}
        </div>
      </>}
    </section>
  </main>;
}
