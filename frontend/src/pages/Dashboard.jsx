import { useEffect, useState } from "react";
import { getAiMetrics, getDashboardSummary, getHealth } from "../api";
import { ErrorBox, Loading } from "../components/Common";
import { formatNumber, formatPercent } from "../lib/format";

const COUNT_LABELS = [
  ["total", "전체"], ["received", "AI 초안 생성 중"], ["aiDrafted", "검토 대기"], ["inReview", "담당자 확인 중"], ["answered", "답변 완료"], ["closed", "종료"],
];
const HEALTH_LABELS = [["database", "PostgreSQL"], ["aiService", "Ollama"], ["vectorStore", "Chroma"]];

export default function Dashboard() {
  const [period, setPeriod] = useState({ from: "", to: "" });
  const [applied, setApplied] = useState({ from: "", to: "" });
  const [purpose, setPurpose] = useState("");
  const [summary, setSummary] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setError(null);
    getDashboardSummary(applied).then(setSummary).catch(setError);
  }, [applied]);
  useEffect(() => {
    getAiMetrics({ ...applied, purpose }).then(setMetrics).catch(setError);
  }, [applied, purpose]);
  useEffect(() => { getHealth().then(setHealth).catch(() => setHealth(null)); }, []);

  const apply = (event) => { event.preventDefault(); setApplied(period); };

  return <main className="workspace dashboard">
    <div className="customer-page-heading"><div><p className="eyebrow">ADMIN DASHBOARD</p><h1>처리 현황</h1><p>{summary ? `${summary.period.from} ~ ${summary.period.to} (KST)` : "기간을 선택하지 않으면 최근 30일 기준입니다."}</p></div>
      <form className="period-form" onSubmit={apply}><input type="date" value={period.from} onChange={(event) => setPeriod({ ...period, from: event.target.value })} aria-label="시작일" /><span>~</span><input type="date" value={period.to} onChange={(event) => setPeriod({ ...period, to: event.target.value })} aria-label="종료일" /><button className="primary" type="submit">조회</button></form>
    </div>
    <ErrorBox error={error} />
    {health && <section className="panel health-row"><strong>서비스 상태</strong>{HEALTH_LABELS.map(([key, label]) => <span key={key} className={`inquiry-status ${health[key] === "UP" ? "answered" : "escalated"}`}>{label} {health[key]}</span>)}</section>}
    {!summary && !error && <Loading />}
    {summary && <>
      <section className="stat-grid">{COUNT_LABELS.map(([key, label]) => <div className="panel stat-card" key={key}><span>{label}</span><strong>{formatNumber(summary.inquiryCounts[key])}</strong></div>)}</section>
      <div className="dashboard-grid">
        <section className="panel dashboard-card"><h3>많이 들어온 문의 분류</h3>
          {summary.topCategories.length === 0 ? <p className="mock-note">기간 내 분류된 문의가 없습니다.</p>
            : <ol className="rank-list">{summary.topCategories.map((item) => <li key={item.categoryId}><span>{item.categoryName}</span><strong>{item.count}건</strong></li>)}</ol>}
        </section>
        <section className="panel dashboard-card"><h3>AI 처리 요약 (문의 초안)</h3>
          <dl className="metric-list"><div><dt>초안 생성</dt><dd>{formatNumber(summary.aiSummary.draftGeneratedCount, "건")}</dd></div><div><dt>담당자 이관</dt><dd>{formatNumber(summary.aiSummary.handoffCount, "건")}</dd></div><div><dt>평균 응답 시간</dt><dd>{formatNumber(summary.aiSummary.averageLatencyMs, "ms")}</dd></div></dl>
        </section>
      </div>
    </>}
    <section className="panel dashboard-card">
      <div className="card-heading"><h3>Local LLM 처리 성능</h3><select value={purpose} onChange={(event) => setPurpose(event.target.value)} aria-label="처리 유형"><option value="">전체</option><option value="INQUIRY_DRAFT">문의 초안</option><option value="CHAT_ANSWER">챗봇 답변</option></select></div>
      {!metrics ? <Loading /> : metrics.totalRuns === 0 ? <p className="mock-note">기간 내 AI 실행 기록이 없습니다.</p> : <dl className="metric-list wide">
        <div><dt>실행 수</dt><dd>{formatNumber(metrics.totalRuns, "회")}</dd></div>
        <div><dt>성공률</dt><dd>{formatPercent(metrics.successRate)}</dd></div>
        <div><dt>평균 응답</dt><dd>{formatNumber(metrics.averageLatencyMs, "ms")}</dd></div>
        <div><dt>p95 응답</dt><dd>{formatNumber(metrics.p95LatencyMs, "ms")}</dd></div>
        <div><dt>답변 비율</dt><dd>{formatPercent(metrics.answerRate)}</dd></div>
        <div><dt>이관 비율</dt><dd>{formatPercent(metrics.handoffRate)}</dd></div>
        <div><dt>출처 포함 비율</dt><dd>{formatPercent(metrics.sourceAttachedRate)}</dd></div>
        <div><dt>평균 입력 토큰</dt><dd>{formatNumber(metrics.averageInputTokens)}</dd></div>
        <div><dt>평균 출력 토큰</dt><dd>{formatNumber(metrics.averageOutputTokens)}</dd></div>
        <div><dt>tokens/s</dt><dd>{formatNumber(metrics.averageTokensPerSecond)}</dd></div>
      </dl>}
    </section>
  </main>;
}
