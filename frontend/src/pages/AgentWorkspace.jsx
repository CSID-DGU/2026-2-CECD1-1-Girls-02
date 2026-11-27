import { useCallback, useEffect, useState } from "react";
import {
  approveAnswer, changeInquiryStatus, createInquiryAiDraft, getAdminInquiry, getInquiryCategories, listAdminInquiries, saveDraft,
} from "../api";
import { ErrorBox, Loading, Pagination, SourceList } from "../components/Common";
import InquiryStatusBadge from "../components/InquiryStatusBadge";
import { ALLOWED_TRANSITIONS, INQUIRY_STATUS, REVIEWABLE, TRANSITION_LABELS, flattenCategories } from "../lib/constants";
import { formatDateTime } from "../lib/format";

const PAGE_SIZE = 20;

function InquiryList({ filters, onFilters, result, selectedId, onSelect, categories, error }) {
  const totalPages = result ? Math.max(1, Math.ceil(result.total / result.pageSize)) : 0;
  return <aside className="ticket-nav">
    <div className="ticket-nav-head"><p className="eyebrow">INQUIRIES</p><h2>문의 목록</h2></div>
    <div className="filter-group">
      <select value={filters.status} onChange={(event) => onFilters({ ...filters, status: event.target.value, page: 1 })} aria-label="상태 필터">
        <option value="">전체 상태</option>{Object.entries(INQUIRY_STATUS).map(([code, info]) => <option key={code} value={code}>{info.label}</option>)}
      </select>
      <select value={filters.category} onChange={(event) => onFilters({ ...filters, category: event.target.value, page: 1 })} aria-label="분류 필터">
        <option value="">전체 분류</option>{categories.map((c) => <option key={c.categoryId} value={c.categoryId}>{"· ".repeat(c.depth - 1)}{c.name}</option>)}
      </select>
    </div>
    <ErrorBox error={error} />
    {!result && !error && <Loading />}
    {result && <p className="mock-note">총 {result.total}건</p>}
    <div className="ticket-list">
      {result?.items.map((item) => <button key={item.inquiryId} type="button" className={`ticket-item ${selectedId === item.inquiryId ? "selected" : ""}`} onClick={() => onSelect(item.inquiryId)}>
        <span>{item.inquiryId} · {formatDateTime(item.createdAt)}</span>
        <strong>{item.title}</strong>
        <small>{item.categoryPath.join(" > ") || "분류 없음"}</small>
        <InquiryStatusBadge status={item.status} />
      </button>)}
    </div>
    {result && <Pagination page={result.page} totalPages={totalPages} onChange={(page) => onFilters({ ...filters, page })} />}
  </aside>;
}

function InquiryPanel({ inquiryId, onChanged }) {
  const [detail, setDetail] = useState(null);
  const [answerText, setAnswerText] = useState("");
  const [memo, setMemo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setError(null);
    try {
      const data = await getAdminInquiry(inquiryId);
      setDetail(data);
      setAnswerText(data.draft.answerText ?? "");
    } catch (caught) { setError(caught); }
  }, [inquiryId]);

  useEffect(() => { setDetail(null); setNotice(""); setMemo(""); load(); }, [load]);

  const run = async (action, successMessage) => {
    setBusy(true); setError(null); setNotice("");
    try {
      await action();
      setNotice(successMessage);
      await load();
      onChanged();
    } catch (caught) { setError(caught); } finally { setBusy(false); }
  };

  if (!detail) return <section className="agent-content">{error ? <ErrorBox error={error} /> : <Loading />}</section>;

  const editable = REVIEWABLE.includes(detail.status);
  const transitions = ALLOWED_TRANSITIONS[detail.status] ?? [];
  return <section className="agent-content">
    <div className="ticket-header"><div><p className="eyebrow">INQUIRY {detail.inquiryId}</p><h1>{detail.title}</h1><p>{formatDateTime(detail.createdAt)} 접수 · 최근 변경 {formatDateTime(detail.updatedAt)}</p></div><InquiryStatusBadge status={detail.status} /></div>
    <div className="agent-grid">
      <section className="ticket-detail panel">
        <div className="section-title"><span className="step">1</span><div><h3>문의 내용</h3><p>연락처 등 민감 정보는 표시하지 않습니다.</p></div></div>
        <dl className="detail-meta compact"><div><dt>고객</dt><dd>{detail.customerName}</dd></div><div><dt>매장</dt><dd>{detail.storeName ?? "-"}</dd></div><div><dt>분류</dt><dd>{detail.categoryPath.join(" > ") || "-"}</dd></div></dl>
        <blockquote>{detail.content}</blockquote>
        {(detail.summary || detail.categorySuggestion) && <div className="ai-hint"><strong>AI 요약</strong><p>{detail.summary ?? "-"}</p>{detail.categorySuggestion && <small>분류 제안: {detail.categorySuggestion.join(" > ")}</small>}</div>}
        <div className="section-title evidence-title"><span className="step">2</span><div><h3>초안 근거</h3><p>AI가 답변 초안에 인용한 공식 문서입니다.</p></div></div>
        <SourceList sources={detail.draft.sources} emptyText={detail.status === "DRAFT_GENERATING" ? "AI 초안을 생성하고 있습니다." : "인용된 공식 근거가 없습니다. 담당자 확인이 필요한 문의입니다."} />
      </section>
      <section className="draft-panel panel">
        <div className="section-title"><span className="step">3</span><div><h3>답변 작성</h3><p>AI 초안을 수정하거나 직접 작성한 뒤 승인하면 고객에게 공개됩니다.</p></div></div>
        <textarea value={answerText} onChange={(event) => setAnswerText(event.target.value)} readOnly={!editable} maxLength={5000} placeholder={detail.status === "DRAFT_GENERATING" ? "AI 초안 생성이 끝나면 수정할 수 있습니다." : "고객에게 보낼 답변을 작성해 주세요."} aria-label="답변 초안" />
        <div className="draft-actions">
          {editable && <>
            <button className="secondary" type="button" disabled={busy || !answerText.trim()} onClick={() => run(() => saveDraft(detail.inquiryId, answerText.trim()), "초안을 저장했습니다.")}>초안 저장</button>
            <button className="primary" type="button" disabled={busy || !answerText.trim()} onClick={() => run(() => approveAnswer(detail.inquiryId, answerText.trim()), "답변을 등록했습니다. 고객 화면에 공개됩니다.")}>답변 승인·등록</button>
          </>}
          {detail.status === "DRAFT_GENERATING" && <>
            <button className="secondary" type="button" disabled={busy} onClick={() => run(() => createInquiryAiDraft(detail.inquiryId), "AI 초안 생성을 다시 실행했습니다.")}>AI 초안 다시 실행</button>
            <button className="secondary" type="button" disabled={busy} onClick={load}>새로고침</button>
          </>}
        </div>
        {transitions.length > 0 && <div className="status-actions">
          <input value={memo} onChange={(event) => setMemo(event.target.value)} maxLength={1000} placeholder="내부 메모 (선택)" aria-label="내부 메모" />
          {transitions.map((target) => <button key={target} className="secondary" type="button" disabled={busy} onClick={() => run(() => changeInquiryStatus(detail.inquiryId, target, memo.trim()), `상태를 '${INQUIRY_STATUS[target].label}'(으)로 변경했습니다.`)}>{TRANSITION_LABELS[target]}</button>)}
        </div>}
        <ErrorBox error={error} />
        {notice && <p className="demo-toast" role="status">{notice}</p>}
      </section>
    </div>
  </section>;
}

export default function AgentWorkspace() {
  const [filters, setFilters] = useState({ status: "", category: "", page: 1 });
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [categories, setCategories] = useState([]);
  const [version, setVersion] = useState(0);

  useEffect(() => { getInquiryCategories().then((data) => setCategories(flattenCategories(data.categories))).catch(() => {}); }, []);
  useEffect(() => {
    let cancelled = false;
    setError(null);
    listAdminInquiries({ ...filters, pageSize: PAGE_SIZE })
      .then((data) => {
        if (cancelled) return;
        setResult(data);
        setSelectedId((current) => current ?? data.items[0]?.inquiryId ?? null);
      })
      .catch((caught) => { if (!cancelled) setError(caught); });
    return () => { cancelled = true; };
  }, [filters, version]);

  return <main className="agent-layout">
    <InquiryList filters={filters} onFilters={setFilters} result={result} selectedId={selectedId} onSelect={setSelectedId} categories={categories} error={error} />
    {selectedId
      ? <InquiryPanel key={selectedId} inquiryId={selectedId} onChanged={() => setVersion((v) => v + 1)} />
      : <section className="agent-content"><div className="empty-state panel"><span>i</span><h2>처리할 문의가 없습니다.</h2><p>고객이 1:1 문의를 등록하면 여기에 표시됩니다.</p></div></section>}
  </main>;
}
