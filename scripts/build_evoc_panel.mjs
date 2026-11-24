import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { FileBlob, PresentationFile } from "file:///C:/Program%20Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1119-907-0_26.1119.907.0_x64__3k8sg7r9htsxt/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

const workspaceDir = process.cwd();
const source = "C:\\Users\\20231\\Downloads\\eVOC_panel.pptx";
const outputDir = path.join(workspaceDir, "output");
const stagingDir = path.join(workspaceDir, ".codex-finalizer");
const candidatePath = path.join(stagingDir, "eVOC_panel_revised_candidate.pptx");
const finalPath = path.join(outputDir, "eVOC_panel_revised.pptx");
const skillDir = "C:\\Users\\20231\\.codex\\plugins\\cache\\openai-primary-runtime\\presentations\\26.1119.11507\\skills\\presentations";
const runtimePython = "C:\\Program Files\\WindowsApps\\OpenAI.CodexPrimaryRuntime.v26-1119-907-0_26.1119.907.0_x64__3k8sg7r9htsxt\\dependencies\\python\\python.exe";

const text = {
  teamName: "eVOC",
  teamInfo: "팀원 : 김규리, 권수현, 박현서, 최희수  /  지도교수 : 이우진 교수님  /  산업체 멘토 : 서인호 (㈜씨엔티테크)",
  title: "웹 기반 Local LLM 대화형 eVOC 개발\\n(RAG 기반 커스터마이징)",
  overview: "온라인으로 접수되는 고객 문의와 VOC를 대상으로, 정책·공식 문서를 근거로 AI가 답변을 지원하는 웹 서비스 eVOC를 개발한다. 고객은 챗봇으로 1차 안내를 받고, 자동 처리가 어려운 문의는 담당 직원에게 티켓으로 전달된다. 직원은 검색된 공식 근거와 Local LLM 답변 초안을 검토·수정해 고객에게 최종 답변을 제공한다.",
  goals: "상담원은 다양한 정책·약관 문서를 직접 검색해 답변을 작성해야 하므로 응대 시간이 길고 담당자별 답변 품질 편차가 발생한다.\\n검수된 공식 문서를 근거로 답변 초안을 생성하고, 근거 부족·개별 처리 문의는 상담원에게 이관하는 RAG 기반 업무 지원 시스템을 구축한다.\\n반복 문의 대응 시간을 줄이고, 답변의 출처·일관성·검토 가능성을 높인다.",
  results: "[설계 단계 완료] Backend·AI Orchestrator·RAG Retrieval 통합 아키텍처를 설계하고, PostgreSQL·Chroma·Ollama 기반 실행 환경을 구성했다.\\n[실험 계획] Baseline 대비 RAG 고도화 효과를 검증한다.\\nA(Baseline): Hybrid RAG(Dense + BM25 + Reranker)\\nB: A + Adaptive Routing, C: A + Corrective Retrieval\\n[목표 지표] Recall@3 85% 이상, 입력 토큰 30% 이상 절감, 기본형 대비 답변 품질 하락 2%p 이내, 이관 판단 F1 95% 이상\\n※ 실측 결과는 구현 및 평가 완료 후 업데이트 예정",
  process: "[시스템 처리 흐름] 고객 문의 → Backend → AI Orchestrator → RAG Retrieval → Ollama(Local LLM) → 상담원 이관 판단 → 응답\\n[RAG 파이프라인]\\n고객 질문·최근 대화 → 질문 유형·카테고리 판단 → 카테고리별 검색 범위 제한\\n→ Hybrid Search(Dense + BM25 → RRF) → Reranker 상위 3~5개 재정렬\\n→ 토큰 예산 컨텍스트 구성 → LLM 생성 또는 상담원 이관\\n※ 근거 부족·검색 품질 저하 시 생성 대신 상담원에게 이관\\n[데이터 적재 흐름] FAQ·VOC 수집 → 전처리·청킹·메타데이터 → 임베딩 생성 → Chroma 적재 → 실시간 검색 인덱스 반영",
  effects: "[활용 방안] 공공·민간 고객센터의 1차 응대 자동화, 신규 상담원 교육 및 답변 표준화 자료로 활용\\n[기대 효과] 상담원의 반복 업무와 응대 시간을 줄이고, 출처 기반 답변으로 신뢰도와 일관성을 높인다.\\n향후 사내 문의, 민원 상담 등 다른 도메인으로 확장할 수 있다.",
  teamRoles: "김규리: FAQ·VOC 정제, 청킹·메타데이터, Chroma 적재, AI 응답 오케스트레이션\\n권수현: FastAPI·PostgreSQL, 고객·관리자 API 및 화면, 티켓 처리 흐름\\n박현서: GPU 서버, Ollama 실행 환경, Local LLM 모델 운영\\n최희수: 임베딩·Hybrid Search·RRF·Reranker, 검색 품질 분석",
  mentorRoles: "산업체 요구사항 및 고객 문의 처리 흐름 자문\\n서비스 적용 관점의 기능·데이터·운영 피드백\\n개발 결과 검토 및 고도화 방향 제안",
};

async function saveBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(stagingDir, { recursive: true });
await fs.rm(finalPath, { force: true });

const presentation = await PresentationFile.importPptx(await FileBlob.load(source));
const setText = (id, value) => { presentation.resolve(id).text = value.replaceAll("\\n", "\n"); };

setText("sh/7qp4be9c", text.teamName);
setText("sh/ul4vaxgb", text.teamInfo);
setText("sh/wn6dc7eh", text.title);
setText("sh/547294r6", text.overview);
setText("sh/65g3298r", text.goals);
setText("sh/ts7md4r2", text.results);
setText("sh/sryl4zqx", text.process);
setText("sh/fu94fe98", text.effects);
setText("sh/utg3698n", text.teamRoles);
setText("sh/k3yl0zql", text.mentorRoles);

// The reference file includes a separate sample-only slide. The final panel is one page.
if (presentation.slides.length > 1) presentation.slides.delete([1]);

const panel = presentation.slides.getItem(0);
await saveBlob(path.join(stagingDir, "eVOC_panel_preview.png"), await presentation.export({ slide: panel, format: "png", scale: 1 }));
await (await PresentationFile.exportPptx(presentation)).save(candidatePath);

const { finalizePresentation } = await import(pathToFileURL(path.join(skillDir, "container_tools", "artifact_tool_utils.mjs")).href);
const finalized = await finalizePresentation({
  workspaceDir,
  candidatePath,
  finalPath,
  pythonExecutable: runtimePython,
  integrityValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_package_integrity.py"),
  layoutValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_layout_geometry.py"),
  layoutArgs: ["--expected-slide-size-emu", "32399288,43200638", "--validate-bullet-geometry", "--validate-heading-fit"],
  explicitTotalSlideCount: 1,
  requiredNativeTableOwnerSlides: [],
  fontPolicy: {
    basis: "reference",
    families: ["NanumSquare Neo OTF ExtraBold", "NanumSquare Neo OTF Bold", "NanumSquare Neo OTF Regular", "Gmarket Sans Bold", "Paperlogy 8 ExtraBold"],
    referencePath: source,
    referenceSha256: "39780b2a3582f1b19b9e97116dce27d2792458fcaa76a6e3d4704f27555e1dc2",
  },
  verifyArtifactToolImport: true,
  receiptPath: path.join(stagingDir, "eVOC_panel.validation.json"),
});

console.log(JSON.stringify({ finalPath, previewPath: path.join(stagingDir, "eVOC_panel_preview.png"), finalized }, null, 2));
