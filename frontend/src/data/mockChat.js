export const INITIAL_CHAT_MESSAGES = [
  { id: "welcome", role: "assistant", text: "안녕하세요. eVOC 고객 지원 데모입니다. 쿠폰이나 창업 상담에 대해 질문해 주세요.", sources: [], feedback: null },
];

const MOCK_RESPONSES = [
  { keywords: ["쿠폰", "할인"], text: "쿠폰은 결제 화면의 쿠폰 선택 영역에서 적용할 수 있습니다. 쿠폰마다 사용 기간과 적용 조건이 다를 수 있으니 표시된 안내를 함께 확인해 주세요.", sources: ["FAQ · 쿠폰 사용 방법", "정책 · 쿠폰 적용 조건"] },
  { keywords: ["창업", "가맹", "상담"], text: "창업 상담은 기본 정보 확인 후 담당 부서 상담 순서로 진행됩니다. 실제 신청과 일정 확인은 담당 상담원을 통해 안내받아 주세요.", sources: ["FAQ · 창업 상담 절차"] },
];

const DEFAULT_RESPONSE = { text: "현재 화면은 Mock 응답을 사용하는 데모입니다. 실제 문의 내용에 대한 정확한 안내는 고객 문의 API 연동 후 공식 FAQ 검색 결과를 바탕으로 제공됩니다.", sources: ["DEMO · 실제 검색 근거 아님"] };

export async function requestMockChatResponse(query) {
  await new Promise((resolve) => window.setTimeout(resolve, 700));
  return MOCK_RESPONSES.find(({ keywords }) => keywords.some((keyword) => query.includes(keyword))) ?? DEFAULT_RESPONSE;
}
