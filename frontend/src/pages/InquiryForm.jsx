import { useEffect, useState } from "react";
import { INQUIRY_TYPES, STORE_OPTIONS } from "../data/mockInquiries";

const EMPTY_FORM = { customerName: "", type: "", storeName: "", title: "", content: "", privacyAgreed: false };

function validate(form) {
  const errors = {};
  if (!form.customerName.trim()) errors.customerName = "작성자 이름을 입력해 주세요.";
  if (!form.type) errors.type = "문의 유형을 선택해 주세요.";
  if (!form.storeName) errors.storeName = "이용 매장을 선택해 주세요.";
  if (!form.title.trim()) errors.title = "문의 제목을 입력해 주세요.";
  if (!form.content.trim()) errors.content = "문의 내용을 입력해 주세요.";
  if (!form.privacyAgreed) errors.privacyAgreed = "개인정보 수집·이용 동의가 필요합니다.";
  return errors;
}

export default function InquiryForm({ initialContent, onRegister, onCancel, onViewHistory }) {
  const [form, setForm] = useState(() => ({ ...EMPTY_FORM, content: initialContent ?? "" }));
  const [errors, setErrors] = useState({});
  const [registeredInquiry, setRegisteredInquiry] = useState(null);

  useEffect(() => { setForm((current) => ({ ...current, content: initialContent ?? "" })); }, [initialContent]);
  const update = (field, value) => { setForm((current) => ({ ...current, [field]: value })); setErrors((current) => ({ ...current, [field]: "" })); };

  const submit = (event) => {
    event.preventDefault();
    const nextErrors = validate(form);
    if (Object.keys(nextErrors).length > 0) { setErrors(nextErrors); return; }
    setRegisteredInquiry(onRegister(form));
  };

  if (registeredInquiry) {
    return <main className="inquiry-page workspace"><section className="completion-card panel"><span className="completion-icon">✓</span><p className="eyebrow">MOCK INQUIRY REGISTERED</p><h1>문의가 등록되었습니다.</h1><p>데모 접수 번호는 <strong>#{registeredInquiry.id}</strong>입니다. 현재 데이터는 브라우저 메모리에만 저장됩니다.</p><div className="form-actions centered"><button className="secondary" type="button" onClick={() => { setRegisteredInquiry(null); setForm(EMPTY_FORM); }}>새 문의 작성</button><button className="primary" type="button" onClick={onViewHistory}>문의 내역 보기</button></div></section></main>;
  }

  return <main className="inquiry-page workspace">
    <div className="customer-page-heading"><div><p className="eyebrow">1:1 INQUIRY · MOCK DEMO</p><h1>고객 1:1 문의</h1><p>문의 내용을 남겨 주시면 담당자가 확인한 뒤 답변합니다.</p></div><span className="demo-badge inline">MOCK DATA</span></div>
    <form className="inquiry-form panel" onSubmit={submit} noValidate>
      <div className="form-notice">DEMO · 문의 등록 API를 호출하지 않으며 입력 내용은 새로고침하면 사라집니다.</div>
      <div className="form-grid">
        <label className="form-field">작성자 이름 <span>*</span><input value={form.customerName} onChange={(event) => update("customerName", event.target.value)} placeholder="이름을 입력해 주세요" aria-invalid={Boolean(errors.customerName)} />{errors.customerName && <small className="field-error">{errors.customerName}</small>}</label>
        <label className="form-field">문의 유형 <span>*</span><select value={form.type} onChange={(event) => update("type", event.target.value)} aria-invalid={Boolean(errors.type)}><option value="">선택해 주세요</option>{INQUIRY_TYPES.map((type) => <option key={type}>{type}</option>)}</select>{errors.type && <small className="field-error">{errors.type}</small>}</label>
        <label className="form-field full">이용 매장 <span>*</span><select value={form.storeName} onChange={(event) => update("storeName", event.target.value)} aria-invalid={Boolean(errors.storeName)}><option value="">선택해 주세요</option>{STORE_OPTIONS.map((store) => <option key={store}>{store}</option>)}</select>{errors.storeName && <small className="field-error">{errors.storeName}</small>}</label>
        <label className="form-field full">문의 제목 <span>*</span><input value={form.title} onChange={(event) => update("title", event.target.value)} maxLength="200" placeholder="문의 제목을 입력해 주세요" aria-invalid={Boolean(errors.title)} />{errors.title && <small className="field-error">{errors.title}</small>}</label>
        <label className="form-field full">문의 내용 <span>*</span><textarea value={form.content} onChange={(event) => update("content", event.target.value)} rows="8" placeholder="문의 내용을 자세히 입력해 주세요" aria-invalid={Boolean(errors.content)} />{errors.content && <small className="field-error">{errors.content}</small>}<small className="field-count">{form.content.length}자</small></label>
      </div>
      <label className="privacy-agreement"><input type="checkbox" checked={form.privacyAgreed} onChange={(event) => update("privacyAgreed", event.target.checked)} /><span><strong>개인정보 수집·이용에 동의합니다. (필수)</strong><small>문의 처리 목적으로 작성자 이름과 문의 내용을 수집하는 데 동의합니다.</small></span></label>
      {errors.privacyAgreed && <p className="field-error agreement-error">{errors.privacyAgreed}</p>}
      <div className="form-actions"><button className="secondary" type="button" onClick={onCancel}>취소</button><button className="primary" type="submit">문의 등록</button></div>
    </form>
  </main>;
}
