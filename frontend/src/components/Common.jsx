export function ErrorBox({ error }) {
  if (!error) return null;
  return <p className="api-error" role="alert">{error.message ?? String(error)}{error.code ? ` (${error.code})` : ""}</p>;
}

/** zeroBased: FAQ·매장 API는 0부터, 관리자 목록은 1부터 시작한다. */
export function Pagination({ page, totalPages, onChange, zeroBased = false }) {
  if (!totalPages || totalPages <= 1) return null;
  const current = zeroBased ? page + 1 : page;
  return <div className="pager">
    <button type="button" className="secondary" disabled={current <= 1} onClick={() => onChange(page - 1)}>이전</button>
    <span>{current} / {totalPages}</span>
    <button type="button" className="secondary" disabled={current >= totalPages} onClick={() => onChange(page + 1)}>다음</button>
  </div>;
}

export function SourceList({ sources, emptyText = "표시할 공식 근거가 없습니다." }) {
  if (!sources?.length) return <div className="no-evidence"><span>i</span><div><strong>{emptyText}</strong></div></div>;
  return <div className="source-list">
    {sources.map((source, index) => <article className="source-card" key={`${source.documentId ?? source.chunkId}-${index}`}>
      <div className="source-topline"><span className="source-kind">공식 근거</span>{source.documentId && <span className="approved">{source.documentId}</span>}</div>
      <h4>{source.title ?? source.documentTitle ?? source.documentId ?? source.chunkId}</h4>
      {source.excerpt && <p>{source.excerpt}</p>}
    </article>)}
  </div>;
}

export function Loading({ text = "불러오는 중..." }) {
  return <p className="mock-note" aria-live="polite">{text}</p>;
}
