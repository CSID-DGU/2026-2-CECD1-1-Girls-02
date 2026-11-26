import InquiryStatusBadge from "../components/InquiryStatusBadge";

export default function InquiryHistory({ inquiries, onSelect, onCreate }) {
  return <main className="inquiry-page workspace">
    <div className="customer-page-heading"><div><p className="eyebrow">MY INQUIRIES · MOCK DEMO</p><h1>나의 문의 내역</h1><p>접수한 문의의 처리 상태와 최종 답변을 확인할 수 있습니다.</p></div><button className="primary" type="button" onClick={onCreate}>새 문의 작성</button></div>
    <div className="form-notice history-notice">DEMO · 아래 문의는 화면 확인을 위한 가상 데이터이며 실제 고객 정보가 아닙니다.</div>
    {inquiries.length === 0
      ? <section className="empty-state panel"><span>i</span><h2>등록된 문의가 없습니다.</h2><p>궁금한 점이나 의견이 있다면 1:1 문의를 작성해 주세요.</p><button className="primary" type="button" onClick={onCreate}>첫 문의 작성</button></section>
      : <section className="inquiry-list panel" aria-label="고객 문의 목록">
        {inquiries.map((inquiry) => <button className="inquiry-list-item" type="button" key={inquiry.id} onClick={() => onSelect(inquiry.id)}>
          <div className="inquiry-list-top"><span className="inquiry-number">#{inquiry.id}</span><InquiryStatusBadge status={inquiry.status} /></div>
          <h2>{inquiry.title}</h2>
          <div className="inquiry-meta"><span>{inquiry.type}</span><span>{inquiry.storeName}</span><span>{inquiry.createdAt}</span></div>
          <span className="detail-arrow">상세 보기 →</span>
        </button>)}
      </section>}
  </main>;
}
