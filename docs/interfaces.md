# eVOC 공통 인터페이스 경계

이 문서는 모듈 사이의 호출 방향과 책임 경계만 정의한다. 구체적인 Request/Response 필드, 클래스명, 함수명은 팀 합의로 계약이 확정된 뒤 작성한다.

| 호출 주체 | 호출 대상 | 목적 | 현재 확정된 반환 책임 |
| --- | --- | --- | --- |
| 백엔드 서비스 | AI Orchestrator | 고객 문의 처리 요청 | AI 처리 결과 반환 |
| AI Orchestrator | RAG Retrieval | 공식 지식·VOC 검색 요청 | 검색 결과와 출처 반환 |
| RAG Pipeline | RAG Retrieval 공통 구성 요소 | 청크·임베딩·인덱스 연동 | 미정 |
| AI Orchestrator | Ollama | LLM 답변 생성 요청 | 생성 결과 반환 |
| AI Orchestrator | 백엔드 서비스 | AI 처리 결과 반환 | 미정 |

## 호출 원칙

- Backend, AI Orchestrator, RAG Retrieval 사이의 연동은 하나의 FastAPI 애플리케이션 안에서 Python 내부 호출로 수행한다.
- RAG Retrieval은 Ollama를 호출하지 않는다.
- Ollama 호출과 상담원 이관 판단은 AI Orchestrator의 책임이다.
- RAG Pipeline은 실시간 문의 처리 흐름과 분리한다.
- 아직 합의되지 않은 데이터 필드, 오류 형식, 함수 및 클래스 이름은 이 단계에서 고정하지 않는다.

