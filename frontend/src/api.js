/**
 * eVOC 백엔드 API 클라이언트.
 * 모든 응답은 { status, code, message, data } 형식이며, 실패하면 ApiError를 던진다.
 */
const env = import.meta.env ?? {};
const API_BASE_URL = (env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const BRAND_CODE = env.VITE_BRAND_CODE ?? "brand_a";

export class ApiError extends Error {
  constructor(message, { code, status } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

function buildUrl(path, query) {
  const url = new URL(`${API_BASE_URL}${path}`);
  Object.entries(query ?? {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  });
  return url.toString();
}

async function call(path, { method = "GET", query, body, headers = {} } = {}) {
  let response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}), ...headers },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError("서버에 연결하지 못했습니다. 백엔드 실행 상태를 확인해 주세요.", { code: "NETWORK_ERROR", status: 0 });
  }
  let payload = null;
  try { payload = await response.json(); } catch { /* 본문 없음 */ }
  return { response, payload };
}

async function request(path, options) {
  const { response, payload } = await call(path, options);
  if (!response.ok || !payload || payload.data === undefined) {
    throw new ApiError(payload?.message ?? "요청을 처리하지 못했습니다.", { code: payload?.code, status: response.status });
  }
  return payload.data;
}

const brandHeader = { "X-Brand-Code": BRAND_CODE };
const sessionHeader = (sessionKey) => ({ "X-Chat-Session-Key": sessionKey });

// ---------- FAQ ----------
export const getFaqs = ({ categoryId, keyword, page = 0, size = 10 } = {}) =>
  request("/api/v1/faqs", { query: { categoryId, keyword, page, size }, headers: brandHeader });
export const getFaq = (faqId) => request(`/api/v1/faqs/${encodeURIComponent(faqId)}`);

// ---------- 1:1 문의 (고객) ----------
export const getInquiryCategories = () => request("/api/v1/inquiry-categories", { headers: brandHeader });
export const searchStores = ({ keyword, page = 0, size = 20 } = {}) =>
  request("/api/v1/stores", { query: { keyword, page, size }, headers: brandHeader });
export const createInquiry = (inquiry) =>
  request("/api/v1/inquiries", { method: "POST", body: { brandId: BRAND_CODE, ...inquiry } });
export const getInquiryStatus = (inquiryId, receiptToken) =>
  request(`/api/v1/inquiries/${encodeURIComponent(inquiryId)}`, { query: { receiptToken } });

// ---------- 챗봇 ----------
export const sendChatMessage = ({ conversationId, message }, sessionKey) =>
  request("/api/v1/chat/messages", {
    method: "POST",
    body: { brandId: BRAND_CODE, conversationId: conversationId ?? null, message },
    headers: sessionHeader(sessionKey),
  });
export const getChatMessages = (conversationId, sessionKey, { limit = 30, before } = {}) =>
  request(`/api/v1/chat/conversations/${encodeURIComponent(conversationId)}/messages`, {
    query: { limit, before },
    headers: sessionHeader(sessionKey),
  });

// ---------- 관리자 ----------
const admin = (inquiryId = "") => `/api/v1/admin/inquiries${inquiryId ? `/${encodeURIComponent(inquiryId)}` : ""}`;
export const listAdminInquiries = ({ status, category, page = 1, pageSize = 20 } = {}) =>
  request(admin(), { query: { status, category, page, pageSize } });
export const getAdminInquiry = (inquiryId) => request(admin(inquiryId));
export const saveDraft = (inquiryId, answerText) =>
  request(`${admin(inquiryId)}/draft`, { method: "PUT", body: { answerText } });
export const approveAnswer = (inquiryId, approvedAnswer) =>
  request(`${admin(inquiryId)}/approve`, { method: "POST", body: { approvedAnswer } });
export const changeInquiryStatus = (inquiryId, status, memo) =>
  request(`${admin(inquiryId)}/status`, { method: "PATCH", body: { status, memo: memo || undefined } });
export const getDashboardSummary = ({ from, to } = {}) => request("/api/v1/admin/dashboard/summary", { query: { from, to } });
export const getAiMetrics = ({ from, to, purpose } = {}) => request("/api/v1/admin/metrics/ai", { query: { from, to, purpose } });

/** AI 초안을 수동으로 다시 실행한다 (DRAFT_GENERATING 상태에서만 동작). 정수 ID를 쓴다. */
export async function createInquiryAiDraft(inquiryId) {
  const internalId = String(inquiryId).replace(/^inq_0*/, "");
  return request(`/inquiries/${internalId}/ai-draft`, { method: "POST" });
}

// ---------- 운영 ----------
/** 503이어도 서비스별 상태가 data에 담겨 오므로 그대로 돌려준다. */
export async function getHealth() {
  const { response, payload } = await call("/healthz");
  if (!payload?.data) throw new ApiError("서버 상태를 확인하지 못했습니다.", { status: response.status });
  return { healthy: response.ok, ...payload.data };
}
