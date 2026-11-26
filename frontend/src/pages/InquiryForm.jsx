import { useEffect, useMemo, useState } from "react";
import { createInquiry, getInquiryCategories, searchStores } from "../api";
import { ErrorBox } from "../components/Common";
import { addMyInquiry } from "../lib/storage";

const EMPTY_FORM = { customerName: "", type: "", level1: "", level2: "", level3: "", storeName: "", title: "", content: "", privacyConsent: false };

function validate(form) {
  const errors = {};
  if (!form.customerName.trim()) errors.customerName = "작성자 이름을 입력해 주세요.";
  if (!form.type) errors.type = "문의 유형을 선택해 주세요.";
  if (!form.title.trim()) errors.title = "문의 제목을 입력해 주세요.";
  if (!form.content.trim()) errors.content = "문의 내용을 입력해 주세요.";
  if (!form.privacyConsent) errors.privacyConsent = "개인정보 수집·이용 동의가 필요합니다.";
  return errors;
}

export default function InquiryForm({ initialContent, onCancel, onViewHistory, onOpen }) {
  const [form, setForm] = useState(() => ({ ...EMPTY_FORM, content: initialContent ?? "" }));
  const [errors, setErrors] = useState({});
  const [reference, setReference] = useState({ inquiryTypes: [], categories: [] });
  const [referenceError, setReferenceError] = useState(null);
  const [stores, setStores] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [registered, setRegistered] = useState(null);

  useEffect(() => { setForm((current) => ({ ...current, content: initialContent ?? "" })); }, [initialContent]);
  useEffect(() => { getInquiryCategories().then(setReference).catch(setReferenceError); }, []);

  // 매장 검색: 입력이 멈추면 검색한다.
  useEffect(() => {
    const handle = window.setTimeout(() => {
      searchStores({ keyword: form.storeName.trim(), size: 20 }).then((data) => setStores(data.items)).catch(() => setStores([]));
    }, 250);
    return () => window.clearTimeout(handle);
  }, [form.storeName]);

  const update = (field, value) => {
    setForm((current) => {
      const next = { ...current, [field]: value };
      if (field === "level1") { next.level2 = ""; next.level3 = ""; }
      if (field === "level2") next.level3 = "";
      return next;
    });
    setErrors((current) => ({ ...current, [field]: "" }));
  };

  const level1 = reference.categories;
  const level2 = useMemo(() => level1.find((c) => c.categoryId === form.level1)?.children ?? [], [level1, form.level1]);
  const level3 = useMemo(() => level2.find((c) => c.categoryId === form.level2)?.children ?? [], [level2, form.level2]);

  const categoryPath = () => {
    const typeName = reference.inquiryTypes.find((t) => t.code === form.type)?.name;
    const names = [
      level1.find((c) => c.categoryId === form.level1)?.name,
      level2.find((c) => c.categoryId === form.level2)?.name,
      level3.find((c) => c.categoryId === form.level3)?.name,
    ];
    return [typeName, ...names].filter(Boolean);
  };

  const submit = async (event) => {
    event.preventDefault();
    const nextErrors = validate(form);
    if (Object.keys(nextErrors).length > 0) { setErrors(nextErrors); return; }
    setSubmitting(true); setSubmitError(null);
    try {
      const created = await createInquiry({
        categoryPath: categoryPath(),
        title: form.title.trim(),
        content: form.content.trim(),
        customerName: form.customerName.trim(),
        storeName: form.storeName.trim() || null,
        privacyConsent: form.privacyConsent,
      });
      addMyInquiry({ inquiryId: created.inquiryId, receiptToken: created.receiptToken, title: form.title.trim(), createdAt: created.createdAt });
      setRegistered(created);
    } catch (caught) {
      setSubmitError(caught);
    } finally {
      setSubmitting(false);
    }
  };

  if (registered) {
    return <main className="inquiry-page workspace"><section className="completion-card panel"><span className="completion-icon">✓</span><p className="eyebrow">INQUIRY REGISTERED</p><h1>문의가 접수되었습니다.</h1><p>접수 번호는 <strong>{registered.inquiryId}</strong>입니다. 담당자가 확인한 뒤 답변을 등록하면 문의 내역에서 확인할 수 있어요.</p><p className="mock-note">조회 정보는 이 브라우저에 저장됩니다. 다른 기기에서는 문의 내역이 보이지 않아요.</p><div className="form-actions centered"><button className="secondary" type="button" onClick={() => { setRegistered(null); setForm(EMPTY_FORM); }}>새 문의 작성</button><button className="secondary" type="button" onClick={onViewHistory}>문의 내역 보기</button><button className="primary" type="button" onClick={() => onOpen(registered.inquiryId)}>처리 상태 보기</button></div></section></main>;
  }

  return <main className="inquiry-page workspace">
    <div className="customer-page-heading"><div><p className="eyebrow">1:1 INQUIRY</p><h1>고객 1:1 문의</h1><p>문의 내용을 남겨 주시면 담당자가 확인한 뒤 답변합니다.</p></div></div>
    <form className="inquiry-form panel" onSubmit={submit} noValidate>
      <ErrorBox error={referenceError} />
      <div className="form-grid">
        <label className="form-field">작성자 이름 <span>*</span><input value={form.customerName} onChange={(event) => update("customerName", event.target.value)} maxLength={50} placeholder="이름을 입력해 주세요" aria-invalid={Boolean(errors.customerName)} />{errors.customerName && <small className="field-error">{errors.customerName}</small>}</label>
        <label className="form-field">문의 유형 <span>*</span><select value={form.type} onChange={(event) => update("type", event.target.value)} aria-invalid={Boolean(errors.type)}><option value="">선택해 주세요</option>{reference.inquiryTypes.map((type) => <option key={type.code} value={type.code}>{type.name}</option>)}</select>{errors.type && <small className="field-error">{errors.type}</small>}</label>
        <div className="form-field full">문의 분류 (선택)
          <div className="category-selects">
            <select value={form.level1} onChange={(event) => update("level1", event.target.value)} aria-label="대분류"><option value="">대분류</option>{level1.map((c) => <option key={c.categoryId} value={c.categoryId}>{c.name}</option>)}</select>
            <select value={form.level2} onChange={(event) => update("level2", event.target.value)} aria-label="중분류" disabled={!level2.length}><option value="">중분류</option>{level2.map((c) => <option key={c.categoryId} value={c.categoryId}>{c.name}</option>)}</select>
            <select value={form.level3} onChange={(event) => update("level3", event.target.value)} aria-label="소분류" disabled={!level3.length}><option value="">소분류</option>{level3.map((c) => <option key={c.categoryId} value={c.categoryId}>{c.name}</option>)}</select>
          </div>
        </div>
        <label className="form-field full">이용 매장 (선택)<input list="store-options" value={form.storeName} onChange={(event) => update("storeName", event.target.value)} maxLength={100} placeholder="매장명 또는 매장 코드로 검색" /><datalist id="store-options">{stores.map((store) => <option key={store.storeCode} value={store.storeName}>{store.isActive ? store.storeCode : `${store.storeCode} · 폐점`}</option>)}</datalist></label>
        <label className="form-field full">문의 제목 <span>*</span><input value={form.title} onChange={(event) => update("title", event.target.value)} maxLength={200} placeholder="문의 제목을 입력해 주세요" aria-invalid={Boolean(errors.title)} />{errors.title && <small className="field-error">{errors.title}</small>}</label>
        <label className="form-field full">문의 내용 <span>*</span><textarea value={form.content} onChange={(event) => update("content", event.target.value)} rows="8" maxLength={5000} placeholder="문의 내용을 자세히 입력해 주세요. 주문번호·연락처 등 개인정보는 적지 않아도 됩니다." aria-invalid={Boolean(errors.content)} />{errors.content && <small className="field-error">{errors.content}</small>}<small className="field-count">{form.content.length}자</small></label>
      </div>
      <label className="privacy-agreement"><input type="checkbox" checked={form.privacyConsent} onChange={(event) => update("privacyConsent", event.target.checked)} /><span><strong>개인정보 수집·이용에 동의합니다. (필수)</strong><small>문의 처리 목적으로 작성자 이름과 문의 내용을 수집합니다. AI 처리 시 연락처 등 개인정보는 가려서 전달됩니다.</small></span></label>
      {errors.privacyConsent && <p className="field-error agreement-error">{errors.privacyConsent}</p>}
      <ErrorBox error={submitError} />
      <div className="form-actions"><button className="secondary" type="button" onClick={onCancel}>취소</button><button className="primary" type="submit" disabled={submitting}>{submitting ? "등록 중..." : "문의 등록"}</button></div>
    </form>
  </main>;
}
