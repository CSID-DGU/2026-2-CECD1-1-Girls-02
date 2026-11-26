export const INQUIRY_TYPES = ["문의", "제안", "칭찬", "불만"];
export const STORE_OPTIONS = ["강남역점", "서울역점", "부산서면점", "매장 미지정"];

export const INITIAL_MOCK_INQUIRIES = [
  {
    id: 1002,
    customerName: "김고객",
    type: "문의",
    storeName: "강남역점",
    title: "쿠폰 사용 조건이 궁금합니다",
    content: "보유한 쿠폰의 사용 가능 메뉴와 유효기간을 확인하고 싶습니다.",
    status: "ANSWERED",
    createdAt: "2026-11-24",
    answerContent: "쿠폰 상세 화면에서 적용 메뉴와 유효기간을 확인할 수 있습니다. 결제 전 쿠폰 적용 여부를 확인해 주세요.",
    answeredAt: "2026-11-25",
  },
  {
    id: 1001,
    customerName: "이고객",
    type: "제안",
    storeName: "서울역점",
    title: "매장 이용 관련 제안",
    content: "매장 이용 안내를 더 쉽게 확인할 수 있으면 좋겠습니다.",
    status: "RECEIVED",
    createdAt: "2026-11-23",
    answerContent: null,
    answeredAt: null,
  },
];

export const INQUIRY_STATUS = {
  RECEIVED: { label: "접수 완료", tone: "received" },
  AI_DRAFTED: { label: "답변 검토 중", tone: "reviewing" },
  ESCALATED: { label: "담당자 확인 중", tone: "escalated" },
  ANSWERED: { label: "답변 완료", tone: "answered" },
};

export function createMockInquiry(form, currentInquiries) {
  const nextId = Math.max(1000, ...currentInquiries.map(({ id }) => id)) + 1;
  return {
    id: nextId,
    customerName: form.customerName.trim(),
    type: form.type,
    storeName: form.storeName,
    title: form.title.trim(),
    content: form.content.trim(),
    status: "RECEIVED",
    createdAt: new Date().toISOString().slice(0, 10),
    answerContent: null,
    answeredAt: null,
  };
}
