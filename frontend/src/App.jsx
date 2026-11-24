import { useState } from "react";
import { initialDraft, officialEvidence, tickets } from "./mockData";

function SourceCard({ item }) {
  return <article className="source-card">
    <div className="source-topline"><span className="source-kind">공식 {item.id.startsWith("FAQ") ? "FAQ" : "정책"}</span><span className="approved">검수 완료</span></div>
    <h4>{item.title}</h4><p>{item.excerpt}</p>
    <div className="source-meta"><span>{item.id}</span><span>{item.category}</span></div>
  </article>;
}

function CustomerChat() {
  const [question, setQuestion] = useState("");
  const [submittedQuestion, setSubmittedQuestion] = useState("멤버십 혜택이 궁금해요.");
  const [notice, setNotice] = useState("");
  const submit = (event) => {
    event.preventDefault();
    if (!question.trim()) return;
    setSubmittedQuestion(question.trim()); setQuestion("");
    setNotice("데모 응답이 갱신되었습니다. 실제 서비스에서는 RAG 검색과 LLM 생성 결과가 표시됩니다.");
  };
  return <main className="workspace customer-workspace">
    <section className="chat-panel panel">
      <div className="panel-heading"><div><p className="eyebrow">CUSTOMER CHAT</p><h2>무엇을 도와드릴까요?</h2></div><span className="online"><i /> AI 상담 가능</span></div>
      <div className="chat-thread">
        <div className="message customer"><span className="avatar">고객</span><div className="bubble">{submittedQuestion}</div></div>
        <div className="message assistant"><span className="avatar ai">e</span><div><div className="bubble">멤버십 혜택은 등급과 누적 이용 조건에 따라 제공됩니다. 적용 가능한 혜택과 유효 기간은 이벤트별 안내를 확인해 주세요.</div><div className="citation-row"><span>근거</span><button>멤버십 혜택 안내</button><button>멤버십 운영 정책</button></div></div></div>
        <div className="safe-note">답변은 공식 FAQ·정책 근거를 바탕으로 제공합니다. 근거가 부족하거나 개인 주문 확인이 필요하면 상담원에게 연결됩니다.</div>
      </div>
      <form className="composer" onSubmit={submit}><input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="문의 내용을 입력해 주세요" aria-label="문의 내용" /><button className="send-button" type="submit">보내기 <span>→</span></button></form>
      <div className="quick-actions"><span>빠른 질문</span><button type="button" onClick={() => setQuestion("쿠폰은 어떻게 사용하나요?")}>쿠폰 사용 방법</button><button type="button" onClick={() => setQuestion("주문 상태를 확인하고 싶어요.")}>주문 상태 확인</button></div>
      {notice && <p className="demo-toast">{notice}</p>}
    </section>
    <aside className="evidence-panel panel">
      <div className="panel-heading small"><div><p className="eyebrow">RAG EVIDENCE</p><h3>답변에 사용된 공식 근거</h3></div><span className="evidence-count">2건</span></div>
      <div className="evidence-status"><span className="check">✓</span><div><strong>공식 근거 충분</strong><p>승인된 FAQ·정책만 컨텍스트에 포함</p></div></div>
      <div className="source-list">{officialEvidence.map((item) => <SourceCard key={item.id} item={item} />)}</div>
      <div className="mock-note">DEMO · 합성 데이터 화면입니다. 실제 검색 결과 연동 전 UI 검증용입니다.</div>
    </aside>
  </main>;
}

function AgentWorkspace() {
  const [draft, setDraft] = useState(initialDraft);
  const [status, setStatus] = useState("상담원 검토 필요");
  const [saved, setSaved] = useState("");
  const save = (nextStatus) => { setStatus(nextStatus); setSaved(nextStatus === "답변 처리 완료" ? "고객에게 최종 답변 처리되었습니다. (데모)" : "수정한 답변 초안을 저장했습니다. (데모)"); };
  return <main className="agent-layout">
    <aside className="ticket-nav"><div className="ticket-nav-head"><p className="eyebrow">TICKETS</p><h2>고객 문의함</h2><button className="new-ticket">+ 새 문의</button></div><div className="ticket-list">{tickets.map((ticket) => <button className={`ticket-item ${ticket.active ? "selected" : ""}`} key={ticket.id}><span>{ticket.id}</span><strong>{ticket.title}</strong><small>{ticket.state}</small></button>)}</div></aside>
    <section className="agent-content">
      <div className="ticket-header"><div><p className="eyebrow">TICKET T-2026-00123</p><h1>주문 상태 확인 요청</h1><p>접수 시간 2026. 11. 23. 14:25 · 고객 정보는 마스킹 처리됨</p></div><span className="handoff-badge">{status}</span></div>
      <div className="agent-grid">
        <section className="ticket-detail panel"><div className="section-title"><span className="step">1</span><div><h3>고객 문의</h3><p>개인 주문 정보가 필요한 문의는 자동 답변을 중단하고 이관합니다.</p></div></div><blockquote>“어제 주문한 상품의 현재 배송 상태를 확인하고 싶습니다.”</blockquote><div className="privacy"><span>🔒</span> 주문 번호·연락처 등 직접 식별 정보는 상담원 화면에서만 확인합니다.</div><div className="section-title evidence-title"><span className="step">2</span><div><h3>RAG 검색 결과</h3><p>공식 문서 결과가 부족하여 답변 자동 전송을 보류했습니다.</p></div></div><div className="no-evidence"><span>!</span><div><strong>개별 주문 조회는 공식 FAQ만으로 처리할 수 없습니다.</strong><p>유사 사례는 내부 참고용이며 고객 답변의 근거로 사용하지 않습니다.</p></div></div></section>
        <section className="draft-panel panel"><div className="section-title"><span className="step">3</span><div><h3>Local LLM 답변 초안</h3><p>근거·이관 규칙을 반영한 상담원 검토용 초안입니다.</p></div></div><textarea value={draft} onChange={(e) => setDraft(e.target.value)} aria-label="답변 초안" /><div className="draft-foot"><span>Ollama · 초안 생성 완료</span><span>상담원이 수정 후 확정</span></div><div className="draft-actions"><button className="secondary" onClick={() => save("답변 초안 저장")}>수정 저장</button><button className="primary" onClick={() => save("답변 처리 완료")}>최종 답변 처리</button></div>{saved && <p className="demo-toast">{saved}</p>}</section>
      </div>
    </section>
  </main>;
}

function AuthScreen({ mode, onEnter, onModeChange }) {
  const isSignup = mode === "signup";
  return <main className="auth-page">
    <section className="auth-intro">
      <p className="eyebrow">EVOC CUSTOMER CARE</p>
      <h1>문의는 빠르게,<br />답변은 <em>근거 있게.</em></h1>
      <p>공식 FAQ·정책 문서를 바탕으로 AI가 1차 응대를 돕고, 어려운 문의는 담당 상담원에게 안전하게 연결합니다.</p>
      <div className="auth-flow"><span>문의 접수</span><b>→</b><span>공식 근거 검색</span><b>→</b><span>AI 답변 또는 이관</span></div>
    </section>
    <section className="auth-card panel">
      <p className="eyebrow">{isSignup ? "CREATE ACCOUNT" : "WELCOME BACK"}</p>
      <h2>{isSignup ? "eVOC 회원가입" : "로그인"}</h2>
      <p className="auth-description">{isSignup ? "가입 후 문의 이력과 답변 진행 상태를 확인할 수 있어요." : "로그인하고 내 문의와 답변 현황을 확인하세요."}</p>
      <form className="auth-form" onSubmit={(event) => { event.preventDefault(); onEnter(); }}>
        {isSignup && <><label>이름<input placeholder="이름을 입력해 주세요" required /></label><label>휴대폰 번호<input placeholder="010-0000-0000" required /></label></>}
        <label>이메일<input type="email" placeholder="example@email.com" required /></label>
        <label>비밀번호<input type="password" placeholder="비밀번호를 입력해 주세요" required /></label>
        {isSignup && <label className="checkbox"><input type="checkbox" required /> <span>서비스 이용약관 및 개인정보 수집·이용에 동의합니다.</span></label>}
        <button className="auth-submit" type="submit">{isSignup ? "회원가입하고 시작하기" : "로그인"}</button>
      </form>
      <div className="auth-divider"><span>또는</span></div>
      <div className="social-buttons"><button type="button" onClick={onEnter}><b className="kakao">●</b> 카카오로 계속하기</button><button type="button" onClick={onEnter}><b className="naver">N</b> 네이버로 계속하기</button></div>
      <p className="auth-switch">{isSignup ? "이미 계정이 있으신가요?" : "eVOC가 처음이신가요?"}<button type="button" onClick={() => onModeChange(isSignup ? "login" : "signup")}>{isSignup ? "로그인" : "회원가입"}</button></p>
      <p className="auth-demo">DEMO · 인증 로직 없이 화면 이동만 동작합니다.</p>
    </section>
  </main>;
}

export default function App() {
  const [view, setView] = useState("login");
  const authMode = view === "signup" ? "signup" : "login";
  const isAuth = view === "login" || view === "signup";
  return <div className="app-shell"><header className="topbar"><button className="brand" onClick={() => setView("customer")}><span className="brand-mark">e</span><span>eVOC</span><small>AI CUSTOMER CARE</small></button><nav><button className={view === "customer" ? "active" : ""} onClick={() => setView("customer")}>고객 챗봇</button><button className={view === "agent" ? "active" : ""} onClick={() => setView("agent")}>상담원 워크스페이스</button></nav>{!isAuth && <button className="login-link" onClick={() => setView("login")}>로그아웃</button>}{isAuth && <span className="demo-badge">DEMO MODE</span>}</header>{isAuth ? <AuthScreen mode={authMode} onEnter={() => setView("customer")} onModeChange={setView} /> : view === "customer" ? <CustomerChat /> : <AgentWorkspace />}</div>;
}
