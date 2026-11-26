import InquiryStatusBadge from "../components/InquiryStatusBadge";

export default function InquiryDetail({ inquiry, onBack }) {
  if (!inquiry) {
    return <main className="inquiry-page workspace"><section className="empty-state panel"><span>!</span><h2>문의 정보를 찾을 수 없습니다.</h2><button className="primary" type="button" onClick={onBack}>문의 목록으로</button></section></main>;
  }

  const isAnswered = inquiry.status === "ANSWERED" && inquiry.answerContent;
  return <main className="inquiry-page workspace">
    <button className="back-button" type="button" onClick={onBack}>← 문의 목록으로</button>
    <section className="inquiry-detail panel">
      <div className="detail-heading"><div><p className="eyebrow">INQUIRY #{inquiry.id} · MOCK DEMO</p><h1>{inquiry.title}</h1></div><InquiryStatusBadge status={inquiry.status} /></div>
      <dl className="detail-meta"><div><dt>문의 유형</dt><dd>{inquiry.type}</dd></div><div><dt>이용 매장</dt><dd>{inquiry.storeName}</dd></div><div><dt>작성일</dt><dd>{inquiry.createdAt}</dd></div></dl>
      <div className="detail-section"><p className="eyebrow">QUESTION</p><h2>문의 내용</h2><p className="detail-content">{inquiry.content}</p></div>
      <div className={`answer-section ${isAnswered ? "completed" : "waiting"}`}>
        <div className="answer-heading"><div><p className="eyebrow">FINAL ANSWER</p><h2>{isAnswered ? "담당자 최종 답변" : "답변을 준비하고 있습니다."}</h2></div>{isAnswered && <time>{inquiry.answeredAt}</time>}</div>
        {isAnswered
          ? <p>{inquiry.answerContent}</p>
          : <p>담당자가 문의 내용을 확인 중입니다. 관리자 승인 전 AI 답변 초안은 고객 화면에 표시되지 않습니다.</p>}
      </div>
      <p className="mock-note">DEMO · 현재 문의와 답변은 Mock Data이며 실제 Backend 데이터를 조회하지 않습니다.</p>
    </section>
  </main>;
}
