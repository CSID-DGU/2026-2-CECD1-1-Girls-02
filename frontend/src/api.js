const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(message, { code, status } = {}) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function readJson(response) {
  try {
    return await response.json();
  } catch {
    return null;
  }
}

/**
 * The browser sends only the stored inquiry ID. Customer text and personal
 * data remain inside the backend database boundary.
 */
export async function createInquiryAiDraft(inquiryId) {
  const response = await fetch(`${API_BASE_URL}/inquiries/${inquiryId}/ai-draft`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  const payload = await readJson(response);

  if (!response.ok || !payload?.data) {
    throw new ApiError(payload?.message ?? "AI 초안 생성 요청에 실패했습니다.", {
      code: payload?.code,
      status: response.status,
    });
  }

  return payload.data;
}
