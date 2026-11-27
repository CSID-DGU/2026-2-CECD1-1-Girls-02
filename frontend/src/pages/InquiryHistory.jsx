import { useEffect, useState } from "react";
import { getInquiryStatus } from "../api";
import InquiryStatusBadge from "../components/InquiryStatusBadge";
import { formatDate } from "../lib/format";
import { getMyInquiries } from "../lib/storage";

export default function InquiryHistory({ onSelect, onCreate }) {
  const [items, setItems] = useState(() => getMyInquiries().map((saved) => ({ saved, status: null, error: null })));

  useEffect(() => {
    let cancelled = false;
    Promise.allSettled(getMyInquiries().map((saved) => getInquiryStatus(saved.inquiryId, saved.receiptToken)))
      .then((results) => {
        if (cancelled) return;
        setItems((current) => current.map((item, index) => ({
          ...item,
          status: results[index]?.status === "fulfilled" ? results[index].value : null,
          error: results[index]?.status === "rejected" ? results[index].reason : null,
        })));
      });
    return () => { cancelled = true; };
  }, []);

  return <main className="inquiry-page workspace">
    <div className="customer-page-heading"><div><p className="eyebrow">MY INQUIRIES</p><h1>나의 문의 내역</h1><p>이 브라우저에서 접수한 문의의 처리 상태와 최종 답변을 확인할 수 있습니다.</p></div><button className="primary" type="button" onClick={onCreate}>새 문의 작성</button></div>
    {items.length === 0
      ? <section className="empty-state panel"><span>i</span><h2>등록된 문의가 없습니다.</h2><p>궁금한 점이나 의견이 있다면 1:1 문의를 작성해 주세요.</p><button className="primary" type="button" onClick={onCreate}>첫 문의 작성</button></section>
      : <section className="inquiry-list panel" aria-label="고객 문의 목록">
        {items.map(({ saved, status, error }) => <button className="inquiry-list-item" type="button" key={saved.inquiryId} onClick={() => onSelect(saved.inquiryId)}>
          <div className="inquiry-list-top"><span className="inquiry-number">{saved.inquiryId}</span>{status ? <InquiryStatusBadge status={status.status} label={status.statusLabel} /> : <span className="inquiry-status received">{error ? "조회 실패" : "확인 중"}</span>}</div>
          <h2>{status?.title ?? saved.title}</h2>
          <div className="inquiry-meta"><span>접수 {formatDate(status?.createdAt ?? saved.createdAt)}</span>{status?.answeredAt && <span>답변 {formatDate(status.answeredAt)}</span>}</div>
          <span className="detail-arrow">상세 보기 →</span>
        </button>)}
      </section>}
  </main>;
}
