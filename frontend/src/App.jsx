import { useState } from "react";
import Header from "./components/Header";
import AgentWorkspace from "./pages/AgentWorkspace";
import AuthScreen from "./pages/AuthScreen";
import CustomerChat from "./pages/CustomerChat";
import Dashboard from "./pages/Dashboard";
import FaqPage from "./pages/FaqPage";
import InquiryDetail from "./pages/InquiryDetail";
import InquiryForm from "./pages/InquiryForm";
import InquiryHistory from "./pages/InquiryHistory";
import "./app-overrides.css";
import "./integration.css";

export default function App() {
  const [view, setView] = useState("login");
  const [selectedInquiryId, setSelectedInquiryId] = useState(null);
  const [inquiryDraft, setInquiryDraft] = useState("");
  const authMode = view === "signup" ? "signup" : "login";
  const isAuth = view === "login" || view === "signup";

  const changeView = (nextView) => {
    if (nextView === "inquiry-new") setInquiryDraft("");
    setView(nextView);
  };
  const createFromChat = (content) => { setInquiryDraft(content); setView("inquiry-new"); };
  const openInquiry = (id) => { setSelectedInquiryId(id); setView("inquiry-detail"); };

  const renderPage = () => {
    if (isAuth) return <AuthScreen mode={authMode} onEnter={() => setView("customer")} onModeChange={setView} />;
    if (view === "customer") return <CustomerChat onCreateInquiry={createFromChat} />;
    if (view === "faq") return <FaqPage onAsk={() => setView("customer")} />;
    if (view === "inquiry-new") return <InquiryForm initialContent={inquiryDraft} onCancel={() => setView("customer")} onViewHistory={() => setView("inquiries")} onOpen={openInquiry} />;
    if (view === "inquiries") return <InquiryHistory onSelect={openInquiry} onCreate={() => changeView("inquiry-new")} />;
    if (view === "inquiry-detail") return <InquiryDetail inquiryId={selectedInquiryId} onBack={() => setView("inquiries")} />;
    if (view === "dashboard") return <Dashboard />;
    return <AgentWorkspace />;
  };

  return <div className="app-shell"><Header view={view} isAuth={isAuth} onViewChange={changeView} />{renderPage()}</div>;
}
