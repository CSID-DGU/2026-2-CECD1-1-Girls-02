const CUSTOMER_MENU = [
  ["customer", "고객 챗봇"],
  ["faq", "FAQ"],
  ["inquiry-new", "1:1 문의"],
  ["inquiries", "문의 내역"],
];
const ADMIN_MENU = [
  ["agent", "상담원 워크스페이스"],
  ["dashboard", "대시보드"],
];

export default function Header({ view, isAuth, onViewChange }) {
  const isActive = (key) => view === key || (key === "inquiries" && view === "inquiry-detail");
  return <header className="topbar">
    <button className="brand" onClick={() => onViewChange("customer")}>
      <span className="brand-mark">e</span><span>eVOC</span><small>AI CUSTOMER CARE</small>
    </button>
    {!isAuth && <nav>
      {[...CUSTOMER_MENU, ...ADMIN_MENU].map(([key, label]) => (
        <button key={key} className={isActive(key) ? "active" : ""} onClick={() => onViewChange(key)}>{label}</button>
      ))}
    </nav>}
    {!isAuth && <button className="login-link" onClick={() => onViewChange("login")}>로그아웃</button>}
    {isAuth && <span className="demo-badge">DEMO MODE</span>}
  </header>;
}
