export default function Header({ view, isAuth, onViewChange }) {
  return <header className="topbar">
    <button className="brand" onClick={() => onViewChange("customer")}>
      <span className="brand-mark">e</span><span>eVOC</span><small>AI CUSTOMER CARE</small>
    </button>
    <nav>
      <button className={view === "customer" ? "active" : ""} onClick={() => onViewChange("customer")}>고객 챗봇</button>
      <button className={view === "inquiry-new" ? "active" : ""} onClick={() => onViewChange("inquiry-new")}>1:1 문의</button>
      <button className={["inquiries", "inquiry-detail"].includes(view) ? "active" : ""} onClick={() => onViewChange("inquiries")}>문의 내역</button>
      <button className={view === "agent" ? "active" : ""} onClick={() => onViewChange("agent")}>상담원 워크스페이스</button>
    </nav>
    {!isAuth && <button className="login-link" onClick={() => onViewChange("login")}>로그아웃</button>}
    {isAuth && <span className="demo-badge">DEMO MODE</span>}
  </header>;
}
