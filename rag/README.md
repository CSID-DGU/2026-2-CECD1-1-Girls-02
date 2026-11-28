# RAG ingestion contract

This directory contains code only. Never commit a real brand name, internal document, original VOC, or PII here. Inputs and generated artifacts must stay in an approved private location outside Git.

| Collection | Permitted source | Retrieval use | Policy authority |
| --- | --- | --- | --- |
| `brand_a_official_knowledge` | approved official FAQ, policy, and notice documents | `DRAFT_ONLY` | yes, subject to human review |
| `brand_a_voc_cases` | approved, de-identified historical VOC | `AGENT_REFERENCE_ONLY` | no — never cite as policy |

Each JSONL input line requires `source_id`, `title`, `text`, `document_version`, and `source_type` (`official` or `voc`). Optional metadata: `source_url`, `published_at`, and `category`. The source type must match the chosen collection.

## Workflow

1. Keep approved raw JSONL in a private path, outside this repository.
2. First run without `--apply`: common direct identifiers are masked and only sanitized chunks, an audit log, and rejection reasons are written.
3. Review those records, then add `--apply` to upsert deterministic IDs and verify every written ID in Chroma.
4. Before promotion, link document and pipeline versions to GT evaluation results: retrieval recall, citation correctness, and harmful-leakage rate.

```powershell
$env:PYTHONPATH = "rag"
python rag/scripts/ingest_jsonl.py --input C:\private\official.jsonl --collection brand_a_official_knowledge --output-dir C:\private\rag-build\official-v1
python rag/scripts/ingest_jsonl.py --input C:\private\official.jsonl --collection brand_a_official_knowledge --output-dir C:\private\rag-build\official-v1 --apply
python -m unittest discover -s rag/tests -v
```

The CLI never copies raw input. Retain its artifact directory under access control with ingestion audit, document version, exclusion reason, evaluation run ID, and deployment approval.

## Rebuild the in-process BM25 index after Chroma ingestion

BM25 reads the same deterministic Chroma IDs, documents, and metadata written by
`ingest_jsonl.py`. Rebuild only after the ingestion command has completed and its
Chroma ID verification has succeeded. `OfficialSearchSettings.from_env()` uses
`CHROMA_HOST`, `CHROMA_PORT`, and `CHROMA_OFFICIAL_COLLECTION`; use
`localhost:8001` on the host or `chroma:8000` inside Compose.

The running application process must own and call the manager. A standalone CLI
would lose its in-memory index when it exits and cannot update another process.

```python
from rag.app.retrieval.bm25 import kiwi_tokenize
from rag.app.retrieval.bm25_chroma import BM25IndexManager, OfficialChromaChunkLoader

loader = OfficialChromaChunkLoader.connect()
bm25 = BM25IndexManager(loader, tokenizer=kiwi_tokenize)
status = bm25.rebuild()
assert status.state == "ready"
assert status.loaded_chunk_count == status.index_chunk_count
```

Operational sequence:

1. Confirm Chroma heartbeat and the official collection.
2. Complete approved FAQ ingestion and ID verification.
3. Call `rebuild()` inside the process that serves BM25 requests.
4. Record `status.snapshot_id`, counts, tokenizer, and completion time.
5. Confirm `state == "ready"` before calling `search()`.
6. Run a non-sensitive Top-K smoke query.

The loader pages through only active, approved, `DRAFT_ONLY` official chunks and
validates the same policy again after loading. It preserves Chroma chunk IDs and
document metadata. A count change during pagination aborts the rebuild. Same-count
concurrent updates cannot be detected without a Chroma transaction, so ingestion
and rebuilding must remain sequential.

Rebuilds are fail-closed: the new index is built separately and swapped only after
validation. During a rebuild, or after a failed rebuild, `search()` raises
`BM25IndexUnavailableError`; an older index is not silently presented as current.
Chroma changes do not automatically update BM25—`rebuild()` must be called again.

## 공식 FAQ 검색 CLI 데모

저장소 루트에서 RAG 의존성이 설치된 가상환경으로 실행한다. 루트 `.env`의
`CHROMA_HOST`, `CHROMA_PORT`, `CHROMA_OFFICIAL_COLLECTION`,
`RAG_EMBEDDING_MODEL`을 읽으며 실행 프로세스의 환경변수가 우선한다.

```sh
.venv-rag/bin/python -m rag.scripts.demo_retrieval
.venv-rag/bin/python -m rag.scripts.demo_retrieval --query "쿠폰이 적용되지 않으면 어떻게 하나요?"
.venv-rag/bin/python -m rag.scripts.demo_retrieval --strategy hybrid --top-k 5 --show-full-text
```

- 대화형 모드에서 `exit` 또는 `quit`으로 종료한다. `--query`는 한 번 검색하고 종료한다.
- 기본 `--strategy all`은 Dense Top-10, Basic BM25 Top-10, Hybrid Top-5를 순서대로 표시한다.
  단독 모드는 `dense`, `bm25`, `hybrid`로 선택한다. `--top-k` 범위는 1~50이다.
  `all`의 Dense·BM25 출력은 `max(10, top_k)`이며 Hybrid 내부 후보도 각 검색기에
  최소 10개를 요청한다. Hybrid 점수는 동일 가중치와 `rrf_k=60`을 사용한다.
- 검색 본문 미리보기는 최대 200자다. `--show-full-text`로 전체 청크를 볼 수 있다.
  Hybrid에서 Agent가 쓰는 컨텍스트 빌더의 채택 근거는 별도 섹션에 표시한다.
  출력에는 기존 개인정보 마스킹을 적용한다. 데모에는 고객 개인정보를 입력하지 않는다.
- Basic 인덱스는 시작 시 한 번 생성한다. Chroma를 갱신한 뒤에는 데모를 재시작한다.
  최초 Dense 검색 시간에는 BGE-M3 모델 로딩이 포함될 수 있다.
  오프라인에서 이미 캐시된 동일 모델을 사용하려면 실행 시 `RAG_EMBEDDING_MODEL`에
  해당 로컬 스냅샷 디렉터리를 지정할 수 있다.

CLI는 Chroma의 기존 공식 컬렉션을 조회한다. Ollama, Backend Runtime, 챗봇 API를
거치지 않는다.

## Agent 라우팅 진단 CLI

저장소 루트에서 실행한다.

```sh
.venv-rag/bin/python -m rag.scripts.demo_agent_routing --query "갈릭디핑소스는 몇 개 주나요?"
.venv-rag/bin/python -m rag.scripts.demo_agent_routing --query "맛대가리가 존나게 없어요?" --with-retrieval
.venv-rag/bin/python -m rag.scripts.demo_agent_routing --query "피자를 먹고 배가 아파요." --is-safety-related
```

기본 모드는 고객 채팅과 같이 질문만 넣고 실제 Agent의 분류 노드와 검색 전 분기를 호출한다.
현재 `classify` 노드는 State를 갱신하지 않으며, 다음 분기가 텍스트 가드레일과 입력 플래그를 검사한다.
`--is-sensitive`, `--is-safety-related`, `--is-urgent`,
`--has-individual-order-context`는 외부 판단을 가정하는 수동 State 입력이다.

`--with-retrieval`은 `retrieve` 분기에서만 Backend와 같은 공식 Dense 어댑터와
컨텍스트 빌더를 호출한다. `generate`가 표시되면 그래프의 다음 노드를 뜻한다.
CLI는 답변 생성 또는 실제 상담원 이관을 실행하지 않는다. 기본 모드와 검색 전 이관 분기는
외부 서비스 연결 없이 동작한다.

## 디렉터리와 검증

| 경로 | 역할 |
| --- | --- |
| `rag/app/ingestion.py` | 문서 청킹 및 적재 |
| `rag/app/retrieval/` | 검색 계약, Dense·BM25·RRF, Chroma 연결 및 인덱스 관리 |
| `rag/app/evaluation/` | 평가 스키마, 지표, Runner |
| `rag/scripts/` | 적재, 토크나이저 분석, 검색·라우팅 진단 CLI |
| `rag/evaluation/` | GT 예시와 실험별 실행 자료·보고서 |
| `rag/tests/` | RAG 및 진단 CLI 테스트 |

기존 평가 실험은 저장된 모듈 경로로 재실행할 수 있다. 비공개 FAQ, GT와 질문별 결과는
형상 관리에서 제외한다.

```sh
.venv-rag/bin/python -m unittest discover -s rag/tests -p 'test_*.py' -q
PYTHONPATH=. .venv-rag/bin/pytest backend/tests -q
```
