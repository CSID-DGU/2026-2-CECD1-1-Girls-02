import { useState } from "react";
import { ApiError, createInquiryAiDraft } from "../api";

export default function AgentWorkspace() {
  const [inquiryId, setInquiryId] = useState(import.meta.env.VITE_DEMO_INQUIRY_ID ?? "");
  const [draft, setDraft] = useState("");
  const [result, setResult] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");

  const generateAiDraft = async () => {
    const parsedId = Number(inquiryId);
    setError(""); setResult(null); setDraft("");
    if (!Number.isInteger(parsedId) || parsedId <= 0) { setError("AI 처리를 실행할 DB 문의 ID를 입력해 주세요."); return; }
    setIsGenerating(true);
    try {
      const nextResult = await createInquiryAiDraft(parsedId);
      setResult(nextResult);
      setDraft(nextResult.draft_text ?? `자동 답변을 생성하지 않았습니다.\n\n이관 사유: ${nextResult.escalation_reason ?? "공식 근거 또는 업무 규칙을 확인해 주세요."}`);
    } catch (caughtError) {
      setError(caughtError instanceof ApiError ? caughtError.message : "서버에 연결하지 못했습니다. FastAPI 실행 상태를 확인해 주세요.");
    } finally { setIsGenerating(false); }
  };

  const actionLabel = result?.action === "DRAFT_FOR_REVIEW" ? "답변 초안 생성" : result ? "상담원 이관 필요" : "AI 처리 전";
  return <main className="agent-layout">
    <aside className="ticket-nav"><div className="ticket-nav-head"><p className="eyebrow">INQUIRY SELECT</p><h2>문의 선택</h2></div><label className="inquiry-id-field">문의 ID<input value={inquiryId} onChange={(event) => setInquiryId(event.target.value)} inputMode="numeric" placeholder="예: 1" aria-label="처리할 문의 ID" /></label><p className="mock-note">현재 문의 목록 API는 아직 없습니다. PostgreSQL에 저장된 문의 ID를 직접 입력해 AI 처리를 검증합니다.</p></aside>
    <section className="agent-content">
      <div className="ticket-header"><div><p className="eyebrow">INQUIRY {inquiryId || "-"}</p><h1>AI 답변 초안 처리</h1><p>브라우저는 ID만 전송하고, 문의 원문·개인정보는 백엔드에서만 조회합니다.</p></div><span className="handoff-badge">{actionLabel}</span></div>
      <div className="agent-grid">
        <section className="ticket-detail panel"><div className="section-title"><span className="step">1</span><div><h3>AI 실행 요청</h3><p>저장된 문의에 대해 규칙 분류, 공식 근거 검색, 컨텍스트 검증을 실행합니다.</p></div></div><blockquote>문의 ID를 입력한 뒤 AI 초안 생성을 실행하세요. 주문·개인정보가 필요한 문의는 생성 대신 이관됩니다.</blockquote><div className="privacy"><span>🔒</span> 원문 문의와 고객 식별 정보는 프론트에 전달하지 않습니다.</div><div className="section-title evidence-title"><span className="step">2</span><div><h3>사용된 공식 근거</h3><p>API가 반환한 인용 문서 ID만 표시합니다.</p></div></div>{result?.cited_source_ids?.length ? <div className="source-list">{result.cited_source_ids.map((sourceId) => <article className="source-card" key={sourceId}><div className="source-topline"><span className="source-kind">공식 근거</span><span className="approved">인용됨</span></div><h4>{sourceId}</h4></article>)}</div> : <div className="no-evidence"><span>i</span><div><strong>{result ? "고객 답변에 사용할 공식 근거가 선택되지 않았습니다." : "아직 AI 처리를 실행하지 않았습니다."}</strong><p>{result ? "이관 사유를 확인하고 상담원 절차로 진행하세요." : "API 실행 후 인용 문서 ID가 표시됩니다."}</p></div></div>}</section>
        <section className="draft-panel panel"><div className="section-title"><span className="step">3</span><div><h3>Local LLM 답변 초안</h3><p>백엔드가 저장한 결과를 그대로 표시합니다.</p></div></div><textarea value={draft} readOnly placeholder="AI 초안 생성 결과가 여기에 표시됩니다." aria-label="생성된 답변 초안" /><div className="draft-foot"><span>{result ? `생성 상태 · ${result.generation_status}` : "생성 전"}</span><span>{result ? `${result.latency_ms} ms` : ""}</span></div><div className="draft-actions"><button className="primary" onClick={generateAiDraft} disabled={isGenerating}>{isGenerating ? "AI 초안 생성 중..." : "AI 초안 생성"}</button></div>{error && <p className="api-error" role="alert">{error}</p>}{result && <p className="demo-toast">{result.action === "DRAFT_FOR_REVIEW" ? "공식 근거 기반 초안이 저장되었습니다." : `자동 답변을 중단했습니다: ${result.escalation_reason ?? "상담원 검토 필요"}`}</p>}<p className="mock-note">답변 수정·최종 전송 API는 아직 없으므로 화면에서 임의 저장 기능은 제공하지 않습니다.</p></section>
      </div>
    </section>
  </main>;
}
