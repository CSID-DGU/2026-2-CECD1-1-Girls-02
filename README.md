# eVOC

온라인 고객 문의를 접수하고, 정책 문서 기반 AI 답변 초안을 제공하는 eVOC 프로젝트입니다.

## Repository structure

```text
frontend/       # 고객·관리자 화면
backend/        # FastAPI 및 PostgreSQL 연동
  app/
  tests/
rag/            # RAG·Local LLM 모듈
  app/
  scripts/
```

## Local infrastructure

PostgreSQL과 Chroma만 Docker Compose로 실행합니다. 프론트엔드·백엔드·AI 서비스 컨테이너는 각 팀의 실행 환경이 정해진 뒤 추가합니다.

```bash
cp .env.example .env
docker compose up -d postgres chroma
docker compose ps
```

PostgreSQL은 `localhost:5432`, Chroma는 `localhost:8001`에서 접근합니다.

종료할 때는 아래 명령을 사용합니다.

```bash
docker compose down
```

## Backend 실행

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head        # 테이블 생성·갱신
python scripts/seed_demo.py # 시연용 기준 데이터 (가상 예시)
uvicorn app.main:app --reload # http://localhost:8000/docs
```
