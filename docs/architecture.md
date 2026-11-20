# eVOC 시스템 아키텍처

## 전체 시스템 구성

eVOC는 Backend, AI Orchestrator, RAG Retrieval을 하나의 FastAPI 애플리케이션에 포함한다. 이 세 모듈은 별도의 HTTP 서비스로 나누지 않고 Python 내부 호출로 연동한다. PostgreSQL은 업무 데이터를 관리하는 별도 DB 서비스이며, Chroma는 초기 단계에서 애플리케이션과 같은 실행 환경의 로컬 `PersistentClient`로 사용한다. Local LLM은 별도 GPU 서버의 Ollama에서 실행한다.

프론트엔드는 이 문서의 백엔드 골격 및 배포 설계 범위에 포함하지 않는다.

## 모듈별 책임 범위

| 위치 | 책임 |
| --- | --- |
| `backend/app/api/` | FastAPI HTTP 엔드포인트 경계 |
| `backend/app/services/` | 고객·관리자 업무 로직과 AI 처리 요청 조정 |
| `backend/app/db/` | PostgreSQL 연결 및 데이터 관리 경계 |
| `backend/app/ai/` | RAG 호출, 컨텍스트 구성, Ollama 호출, 상담원 이관 판단 |
| `backend/app/rag/pipeline/` | FAQ/VOC 전처리, 청킹, 메타데이터 처리, 임베딩 및 Chroma 적재 |
| `backend/app/rag/retrieval/` | Dense 검색, BM25, RRF, Reranker와 검색 결과·출처 반환 |
| `backend/app/rag/evaluation/` | 검색 품질 평가 |
| `backend/app/core/` | 여러 애플리케이션 모듈이 공유할 공통 설정 및 기반 요소의 경계 |
| `backend/scripts/` | 향후 데이터 적재 등 운영·개발 스크립트의 위치 |
| `backend/tests/` | 백엔드 애플리케이션 테스트 |

RAG Retrieval은 검색 결과와 출처만 반환하며 Local LLM을 직접 호출하지 않는다. 데이터 적재 파이프라인은 실시간 검색 처리와 분리한다.

## 초기 배포 단위

1. **FastAPI 애플리케이션**: Backend, AI Orchestrator, RAG Retrieval을 함께 배포하고 Python 내부 함수 호출로 연동한다.
2. **PostgreSQL**: FastAPI 애플리케이션과 분리된 DB 서비스로 운영한다.
3. **Chroma**: 초기에는 로컬 `PersistentClient`로 사용한다.
4. **Ollama**: 별도 GPU 서버에서 Local LLM을 실행한다. 이번 초기 골격에는 서버 연결 코드를 포함하지 않는다.

## 실시간 AI 처리 흐름

1. 클라이언트 요청을 FastAPI API가 수신한다.
2. 백엔드 서비스가 고객 문의 처리를 AI Orchestrator에 요청한다.
3. AI Orchestrator가 RAG Retrieval에 공식 지식·VOC 검색을 요청한다.
4. RAG Retrieval이 Chroma 등의 검색 자원을 이용해 검색 결과와 출처를 반환한다.
5. AI Orchestrator가 검색 결과로 컨텍스트를 구성하고 별도 GPU 서버의 Ollama에 답변 생성을 요청한다.
6. AI Orchestrator가 생성 결과와 정책에 따라 상담원 이관 여부를 판단하고 백엔드 서비스에 처리 결과를 반환한다.
7. 백엔드 서비스가 필요한 업무 처리 후 API 응답을 반환한다.

## 데이터 적재 흐름

1. 적재 대상 FAQ/VOC 데이터를 수집한다.
2. RAG Pipeline이 전처리, 청킹, 메타데이터 구성을 수행한다.
3. 공통 임베딩·인덱스 구성 요소를 통해 임베딩을 생성하고 Chroma에 적재한다.
4. RAG Retrieval이 갱신된 인덱스를 실시간 검색에 사용한다.

원본 데이터, 특히 개인정보를 포함할 수 있는 파일은 Git으로 관리하지 않는다. 적재 작업은 실시간 질의 처리 경로와 분리한다.

## 향후 확장 방향

- 데이터 적재 및 대량 임베딩 작업은 추후 Celery Worker로 분리할 수 있도록 실시간 요청 경로와 경계를 유지한다.
- Redis는 필요해질 때 작업 큐 브로커 또는 캐시로 도입한다.
- Worker를 별도 실행 단위로 분리할 경우 여러 프로세스의 안전한 접근을 위해 Chroma 서버 모드 도입을 검토한다.
- RAG 검색 인터페이스의 입력·출력 경계는 유지하면서 검색 구현을 Dense에서 Hybrid(BM25·RRF), 이후 Reranker 단계로 확장한다.
- 이번 초기 구조에는 Dockerfile, Docker Compose, Redis, Celery 설정을 포함하지 않는다.

