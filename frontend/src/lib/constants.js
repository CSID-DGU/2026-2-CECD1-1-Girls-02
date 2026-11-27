/** 관리자 화면에서 쓰는 문의 상태 이름과 색상. 고객 화면은 API의 statusLabel을 그대로 쓴다. */
export const INQUIRY_STATUS = {
  DRAFT_GENERATING: { label: "AI 초안 생성 중", tone: "received" },
  PENDING_REVIEW: { label: "검토 대기", tone: "reviewing" },
  IN_REVIEW: { label: "담당자 확인 중", tone: "escalated" },
  ANSWERED: { label: "답변 완료", tone: "answered" },
  CLOSED: { label: "종료", tone: "closed" },
};

/** 백엔드 admin_inquiry_service.ALLOWED_TRANSITIONS와 같은 규칙 */
export const ALLOWED_TRANSITIONS = {
  PENDING_REVIEW: ["IN_REVIEW", "CLOSED"],
  IN_REVIEW: ["PENDING_REVIEW", "CLOSED"],
  ANSWERED: ["CLOSED"],
};
export const REVIEWABLE = ["PENDING_REVIEW", "IN_REVIEW"];

export const TRANSITION_LABELS = { IN_REVIEW: "확인 시작", PENDING_REVIEW: "검토 대기로 되돌리기", CLOSED: "종료 처리" };

export const HANDOFF_REASONS = {
  INSUFFICIENT_EVIDENCE: "공식 안내에서 확인되지 않는 내용이에요.",
  ACCOUNT_VERIFICATION: "개인 계정 정보 확인이 필요한 문의예요.",
  INDIVIDUAL_ORDER: "개별 주문 확인이 필요한 문의예요.",
  INDIVIDUAL_FRANCHISE: "개별 창업 상담이 필요한 문의예요.",
  SAFETY_ISSUE: "담당자가 직접 확인해야 하는 문의예요.",
  PROMPT_INJECTION: "요청 형식 확인이 필요해요.",
  AI_OUTPUT_REJECTED: "자동 답변 검증을 통과하지 못했어요.",
};

/** 문의 유형/카테고리 트리를 select용 평면 목록으로 만든다. */
export function flattenCategories(nodes, path = []) {
  return (nodes ?? []).flatMap((node) => {
    const current = [...path, node.name];
    return [{ ...node, path: current }, ...flattenCategories(node.children, current)];
  });
}
