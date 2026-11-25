import { useState } from "react";

import { ApiError, createInquiryAiDraft } from "./api";
import "./app-overrides.css";

function CustomerChat() {
  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("");

  const submit = (event) => {
    event.preventDefault();
    if (!question.trim()) return;
    setSubmittedQuestion(question.trim());
    setQuestion("");
  };

  return <main className="workspace customer-workspace">
    <section className="chat-panel panel">
      <div className="panel-heading"><div><p className="eyebrow">CUSTOMER CHAT</p><h2>무엇을 도와드릴까요?</h2></div><span className="online"><i /> 문의 접수 준비</span></div>
      <div className="chat-thread">
        {submittedQuestion && <div className="message customer"><span className="avatar">고객</span><div className="bubble">{submittedQuestion}</div></div>}
        <div className="message assistant"><span className="avatar ai">e</span><div className="bubble">고객 문의 생성 API가 연결되면 저장된 문의를 바탕으로 공식 근거 검색과 AI 응답이 이 화면에 표시됩니다.</div></div>
        <div className="safe-note">자동 답변은 승인된 공식 FAQ·정책만 근거로 사용합니다. 개인 주문 확인이나 근거 부족 문의는 상담원에게 이관됩니다.</div>
      </div>
      <form className="composer" onSubmit={submit}><input value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="문의 내용을 입력해 주세요" aria-label="문의 내용" /><button className="send-button" type="submit">입력 확인 <span>→</span></button></form>
      <div className="quick-actions"><span>예시 질문</span><button type="button" onClick={() => setQuestion("쿠폰은 어떻게 사용하나요?")}>쿠폰 사용 방법</button><button type="button" onClick={() => setQuestion("창업 상담 절차가 궁금해요.")}>창업 상담 절차</button></div>
    </section>
    <aside className="evidence-panel panel">
      <div className="panel-heading small"><div><p className="eyebrow">RAG EVIDENCE</p><h3>공식 근거</h3></div><span className="evidence-count">대기</span></div>
      <div className="evidence-status"><span className="check">i</span><div><strong>고객 문의 API 연결 전</strong><p>가짜 FAQ·정책 근거는 화면에서 제거했습니다.</p></div></div>
      <div className="mock-note">상담원 워크스페이스에서는 저장된 문의 ID를 이용해 실제 FastAPI AI 초안 생성 API를 호출할 수 있습니다.</div>
    </aside>
  </main>;
}

function AgentWorkspace() {
  const [inquiryId, setInquiryId] = useState(import.meta.env.VITE_DEMO_INQUIRY_ID ?? "");
  const [draft, setDraft] = useState("");
  const [result, setResult] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");

  const generateAiDraft = async () => {
    const parsedId = Number(inquiryId);
    setError("");
    setResult(null);
    setDraft("");

    if (!Number.isInteger(parsedId) || parsedId <= 0) {
      setError("AI 처리를 실행할 DB 문의 ID를 입력해 주세요.");
      return;
    }

    setIsGenerating(true);
    try {
      const nextResult = await createInquiryAiDraft(parsedId);
      setResult(nextResult);
      setDraft(
        nextResult.draft_text
          ?? `자동 답변을 생성하지 않았습니다.\n\n이관 사유: ${nextResult.escalation_reason ?? "공식 근거 또는 업무 규칙을 확인해 주세요."}`,
      );
    } catch (caughtError) {
      setError(
        caughtError instanceof ApiError
          ? caughtError.message
          : "서버에 연결하지 못했습니다. FastAPI 실행 상태를 확인해 주세요.",
      );
    } finally {
      setIsGenerating(false);
    }
  };

  const actionLabel = result?.action === "DRAFT_FOR_REVIEW" ? "답변 초안 생성" : result ? "상담원 이관 필요" : "AI 처리 전";

  return <main className="agent-layout">
    <aside className="ticket-nav">
      <div className="ticket-nav-head"><p className="eyebrow">INQUIRY SELECT</p><h2>문의 선택</h2></div>
      <label className="inquiry-id-field">문의 ID<input value={inquiryId} onChange={(event) => setInquiryId(event.target.value)} inputMode="numeric" placeholder="예: 1" aria-label="처리할 문의 ID" /></label>
      <p className="mock-note">현재 문의 목록 API는 아직 없습니다. PostgreSQL에 저장된 문의 ID를 직접 입력해 AI 처리를 검증합니다.</p>
    </aside>
    <section className="agent-content">
      <div className="ticket-header"><div><p className="eyebrow">INQUIRY {inquiryId || "-"}</p><h1>AI 답변 초안 처리</h1><p>브라우저는 ID만 전송하고, 문의 원문·개인정보는 백엔드에서만 조회합니다.</p></div><span className="handoff-badge">{actionLabel}</span></div>
      <div className="agent-grid">
        <section className="ticket-detail panel">
          <div className="section-title"><span className="step">1</span><div><h3>AI 실행 요청</h3><p>저장된 문의에 대해 규칙 분류, 공식 근거 검색, 컨텍스트 검증을 실행합니다.</p></div></div>
          <blockquote>문의 ID를 입력한 뒤 AI 초안 생성을 실행하세요. 주문·개인정보가 필요한 문의는 생성 대신 이관됩니다.</blockquote>
          <div className="privacy"><span>🔒</span> 원문 문의와 고객 식별 정보는 프론트에 전달하지 않습니다.</div>
          <div className="section-title evidence-title"><span className="step">2</span><div><h3>사용된 공식 근거</h3><p>API가 반환한 인용 문서 ID만 표시합니다.</p></div></div>
          {result?.cited_source_ids?.length ? <div className="source-list">{result.cited_source_ids.map((sourceId) => <article className="source-card" key={sourceId}><div className="source-topline"><span className="source-kind">공식 근거</span><span className="approved">인용됨</span></div><h4>{sourceId}</h4></article>)}</div> : <div className="no-evidence"><span>i</span><div><strong>{result ? "고객 답변에 사용할 공식 근거가 선택되지 않았습니다." : "아직 AI 처리를 실행하지 않았습니다."}</strong><p>{result ? "이관 사유를 확인하고 상담원 절차로 진행하세요." : "API 실행 후 인용 문서 ID가 표시됩니다."}</p></div></div>}
        </section>
        <section className="draft-panel panel">
          <div className="section-title"><span className="step">3</span><div><h3>Local LLM 답변 초안</h3><p>백엔드가 저장한 결과를 그대로 표시합니다.</p></div></div>
          <textarea value={draft} readOnly placeholder="AI 초안 생성 결과가 여기에 표시됩니다." aria-label="생성된 답변 초안" />
          <div className="draft-foot"><span>{result ? `생성 상태 · ${result.generation_status}` : "생성 전"}</span><span>{result ? `${result.latency_ms} ms` : ""}</span></div>
          <div className="draft-actions"><button className="primary" onClick={generateAiDraft} disabled={isGenerating}>{isGenerating ? "AI 초안 생성 중..." : "AI 초안 생성"}</button></div>
          {error && <p className="api-error" role="alert">{error}</p>}
          {result && <p className="demo-toast">{result.action === "DRAFT_FOR_REVIEW" ? "공식 근거 기반 초안이 저장되었습니다." : `자동 답변을 중단했습니다: ${result.escalation_reason ?? "상담원 검토 필요"}`}</p>}
          <p className="mock-note">답변 수정·최종 전송 API는 아직 없으므로 화면에서 임의 저장 기능은 제공하지 않습니다.</p>
        </section>
      </div>
    </section>
  </main>;
}

function AuthScreen({ mode, onEnter, onModeChange }) {
  const isSignup = mode === "signup";
  return <main className="auth-page">
    <section className="auth-intro"><p className="eyebrow">EVOC CUSTOMER CARE</p><h1>문의는 빠르게,<br />답변은 <em>근거 있게.</em></h1><p>공식 FAQ·정책 문서를 바탕으로 AI가 1차 응대를 돕고, 어려운 문의는 담당 상담원에게 안전하게 연결합니다.</p><div className="auth-flow"><span>문의 접수</span><b>→</b><span>공식 근거 검색</span><b>→</b><span>AI 답변 또는 이관</span></div></section>
    <section className="auth-card panel"><p className="eyebrow">{isSignup ? "CREATE ACCOUNT" : "WELCOME BACK"}</p><h2>{isSignup ? "eVOC 회원가입" : "로그인"}</h2><p className="auth-description">{isSignup ? "가입 후 문의 이력과 답변 진행 상태를 확인할 수 있어요." : "로그인하고 내 문의와 답변 현황을 확인하세요."}</p><form className="auth-form" onSubmit={(event) => { event.preventDefault(); onEnter(); }}>{isSignup && <><label>이름<input placeholder="이름을 입력해 주세요" required /></label><label>휴대폰 번호<input placeholder="010-0000-0000" required /></label></>}<label>이메일<input type="email" placeholder="example@email.com" required /></label><label>비밀번호<input type="password" placeholder="비밀번호를 입력해 주세요" required /></label>{isSignup && <label className="checkbox"><input type="checkbox" required /> <span>서비스 이용약관 및 개인정보 수집·이용에 동의합니다.</span></label>}<button className="auth-submit" type="submit">{isSignup ? "회원가입하고 시작하기" : "로그인"}</button></form><div className="auth-divider"><span>또는</span></div><div className="social-buttons"><button type="button" onClick={onEnter}><b className="kakao">●</b> 카카오로 계속하기</button><button type="button" onClick={onEnter}><b className="naver">N</b> 네이버로 계속하기</button></div><p className="auth-switch">{isSignup ? "이미 계정이 있으신가요?" : "eVOC가 처음이신가요?"}<button type="button" onClick={() => onModeChange(isSignup ? "login" : "signup")}>{isSignup ? "로그인" : "회원가입"}</button></p><p className="auth-demo">DEMO · 인증 로직 없이 화면 이동만 동작합니다.</p></section>
  </main>;
}

export default function App() {
  const [view, setView] = useState("login");
  const authMode = view === "signup" ? "signup" : "login";
  const isAuth = view === "login" || view === "signup";
  return <div className="app-shell"><header className="topbar"><button className="brand" onClick={() => setView("customer")}><span className="brand-mark">e</span><span>eVOC</span><small>AI CUSTOMER CARE</small></button><nav><button className={view === "customer" ? "active" : ""} onClick={() => setView("customer")}>고객 챗봇</button><button className={view === "agent" ? "active" : ""} onClick={() => setView("agent")}>상담원 워크스페이스</button></nav>{!isAuth && <button className="login-link" onClick={() => setView("login")}>로그아웃</button>}{isAuth && <span className="demo-badge">DEMO MODE</span>}</header>{isAuth ? <AuthScreen mode={authMode} onEnter={() => setView("customer")} onModeChange={setView} /> : view === "customer" ? <CustomerChat /> : <AgentWorkspace />}</div>;
}
