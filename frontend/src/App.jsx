import { useState } from "react";
import Header from "./components/Header";
import { createMockInquiry, INITIAL_MOCK_INQUIRIES } from "./data/mockInquiries";
import AgentWorkspace from "./pages/AgentWorkspace";
import AuthScreen from "./pages/AuthScreen";
import CustomerChat from "./pages/CustomerChat";
import InquiryDetail from "./pages/InquiryDetail";
import InquiryForm from "./pages/InquiryForm";
import InquiryHistory from "./pages/InquiryHistory";
import "./app-overrides.css";

export default function App() {
  const [view, setView] = useState("login");
  const [inquiries, setInquiries] = useState(() => INITIAL_MOCK_INQUIRIES.map((inquiry) => ({ ...inquiry })));
  const [selectedInquiryId, setSelectedInquiryId] = useState(null);
  const [inquiryDraft, setInquiryDraft] = useState("");
  const authMode = view === "signup" ? "signup" : "login";
  const isAuth = view === "login" || view === "signup";

  const changeView = (nextView) => {
    if (nextView === "inquiry-new") setInquiryDraft("");
    setView(nextView);
  };
  const createFromChat = (content) => { setInquiryDraft(content); setView("inquiry-new"); };
  const registerInquiry = (form) => {
    const inquiry = createMockInquiry(form, inquiries);
    setInquiries((current) => [inquiry, ...current]);
    setInquiryDraft("");
    return inquiry;
  };
  const openInquiry = (id) => { setSelectedInquiryId(id); setView("inquiry-detail"); };

  const renderPage = () => {
    if (isAuth) return <AuthScreen mode={authMode} onEnter={() => setView("customer")} onModeChange={setView} />;
    if (view === "customer") return <CustomerChat onCreateInquiry={createFromChat} />;
    if (view === "inquiry-new") return <InquiryForm initialContent={inquiryDraft} onRegister={registerInquiry} onCancel={() => setView("customer")} onViewHistory={() => setView("inquiries")} />;
    if (view === "inquiries") return <InquiryHistory inquiries={inquiries} onSelect={openInquiry} onCreate={() => changeView("inquiry-new")} />;
    if (view === "inquiry-detail") return <InquiryDetail inquiry={inquiries.find(({ id }) => id === selectedInquiryId)} onBack={() => setView("inquiries")} />;
    return <AgentWorkspace />;
  };

  return <div className="app-shell"><Header view={view} isAuth={isAuth} onViewChange={changeView} />{renderPage()}</div>;
}
