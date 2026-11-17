# 작업 환경 및 GitHub 협업 방법

프로젝트 작업은 아래 순서로 진행합니다.

## 1. 이슈 생성

GitHub 저장소의 **Issues**에서 작업 내용을 작성합니다.

- 제목은 작업 내용을 한눈에 알 수 있도록 작성합니다.
- 본문에는 작업 목적과 해야 할 일을 간단히 정리합니다.
- 생성된 이슈 번호를 확인합니다. 예: `#12`

## 2. 새 브랜치 생성

최신 기본 브랜치를 기준으로 작업 브랜치를 생성합니다.

```bash
git switch main
git pull origin main
git switch -c feat/12-feature-name
```

브랜치 이름은 `작업유형/이슈번호-간단한-설명` 형식을 권장합니다.

- 기능 개발: `feat/12-login`
- 버그 수정: `fix/13-login-error`
- 문서 작업: `docs/14-update-readme`

## 3. 작업 후 Pull Request 생성

작업을 완료하면 변경 사항을 커밋하고 원격 저장소에 올립니다.

```bash
git add .
git commit -m "feat: 로그인 기능 구현"
git push -u origin feat/12-feature-name
```

GitHub에서 Pull Request를 생성한 뒤 PR 템플릿의 항목을 작성합니다.

- 작업 내용과 주요 변경 사항을 요약합니다.
- 관련 이슈를 연결합니다. 예: `Closes #12`
- 테스트 방법이나 확인이 필요한 내용을 작성합니다.
- 리뷰를 받은 뒤 기본 브랜치에 병합합니다.

## 4. 작업 브랜치 삭제

PR이 병합된 것을 확인한 뒤 작업 브랜치를 삭제합니다.

```bash
git switch main
git pull origin main
git branch -d feat/12-feature-name
git push origin --delete feat/12-feature-name
```

병합되지 않은 브랜치는 실수로 삭제하지 않도록 주의합니다.
