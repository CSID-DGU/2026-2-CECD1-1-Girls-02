// 데모용 합성 데이터입니다. 실제 고객 정보나 운영 정책 데이터가 아닙니다.
// FastAPI API 계약이 확정되면 이 파일 대신 API 호출로 교체합니다.
export const officialEvidence = [
  { id: "FAQ-MEMBER-001", title: "멤버십 혜택 안내", category: "멤버십", excerpt: "멤버십 등급과 누적 이용 조건에 따라 할인 쿠폰 및 적립 혜택이 제공될 수 있습니다." },
  { id: "POLICY-MEMBER-002", title: "멤버십 운영 정책", category: "멤버십", excerpt: "혜택의 적용 조건과 유효 기간은 이벤트별 안내 및 운영 정책을 따릅니다." },
];

export const tickets = [
  { id: "T-2026-00123", title: "주문 상태 확인 요청", state: "검토 필요", active: true },
  { id: "T-2026-00122", title: "쿠폰 적용 문의", state: "답변 초안", active: false },
  { id: "T-2026-00121", title: "멤버십 혜택 문의", state: "처리 완료", active: false },
];

export const initialDraft = `안녕하세요. 문의하신 주문 상태는 주문 번호와 주문 일시를 확인한 뒤 정확히 안내드릴 수 있습니다.\n\n개인 주문 정보 확인이 필요한 문의이므로 담당 상담원이 확인 후 답변드리겠습니다. 불편을 드려 죄송합니다.`;
