import { useEffect, useRef, useState } from "react";
import { INITIAL_CHAT_MESSAGES, requestMockChatResponse } from "../data/mockChat";

const EXAMPLE_QUESTIONS = ["쿠폰은 어떻게 사용하나요?", "창업 상담 절차가 궁금해요."];

export default function CustomerChat({ onCreateInquiry }) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState(() => INITIAL_CHAT_MESSAGES.map((message) => ({ ...message })));
  const [isResponding, setIsResponding] = useState(false);
  const conversationVersion = useRef(0);
  const threadEndRef = useRef(null);

  useEffect(() => { threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, isResponding]);

  const submit = async (event) => {
    event.preventDefault();
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isResponding) return;
    const requestVersion = conversationVersion.current;
    const messageId = Date.now();
    setMessages((current) => [...current, { id: `user-${messageId}`, role: "user", text: trimmedQuestion }]);
    setQuestion(""); setIsResponding(true);
    try {
      const response = await requestMockChatResponse(trimmedQuestion);
      if (conversationVersion.current !== requestVersion) return;
      setMessages((current) => [...current, { id: `assistant-${messageId}`, role: "assistant", text: response.text, sources: response.sources, feedback: null }]);
    } finally {
      if (conversationVersion.current === requestVersion) setIsResponding(false);
    }
  };

  const startNewChat = () => {
    conversationVersion.current += 1;
    setMessages(INITIAL_CHAT_MESSAGES.map((message) => ({ ...message })));
    setQuestion(""); setIsResponding(false);
  };

  const setFeedback = (messageId, feedback) => setMessages((current) => current.map((message) => message.id === messageId ? { ...message, feedback: message.feedback === feedback ? null : feedback } : message));
  const handleKeyDown = (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } };
  const latestSources = [...messages].reverse().find((message) => message.role === "assistant" && message.sources?.length)?.sources ?? [];
  const latestQuestion = [...messages].reverse().find((message) => message.role === "user")?.text ?? "";

  return <main className="workspace customer-workspace">
    <section className="chat-panel panel">
      <div className="panel-heading"><div><p className="eyebrow">CUSTOMER CHAT · MOCK DEMO</p><h2>무엇을 도와드릴까요?</h2></div><div className="chat-heading-actions"><span className="online"><i /> Mock 응답</span><button className="new-chat-button" type="button" onClick={startNewChat}>새 대화</button></div></div>
      <div className="chat-thread" aria-live="polite">
        {messages.map((message) => <div className={`message ${message.role === "user" ? "customer" : "assistant"}`} key={message.id}><span className={`avatar ${message.role === "assistant" ? "ai" : ""}`}>{message.role === "assistant" ? "e" : "고객"}</span><div><div className="bubble">{message.text}</div>{message.role === "assistant" && message.id !== "welcome" && <div className="message-feedback" aria-label="답변 평가"><span>답변이 도움됐나요?</span><button className={message.feedback === "positive" ? "selected" : ""} type="button" onClick={() => setFeedback(message.id, "positive")} aria-label="도움이 됐어요" aria-pressed={message.feedback === "positive"}>👍</button><button className={message.feedback === "negative" ? "selected" : ""} type="button" onClick={() => setFeedback(message.id, "negative")} aria-label="도움이 안 됐어요" aria-pressed={message.feedback === "negative"}>👎</button></div>}</div></div>)}
        {isResponding && <div className="message assistant loading-message"><span className="avatar ai">e</span><div className="bubble"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /><span className="sr-only">Mock 답변 생성 중</span></div></div>}
        <div ref={threadEndRef} />
      </div>
      <div className="safe-note">DEMO · 현재 답변과 근거는 Mock Data입니다. 실제 Backend, RAG, Local LLM을 호출하지 않습니다.</div>
      <form className="composer" onSubmit={submit}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={handleKeyDown} placeholder="문의 내용을 입력해 주세요" aria-label="문의 내용" rows="2" disabled={isResponding} /><button className="send-button" type="submit" disabled={isResponding || !question.trim()}>{isResponding ? "답변 대기" : "전송"} <span>→</span></button></form>
      <p className="input-guide">Enter로 전송 · Shift + Enter로 줄바꿈</p>
      <div className="quick-actions"><span>예시 질문</span>{EXAMPLE_QUESTIONS.map((example) => <button type="button" key={example} onClick={() => setQuestion(example)} disabled={isResponding}>{example.includes("쿠폰") ? "쿠폰 사용 방법" : "창업 상담 절차"}</button>)}</div>
      <div className="inquiry-cta"><div><strong>추가 확인이 필요하신가요?</strong><p>작성 중인 내용이나 마지막 질문을 1:1 문의로 이어서 작성할 수 있습니다.</p></div><button className="secondary" type="button" onClick={() => onCreateInquiry(question.trim() || latestQuestion)}>1:1 문의 작성</button></div>
    </section>
    <aside className="evidence-panel panel"><div className="panel-heading small"><div><p className="eyebrow">RAG EVIDENCE · MOCK</p><h3>공식 근거</h3></div><span className="evidence-count">{latestSources.length}</span></div><div className="evidence-status"><span className="check">i</span><div><strong>데모 근거 표시</strong><p>실제 Chroma 검색 결과가 아닌 UI 확인용 데이터입니다.</p></div></div>{latestSources.length > 0 ? <div className="source-list">{latestSources.map((source) => <article className="source-card" key={source}><div className="source-topline"><span className="source-kind">Mock 근거</span><span className="approved">DEMO</span></div><h4>{source}</h4></article>)}</div> : <div className="no-evidence"><span>i</span><div><strong>표시할 Mock 근거가 없습니다.</strong><p>예시 질문을 전송하면 관련 UI를 확인할 수 있습니다.</p></div></div>}<div className="mock-note">향후 고객 문의 API가 준비되면 Mock 응답 함수만 실제 API 호출로 교체할 수 있습니다.</div></aside>
  </main>;
}
