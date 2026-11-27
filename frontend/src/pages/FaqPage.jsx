import { useEffect, useMemo, useState } from "react";
import { getFaq, getFaqs } from "../api";
import { ErrorBox, Loading, Pagination } from "../components/Common";
import { formatDate } from "../lib/format";

const PAGE_SIZE = 10;

export default function FaqPage({ onAsk }) {
  const [categories, setCategories] = useState([]);
  const [categoryId, setCategoryId] = useState("");
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [openId, setOpenId] = useState(null);
  const [details, setDetails] = useState({});

  // FAQ 카테고리 목록 API가 없어서, 전체 FAQ에서 카테고리를 모은다.
  useEffect(() => {
    getFaqs({ size: 50 }).then((data) => {
      const unique = new Map(data.items.map((item) => [item.categoryId, item.categoryName]));
      setCategories([...unique].map(([id, name]) => ({ id, name })));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    getFaqs({ categoryId, keyword, page, size: PAGE_SIZE })
      .then((data) => { if (!cancelled) setResult(data); })
      .catch((caught) => { if (!cancelled) { setError(caught); setResult(null); } });
    return () => { cancelled = true; };
  }, [categoryId, keyword, page]);

  const toggle = async (faqId) => {
    setOpenId((current) => (current === faqId ? null : faqId));
    if (details[faqId]) return;
    try {
      const detail = await getFaq(faqId);
      setDetails((current) => ({ ...current, [faqId]: detail }));
    } catch (caught) {
      setDetails((current) => ({ ...current, [faqId]: { error: caught } }));
    }
  };

  const search = (event) => { event.preventDefault(); setPage(0); setKeyword(keywordInput.trim()); };
  const selectCategory = (id) => { setPage(0); setCategoryId(id); };
  const chips = useMemo(() => [{ id: "", name: "전체" }, ...categories], [categories]);

  return <main className="inquiry-page workspace">
    <div className="customer-page-heading"><div><p className="eyebrow">FAQ</p><h1>자주 묻는 질문</h1><p>궁금한 내용을 검색하거나 분류를 선택해 보세요.</p></div><button className="secondary" type="button" onClick={onAsk}>챗봇에게 질문하기</button></div>
    <section className="panel faq-panel">
      <form className="faq-search" onSubmit={search}><input value={keywordInput} onChange={(event) => setKeywordInput(event.target.value)} placeholder="검색어 (예: 쿠폰, 멤버십)" aria-label="FAQ 검색어" maxLength={100} /><button className="primary" type="submit">검색</button></form>
      <div className="chip-row" role="tablist">{chips.map((chip) => <button key={chip.id || "all"} type="button" role="tab" aria-selected={categoryId === chip.id} className={`chip ${categoryId === chip.id ? "selected" : ""}`} onClick={() => selectCategory(chip.id)}>{chip.name}</button>)}</div>
      <ErrorBox error={error} />
      {!result && !error && <Loading />}
      {result && result.items.length === 0 && <div className="empty-state"><span>i</span><h2>검색 결과가 없습니다.</h2><p>다른 검색어를 입력하거나 챗봇에게 질문해 보세요.</p></div>}
      {result && result.items.length > 0 && <ul className="faq-list">
        {result.items.map((item) => {
          const detail = details[item.faqId];
          const open = openId === item.faqId;
          return <li key={item.faqId} className={open ? "open" : ""}>
            <button type="button" className="faq-question" aria-expanded={open} onClick={() => toggle(item.faqId)}>
              <span className="source-kind">{item.categoryName}</span><strong>{item.title}</strong>{!open && <small>{item.preview}</small>}
            </button>
            {open && <div className="faq-answer">
              {!detail && <Loading />}
              {detail?.error && <ErrorBox error={detail.error} />}
              {detail?.content && <><p>{detail.content}</p><small>최종 수정 {formatDate(detail.updatedAt)}</small></>}
            </div>}
          </li>;
        })}
      </ul>}
      {result && <Pagination page={result.page} totalPages={result.totalPages} onChange={setPage} zeroBased />}
    </section>
  </main>;
}
