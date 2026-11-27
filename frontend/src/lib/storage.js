/** 브라우저 저장소. 시크릿 모드 등에서 실패해도 화면은 계속 동작해야 하므로 모두 try/catch로 감싼다. */
const KEYS = { session: "evoc.chat.sessionKey", conversation: "evoc.chat.conversationId", inquiries: "evoc.myInquiries" };

function read(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function write(key, value) {
  try {
    if (value === null || value === undefined) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, JSON.stringify(value));
  } catch { /* 저장 불가 환경 */ }
}

function newUuid() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID();
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = Math.floor(Math.random() * 16);
    return (c === "x" ? r : (r % 4) + 8).toString(16);
  });
}

let memorySessionKey = null;

/** 챗봇 세션 키 (X-Chat-Session-Key). 브라우저마다 하나를 만들어 계속 쓴다. */
export function getChatSessionKey() {
  const stored = read(KEYS.session, null);
  if (stored) return stored;
  memorySessionKey = memorySessionKey ?? newUuid();
  write(KEYS.session, memorySessionKey);
  return memorySessionKey;
}

export const getConversationId = () => read(KEYS.conversation, null);
export const setConversationId = (conversationId) => write(KEYS.conversation, conversationId);

/** 고객 문의 목록 API가 없으므로, 접수할 때 받은 ID·조회 토큰을 이 브라우저에 보관한다. */
export const getMyInquiries = () => read(KEYS.inquiries, []);
export function addMyInquiry({ inquiryId, receiptToken, title, createdAt }) {
  const others = getMyInquiries().filter((item) => item.inquiryId !== inquiryId);
  write(KEYS.inquiries, [{ inquiryId, receiptToken, title, createdAt }, ...others]);
}
