"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import ReactMarkdown from "react-markdown";
import { useAuth } from "@/context/AuthContext";
import TopBar from "@/components/TopBar";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

interface ReportSection {
    id: string;
    title: string;
    content?: string;
    type: 'overview' | 'company' | 'summary';
    companies?: { name: string; content: string }[];
}

interface Report {
    id: string;
    report_type: string;
    status: string;
    html_content: string;
    completed_at: string | null;
}

interface Project {
    id: string;
    name: string;
    description: string;
}

interface Message {
    id: string;
    message: string;
    is_bot: boolean;
    created_at: string;
    active_modes?: string[];
}

export default function ReportPage() {
    const { token, isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();
    const params = useParams();
    const projectId = params.id as string;
    const reportId = params.reportId as string;

    const [project, setProject] = useState<Project | null>(null);
    const [report, setReport] = useState<Report | null>(null);
    const [sections, setSections] = useState<ReportSection[]>([]);
    const [activeSection, setActiveSection] = useState<string>("");
    const [messages, setMessages] = useState<Message[]>([]);
    const [newMessage, setNewMessage] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const [isLoading, setIsLoading] = useState(true);

    // Collapsible states
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [chatCollapsed, setChatCollapsed] = useState(false);

    // Mobile responsive states
    const [isMobile, setIsMobile] = useState(false);
    const [mobileFullscreenPanel, setMobileFullscreenPanel] = useState<'sidebar' | 'chat' | null>(null);

    const wsRef = useRef<WebSocket | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const mainContentRef = useRef<HTMLDivElement>(null);

    // Mobile viewport detection
    useEffect(() => {
        const checkMobile = () => {
            const mobile = window.innerWidth <= 768;
            setIsMobile(mobile);
            if (mobile) {
                setSidebarCollapsed(true);
                setChatCollapsed(true);
                setMobileFullscreenPanel(null);
            }
        };
        checkMobile();
        window.addEventListener('resize', checkMobile);
        return () => window.removeEventListener('resize', checkMobile);
    }, []);

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push("/login");
        }
    }, [authLoading, isAuthenticated, router]);

    useEffect(() => {
        if (token && projectId && reportId) {
            fetchData();
            connectWebSocket();
        }
        return () => { wsRef.current?.close(); };
    }, [token, projectId, reportId]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // Scroll spy for active section
    useEffect(() => {
        if (!mainContentRef.current || sections.length === 0) return;

        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach((entry) => {
                    if (entry.isIntersecting) {
                        setActiveSection(entry.target.id);
                    }
                });
            },
            { rootMargin: '-20% 0px -70% 0px' }
        );

        sections.forEach((section) => {
            const el = document.getElementById(section.id);
            if (el) observer.observe(el);
        });

        return () => observer.disconnect();
    }, [sections]);

    const fetchData = async () => {
        try {
            // Fetch project
            const projRes = await fetch(`${API_URL}/api/projects/${projectId}/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (projRes.ok) {
                const projData = await projRes.json();
                setProject(projData);
            }

            // Fetch report details
            const reportRes = await fetch(`${API_URL}/api/reports/project/${projectId}/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (reportRes.ok) {
                const reportsData = await reportRes.json();
                const currentReport = reportsData.find((r: Report) => r.id === reportId);
                if (currentReport) {
                    setReport(currentReport);

                    // Fetch structured sections from API
                    const sectionsRes = await fetch(
                        `${API_URL}/api/reports/project/${projectId}/${reportId}/sections/`,
                        { headers: { Authorization: `Bearer ${token}` } }
                    );

                    if (sectionsRes.ok) {
                        const sectionsData = await sectionsRes.json();
                        if (sectionsData.sections && sectionsData.sections.length > 0) {
                            setSections(sectionsData.sections);
                            setActiveSection(sectionsData.sections[0].id);
                        }
                    }
                }
            }
        } catch (error) {
            console.error("Failed to fetch data:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const connectWebSocket = () => {
        const ws = new WebSocket(`${WS_URL}/ws/projects/${projectId}/chat/?token=${token}`);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "history") {
                setMessages(data.messages);
            } else if (data.type === "message") {
                setMessages((prev) => [...prev, data.message]);
                setIsTyping(false);
            } else if (data.type === "status") {
                setIsTyping(data.status === "thinking");
            }
        };
        wsRef.current = ws;
    };

    const sendMessage = () => {
        if (!newMessage.trim() || !wsRef.current) return;
        wsRef.current.send(JSON.stringify({
            type: "message",
            message: newMessage,
        }));
        setNewMessage("");
        if (textareaRef.current) {
            textareaRef.current.style.height = "auto";
        }
    };

    const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        setNewMessage(e.target.value);
        e.target.style.height = "auto";
        e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
    };

    const scrollToSection = (sectionId: string) => {
        const el = document.getElementById(sectionId);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'start' });
            setActiveSection(sectionId);
        }
    };

    if (authLoading || isLoading) {
        return (
            <div className="loading" style={{ height: "100vh" }}>
                <div className="spinner"></div>
            </div>
        );
    }

    return (
        <>
            <TopBar showBackToDashboard={false} />
            <div className="page-with-topbar">
                <div style={{ display: "flex", height: "calc(100vh - 48px)", overflow: "hidden" }}>

                    {/* LEFT SIDEBAR - Report Sections TOC */}
                    <aside style={{
                        width: isMobile && mobileFullscreenPanel === 'sidebar'
                            ? "100vw"
                            : sidebarCollapsed ? "0px" : "280px",
                        minWidth: isMobile && mobileFullscreenPanel === 'sidebar'
                            ? "100vw"
                            : sidebarCollapsed ? "0px" : "280px",
                        background: "var(--color-surface-elevated)",
                        borderRight: (sidebarCollapsed && mobileFullscreenPanel !== 'sidebar') ? "none" : "1px solid var(--color-border)",
                        display: isMobile && mobileFullscreenPanel === 'chat' ? "none" : "flex",
                        flexDirection: "column",
                        transition: isMobile ? "none" : "all 0.3s ease",
                        overflow: "hidden",
                        position: isMobile && mobileFullscreenPanel === 'sidebar' ? "fixed" : "relative",
                        top: isMobile && mobileFullscreenPanel === 'sidebar' ? "48px" : "auto",
                        left: isMobile && mobileFullscreenPanel === 'sidebar' ? "0" : "auto",
                        height: isMobile && mobileFullscreenPanel === 'sidebar' ? "calc(100vh - 48px)" : "auto",
                        zIndex: isMobile && mobileFullscreenPanel === 'sidebar' ? 1000 : "auto"
                    }}>
                        {/* Close button for mobile fullscreen sidebar */}
                        {isMobile && mobileFullscreenPanel === 'sidebar' && (
                            <button
                                onClick={() => {
                                    setMobileFullscreenPanel(null);
                                    setSidebarCollapsed(true);
                                }}
                                style={{
                                    position: "absolute",
                                    top: "12px",
                                    right: "12px",
                                    width: "32px",
                                    height: "32px",
                                    background: "var(--color-surface-muted)",
                                    border: "1px solid var(--color-border)",
                                    borderRadius: "var(--radius-sm)",
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    zIndex: 10,
                                    color: "var(--color-text)"
                                }}
                                title="Close sidebar"
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M18 6L6 18M6 6l12 12" />
                                </svg>
                            </button>
                        )}

                        {/* Back to Project */}
                        <div style={{ padding: "16px", borderBottom: "1px solid var(--color-border)" }}>
                            <Link
                                href={`/projects/${projectId}`}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                    padding: "10px 12px",
                                    background: "var(--color-surface-muted)",
                                    color: "var(--color-text)",
                                    borderRadius: "var(--radius-sm)",
                                    fontSize: "13px",
                                    fontWeight: 500,
                                    textDecoration: "none",
                                    transition: "background 0.2s ease"
                                }}
                            >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M19 12H5M12 19l-7-7 7-7" />
                                </svg>
                                Back to Project
                            </Link>
                        </div>

                        {/* Report Title */}
                        <div style={{ padding: "16px", borderBottom: "1px solid var(--color-border)" }}>
                            <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                                {report?.report_type ? `${report.report_type} Report` : 'Analysis Report'}
                            </span>
                            <h3 style={{ margin: "8px 0 0", fontSize: "15px", fontWeight: 600, color: "var(--color-heading)" }}>
                                {project?.name || "Report"}
                            </h3>
                        </div>

                        {/* Section TOC */}
                        <div style={{ flex: 1, overflow: "auto", padding: "8px" }}>
                            <div style={{ padding: "8px 12px", marginBottom: "4px" }}>
                                <span style={{ fontSize: "10px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>
                                    Sections
                                </span>
                            </div>
                            {sections.map((section, index) => (
                                <button
                                    key={section.id}
                                    onClick={() => scrollToSection(section.id)}
                                    style={{
                                        width: "100%",
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "10px",
                                        padding: "10px 12px",
                                        marginBottom: "2px",
                                        border: "none",
                                        borderRadius: "var(--radius-sm)",
                                        background: activeSection === section.id ? "rgba(24, 54, 97, 0.15)" : "transparent",
                                        color: activeSection === section.id ? "var(--color-secondary)" : "var(--color-text)",
                                        fontSize: "13px",
                                        cursor: "pointer",
                                        textAlign: "left",
                                        transition: "all 0.15s ease",
                                        borderLeft: activeSection === section.id ? "3px solid var(--color-primary)" : "3px solid transparent"
                                    }}
                                >
                                    <span style={{
                                        width: "20px",
                                        height: "20px",
                                        borderRadius: "50%",
                                        background: activeSection === section.id ? "var(--color-primary)" : "var(--color-surface-muted)",
                                        display: "flex",
                                        alignItems: "center",
                                        justifyContent: "center",
                                        fontSize: "10px",
                                        fontWeight: 600,
                                        color: activeSection === section.id ? "#fff" : "var(--color-text-muted)",
                                        flexShrink: 0
                                    }}>
                                        {index + 1}
                                    </span>
                                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                        {section.title}
                                    </span>
                                </button>
                            ))}
                        </div>
                    </aside>

                    {/* Sidebar Toggle Button */}
                    {!(isMobile && mobileFullscreenPanel) && (
                        <button
                            onClick={() => {
                                if (isMobile) {
                                    if (sidebarCollapsed) {
                                        setMobileFullscreenPanel('sidebar');
                                        setSidebarCollapsed(false);
                                    } else {
                                        setMobileFullscreenPanel(null);
                                        setSidebarCollapsed(true);
                                    }
                                } else {
                                    setSidebarCollapsed(!sidebarCollapsed);
                                }
                            }}
                            style={{
                                position: "absolute",
                                left: sidebarCollapsed ? "0" : "280px",
                                top: "50%",
                                transform: "translateY(-50%)",
                                width: "20px",
                                height: "40px",
                                background: "var(--color-surface-elevated)",
                                border: "1px solid var(--color-border)",
                                borderLeft: "none",
                                borderRadius: "0 6px 6px 0",
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                zIndex: 10,
                                transition: isMobile ? "none" : "left 0.3s ease",
                                color: "var(--color-text-muted)"
                            }}
                        >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d={sidebarCollapsed ? "M9 18l6-6-6-6" : "M15 18l-6-6 6-6"} />
                            </svg>
                        </button>
                    )}

                    {/* MAIN CONTENT AREA - Report Content */}
                    <main
                        ref={mainContentRef}
                        style={{
                            flex: 1,
                            overflow: "auto",
                            padding: "24px",
                            background: "var(--color-background)",
                            scrollbarWidth: "none",
                            msOverflowStyle: "none",
                            display: isMobile && mobileFullscreenPanel ? "none" : "block"
                        }}
                        className="hide-scrollbar"
                    >
                        {/* Report Header */}
                        <div style={{ marginBottom: "24px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                                <div style={{
                                    width: "48px",
                                    height: "48px",
                                    background: "var(--gradient-primary)",
                                    borderRadius: "12px",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontSize: "24px"
                                }}>
                                    🔍
                                </div>
                                <div>
                                    <h1 style={{ margin: 0, fontSize: "22px", fontWeight: 700, color: "var(--color-heading)" }}>
                                        {report?.report_type === 'social' ? 'Social Media Analysis Report' :
                                            report?.report_type === 'tracxn' ? 'Tracxn Market Report' :
                                                'Crunchbase Analysis Report'}
                                    </h1>
                                    <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--color-text-muted)" }}>
                                        {project?.name} • {report?.completed_at ? new Date(report.completed_at).toLocaleDateString() : 'In Progress'}
                                    </p>
                                </div>
                            </div>
                        </div>

                        {/* Report Sections */}
                        <div style={{
                            background: "var(--color-surface-elevated)",
                            borderRadius: "var(--radius-lg)",
                            border: "1px solid var(--color-border)",
                            overflow: "hidden"
                        }}>
                            {sections.map((section, index) => (
                                <div
                                    key={section.id}
                                    id={section.id}
                                    style={{
                                        padding: "24px",
                                        borderBottom: index < sections.length - 1 ? "1px solid var(--color-border)" : "none",
                                        scrollMarginTop: "80px"
                                    }}
                                >
                                    <h2 style={{
                                        margin: "0 0 16px",
                                        fontSize: "18px",
                                        fontWeight: 600,
                                        color: "var(--color-heading)",
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "12px"
                                    }}>
                                        <span style={{
                                            width: "28px",
                                            height: "28px",
                                            borderRadius: "50%",
                                            background: "var(--color-primary)",
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                            fontSize: "12px",
                                            fontWeight: 600,
                                            color: "#fff"
                                        }}>
                                            {index + 1}
                                        </span>
                                        {section.title}
                                    </h2>

                                    {/* Render based on section type */}
                                    {section.type === 'company' && section.companies ? (
                                        // Company sections with collapsible details
                                        <div className="companies-list">
                                            {section.companies.map((company, compIdx) => (
                                                <details
                                                    key={compIdx}
                                                    className="company-report"
                                                    style={{
                                                        marginBottom: "8px",
                                                        border: "1px solid var(--color-border)",
                                                        borderRadius: "var(--radius-sm)",
                                                        background: "var(--color-surface-muted)"
                                                    }}
                                                >
                                                    <summary style={{
                                                        padding: "12px 16px",
                                                        cursor: "pointer",
                                                        fontWeight: 500,
                                                        fontSize: "14px",
                                                        color: "var(--color-heading)",
                                                        listStyle: "none"
                                                    }}>
                                                        {company.name}
                                                    </summary>
                                                    <div
                                                        className="report-content company-content markdown-content"
                                                        style={{
                                                            padding: "16px",
                                                            borderTop: "1px solid var(--color-border)",
                                                            fontSize: "14px",
                                                            lineHeight: "1.7",
                                                            color: "var(--color-text)"
                                                        }}
                                                    >
                                                        <ReactMarkdown>{company.content}</ReactMarkdown>
                                                    </div>
                                                </details>
                                            ))}
                                        </div>
                                    ) : (
                                        // Overview and summary sections with direct content
                                        <div
                                            className="report-content markdown-content"
                                            style={{
                                                fontSize: "14px",
                                                lineHeight: "1.7",
                                                color: "var(--color-text)"
                                            }}
                                        >
                                            <ReactMarkdown>{section.content || ''}</ReactMarkdown>
                                        </div>
                                    )}
                                </div>
                            ))}

                            {sections.length === 0 && (
                                <div style={{ padding: "48px", textAlign: "center", color: "var(--color-text-muted)" }}>
                                    <p>No report content available</p>
                                </div>
                            )}
                        </div>
                    </main>

                    {/* Chat Toggle Button */}
                    {!(isMobile && mobileFullscreenPanel) && (
                        <button
                            onClick={() => {
                                if (isMobile) {
                                    if (chatCollapsed) {
                                        setMobileFullscreenPanel('chat');
                                        setChatCollapsed(false);
                                    } else {
                                        setMobileFullscreenPanel(null);
                                        setChatCollapsed(true);
                                    }
                                } else {
                                    setChatCollapsed(!chatCollapsed);
                                }
                            }}
                            style={{
                                position: "absolute",
                                right: chatCollapsed ? "0" : "360px",
                                top: "50%",
                                transform: "translateY(-50%)",
                                width: "20px",
                                height: "40px",
                                background: "var(--color-surface-elevated)",
                                border: "1px solid var(--color-border)",
                                borderRight: "none",
                                borderRadius: "6px 0 0 6px",
                                cursor: "pointer",
                                display: "flex",
                                alignItems: "center",
                                justifyContent: "center",
                                zIndex: 10,
                                transition: isMobile ? "none" : "right 0.3s ease",
                                color: "var(--color-text-muted)"
                            }}
                        >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d={chatCollapsed ? "M15 18l-6-6 6-6" : "M9 18l6-6-6-6"} />
                            </svg>
                        </button>
                    )}

                    {/* RIGHT SIDEBAR - Chat */}
                    <aside style={{
                        width: isMobile && mobileFullscreenPanel === 'chat'
                            ? "100vw"
                            : chatCollapsed ? "0px" : "360px",
                        minWidth: isMobile && mobileFullscreenPanel === 'chat'
                            ? "100vw"
                            : chatCollapsed ? "0px" : "360px",
                        background: "var(--color-surface-elevated)",
                        borderLeft: (chatCollapsed && mobileFullscreenPanel !== 'chat') ? "none" : "1px solid var(--color-border)",
                        display: isMobile && mobileFullscreenPanel === 'sidebar' ? "none" : "flex",
                        flexDirection: "column",
                        transition: isMobile ? "none" : "all 0.3s ease",
                        overflow: "hidden",
                        position: isMobile && mobileFullscreenPanel === 'chat' ? "fixed" : "relative",
                        top: isMobile && mobileFullscreenPanel === 'chat' ? "48px" : "auto",
                        right: isMobile && mobileFullscreenPanel === 'chat' ? "0" : "auto",
                        height: isMobile && mobileFullscreenPanel === 'chat' ? "calc(100vh - 48px)" : "auto",
                        zIndex: isMobile && mobileFullscreenPanel === 'chat' ? 1000 : "auto"
                    }}>
                        {/* Close button for mobile fullscreen chat */}
                        {isMobile && mobileFullscreenPanel === 'chat' && (
                            <button
                                onClick={() => {
                                    setMobileFullscreenPanel(null);
                                    setChatCollapsed(true);
                                }}
                                style={{
                                    position: "absolute",
                                    top: "12px",
                                    right: "12px",
                                    width: "32px",
                                    height: "32px",
                                    background: "var(--color-surface-muted)",
                                    border: "1px solid var(--color-border)",
                                    borderRadius: "var(--radius-sm)",
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    zIndex: 10,
                                    color: "var(--color-text)"
                                }}
                                title="Close chat"
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M18 6L6 18M6 6l12 12" />
                                </svg>
                            </button>
                        )}

                        {/* Chat Header */}
                        <div style={{
                            padding: "16px",
                            borderBottom: "1px solid var(--color-border)",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px"
                        }}>
                            <span style={{ fontSize: "18px" }}>💬</span>
                            <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 600 }}>AI Assistant</h3>
                        </div>

                        {/* Chat Messages */}
                        <div style={{
                            flex: 1,
                            overflow: "auto",
                            padding: "16px",
                            display: "flex",
                            flexDirection: "column",
                            gap: "12px"
                        }}>
                            {messages.map((msg) => (
                                <div
                                    key={msg.id}
                                    style={{
                                        alignSelf: msg.is_bot ? "flex-start" : "flex-end",
                                        maxWidth: "85%",
                                        padding: "10px 14px",
                                        borderRadius: "var(--radius-md)",
                                        background: msg.is_bot ? "var(--color-surface-muted)" : "var(--gradient-primary)",
                                        color: msg.is_bot ? "var(--color-text)" : "#fff",
                                        fontSize: "13px",
                                        lineHeight: "1.5"
                                    }}
                                >
                                    {msg.message}
                                </div>
                            ))}
                            {isTyping && (
                                <div style={{
                                    alignSelf: "flex-start",
                                    padding: "10px 14px",
                                    borderRadius: "var(--radius-md)",
                                    background: "var(--color-surface-muted)",
                                    color: "var(--color-text-muted)",
                                    fontSize: "13px"
                                }}>
                                    Thinking...
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Chat Input */}
                        <div style={{
                            padding: "12px",
                            borderTop: "1px solid var(--color-border)",
                            display: "flex",
                            gap: "8px"
                        }}>
                            <textarea
                                ref={textareaRef}
                                value={newMessage}
                                onChange={handleTextareaChange}
                                onKeyDown={(e) => {
                                    if (e.key === "Enter" && !e.shiftKey) {
                                        e.preventDefault();
                                        sendMessage();
                                    }
                                }}
                                placeholder="Ask about this report..."
                                style={{
                                    flex: 1,
                                    padding: "10px 12px",
                                    borderRadius: "var(--radius-sm)",
                                    border: "1px solid var(--color-border)",
                                    background: "var(--color-surface-muted)",
                                    color: "var(--color-text)",
                                    fontSize: "13px",
                                    resize: "none",
                                    minHeight: "40px",
                                    maxHeight: "120px"
                                }}
                                rows={1}
                            />
                            <button
                                onClick={sendMessage}
                                disabled={!newMessage.trim()}
                                style={{
                                    padding: "10px 16px",
                                    background: newMessage.trim() ? "var(--gradient-primary)" : "var(--color-surface-muted)",
                                    border: "none",
                                    borderRadius: "var(--radius-sm)",
                                    color: newMessage.trim() ? "#fff" : "var(--color-text-muted)",
                                    cursor: newMessage.trim() ? "pointer" : "not-allowed",
                                    fontSize: "13px",
                                    fontWeight: 500
                                }}
                            >
                                Send
                            </button>
                        </div>
                    </aside>
                </div>
            </div>
        </>
    );
}
