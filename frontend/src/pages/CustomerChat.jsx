import { useEffect, useRef, useState } from "react";
import { ApiError, getChatMessages, sendChatMessage } from "../api";
import { ErrorBox, SourceList } from "../components/Common";
import { HANDOFF_REASONS } from "../lib/constants";
import { getChatSessionKey, getConversationId, setConversationId } from "../lib/storage";

const WELCOME = { id: "welcome", role: "assistant", text: "안녕하세요. eVOC 고객 지원입니다. 쿠폰, 멤버십, 주문 등 궁금한 점을 물어봐 주세요.", sources: [] };
const EXAMPLE_QUESTIONS = ["할인 쿠폰은 중복 사용이 가능한가요?", "멤버십 등급은 어떻게 정해지나요?"];

/** 대화 이력 API의 메시지를 화면용으로 바꾼다. */
function fromHistory(message) {
  return {
    id: message.messageId,
    role: message.role === "USER" ? "user" : "assistant",
    text: message.content,
    mode: message.decision === "HANDOFF" ? "HANDOFF" : "ANSWERED",
    sources: (message.sources ?? []).map((source) => ({ title: source.documentTitle, chunkId: source.chunkId })),
  };
}

export default function CustomerChat({ onCreateInquiry }) {
  const sessionKey = useRef(getChatSessionKey()).current;
  const [conversationId, setConversation] = useState(getConversationId);
  const [messages, setMessages] = useState([WELCOME]);
  const [question, setQuestion] = useState("");
  const [isResponding, setIsResponding] = useState(false);
  const [error, setError] = useState(null);
  const threadEndRef = useRef(null);

  // 이전 대화가 있으면 이력을 불러온다.
  useEffect(() => {
    if (!conversationId) return;
    let cancelled = false;
    getChatMessages(conversationId, sessionKey)
      .then((data) => { if (!cancelled) setMessages([WELCOME, ...data.messages.map(fromHistory)]); })
      .catch(() => { if (!cancelled) { setConversationId(null); setConversation(null); } });
    return () => { cancelled = true; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages, isResponding]);

  const remember = (id) => { setConversation(id); setConversationId(id); };

  const submit = async (event) => {
    event.preventDefault();
    const text = question.trim();
    if (!text || isResponding) return;
    const localId = Date.now();
    setMessages((current) => [...current, { id: `user-${localId}`, role: "user", text }]);
    setQuestion(""); setIsResponding(true); setError(null);
    try {
      let reply;
      try {
        reply = await sendChatMessage({ conversationId, message: text }, sessionKey);
      } catch (caught) {
        // 저장된 대화가 더 이상 유효하지 않으면 새 대화로 한 번 다시 보낸다.
        if (!(caught instanceof ApiError && caught.code === "INVALID_INPUT" && conversationId)) throw caught;
        remember(null);
        reply = await sendChatMessage({ conversationId: null, message: text }, sessionKey);
      }
      remember(reply.conversationId);
      setMessages((current) => [...current, {
        id: `assistant-${localId}`, role: "assistant", text: reply.answer, mode: reply.mode,
        sources: reply.sources, handoffReason: reply.handoffReason, question: text,
      }]);
    } catch (caught) {
      setError(caught);
    } finally {
      setIsResponding(false);
    }
  };

  const startNewChat = () => { remember(null); setMessages([WELCOME]); setQuestion(""); setError(null); };
  const handleKeyDown = (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } };
  const latestAnswer = [...messages].reverse().find((message) => message.role === "assistant" && message.id !== "welcome");
  const latestQuestion = [...messages].reverse().find((message) => message.role === "user")?.text ?? "";

  return <main className="workspace customer-workspace">
    <section className="chat-panel panel">
      <div className="panel-heading"><div><p className="eyebrow">CUSTOMER CHAT</p><h2>무엇을 도와드릴까요?</h2></div><div className="chat-heading-actions"><span className="online"><i /> 공식 문서 기반</span><button className="new-chat-button" type="button" onClick={startNewChat}>새 대화</button></div></div>
      <div className="chat-thread" aria-live="polite">
        {messages.map((message) => <div className={`message ${message.role === "user" ? "customer" : "assistant"}`} key={message.id}>
          <span className={`avatar ${message.role === "assistant" ? "ai" : ""}`}>{message.role === "assistant" ? "e" : "고객"}</span>
          <div>
            <div className="bubble">{message.text}</div>
            {message.mode === "HANDOFF" && <div className="handoff-row">
              {message.handoffReason && <small>{HANDOFF_REASONS[message.handoffReason] ?? message.handoffReason}</small>}
              <button className="secondary" type="button" onClick={() => onCreateInquiry(message.question ?? latestQuestion)}>1:1 문의로 이어서 작성</button>
            </div>}
          </div>
        </div>)}
        {isResponding && <div className="message assistant loading-message"><span className="avatar ai">e</span><div className="bubble"><span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" /><span className="sr-only">답변 생성 중</span></div></div>}
        <div ref={threadEndRef} />
      </div>
      <ErrorBox error={error} />
      <div className="safe-note">AI가 공식 FAQ·정책 문서를 근거로 답변합니다. 개인 주문·계정 확인이 필요한 문의는 1:1 문의로 안내해 드려요.</div>
      <form className="composer" onSubmit={submit}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={handleKeyDown} placeholder="문의 내용을 입력해 주세요" aria-label="문의 내용" rows="2" maxLength={1000} disabled={isResponding} /><button className="send-button" type="submit" disabled={isResponding || !question.trim()}>{isResponding ? "답변 대기" : "전송"} <span>→</span></button></form>
      <p className="input-guide">Enter로 전송 · Shift + Enter로 줄바꿈</p>
      <div className="quick-actions"><span>예시 질문</span>{EXAMPLE_QUESTIONS.map((example) => <button type="button" key={example} onClick={() => setQuestion(example)} disabled={isResponding}>{example}</button>)}</div>
      <div className="inquiry-cta"><div><strong>추가 확인이 필요하신가요?</strong><p>작성 중인 내용이나 마지막 질문을 1:1 문의로 이어서 작성할 수 있습니다.</p></div><button className="secondary" type="button" onClick={() => onCreateInquiry(question.trim() || latestQuestion)}>1:1 문의 작성</button></div>
    </section>
    <aside className="evidence-panel panel">
      <div className="panel-heading small"><div><p className="eyebrow">RAG EVIDENCE</p><h3>답변 근거</h3></div><span className="evidence-count">{latestAnswer?.sources?.length ?? 0}</span></div>
      <SourceList sources={latestAnswer?.sources} emptyText={latestAnswer?.mode === "HANDOFF" ? "자동 답변 대신 1:1 문의를 안내했습니다." : "질문하면 답변에 사용한 공식 문서가 여기에 표시됩니다."} />
    </aside>
  </main>;
}
