"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import TopBar from "@/components/TopBar";
import ExpandableText from "@/components/ExpandableText";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

// Progress step for report generation
interface ProgressStep {
    step_number: number;
    step_key: string;
    step_name: string;
    step_description: string;
    status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
    progress_percent: number;
    started_at: string | null;
    completed_at: string | null;
    duration_seconds: number | null;
    metadata: Record<string, any>;
    details: Array<{
        type: string;
        message: string;
        timestamp: number;
        data?: Record<string, any>;
    }>;
    error_message: string;
}

// Time estimation for remaining report generation
interface TimeEstimate {
    total_estimated_seconds: number;
    remaining_seconds: number;
    elapsed_seconds: number;
    confidence: 'high' | 'medium' | 'low';
    progress_percent: number;
    steps: Array<{
        step_key: string;
        step_name: string;
        avg_duration: number;
        sample_count: number;
        confidence: string;
        is_completed: boolean;
        is_running: boolean;
        actual_duration: number | null;
    }>;
}

interface Report {
    id: string;
    report_type: string;
    status: string;
    progress: number;
    current_step: string;
    is_outdated: boolean;
    completed_at: string | null;
    html_content: string;
    progress_steps?: ProgressStep[];
    time_estimate?: TimeEstimate;
}

interface ProjectInputs {
    startup_name: string;
    startup_description: string;
    target_audience: string;
    current_stage: string;
    business_model: string;
    geographic_focus: string;
    research_goal: string;
    time_range: string;
    inspiration_sources: string;
    completion_status: string;
    ai_generated_fields?: Record<string, boolean>;  // Track which fields were filled by AI
    // Crunchbase report fields
    extracted_keywords?: string[];
    target_description?: string;
}

interface Project {
    id: string;
    name: string;
    description: string;
    inputs: ProjectInputs;
}

interface Message {
    id: string;
    message: string;
    is_bot: boolean;
    created_at: string;
    active_modes?: string[];  // Modes active when this message was generated
}

interface ChatMode {
    id: string;
    name: string;
    description: string;
    icon: string;
    enabled: boolean;
}

const REPORT_TYPES = [
    { type: "crunchbase", label: "Crunchbase Analysis", icon: "🔍", description: "Competitor intelligence and funding data" },
    { type: "tracxn", label: "Tracxn Insights", icon: "📊", description: "Startup landscape and market trends" },
    { type: "social", label: "Social Analysis", icon: "📱", description: "Brand mentions and social sentiment" },
    { type: "pitch_deck", label: "Pitch Deck", icon: "🎯", description: "Auto-generated investor pitch deck" },
];

const INPUT_FIELDS = [
    { key: "startup_name", label: "Startup Name", placeholder: "Your startup name" },
    { key: "startup_description", label: "Description", placeholder: "What does your startup do?", multiline: true },
    { key: "target_audience", label: "Target Audience", placeholder: "Who are your customers?" },
    { key: "current_stage", label: "Stage", placeholder: "idea, mvp, growth" },
    { key: "business_model", label: "Business Model", placeholder: "How do you make money?" },
    { key: "geographic_focus", label: "Geographic Focus", placeholder: "Target regions" },
    { key: "research_goal", label: "Research Goal", placeholder: "What do you want to learn?", multiline: true },
    { key: "time_range", label: "Time Range", placeholder: "e.g., Last 5 years, 2020-2024" },
    { key: "inspiration_sources", label: "Competitors", placeholder: "Stripe, Square, etc." },
];

export default function ProjectPage() {
    const { token, isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();
    const params = useParams();
    const projectId = params.id as string;

    const [project, setProject] = useState<Project | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [reports, setReports] = useState<Report[]>([]);
    const [messages, setMessages] = useState<Message[]>([]);
    const [newMessage, setNewMessage] = useState("");
    const [isTyping, setIsTyping] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [editingInputs, setEditingInputs] = useState(false);
    const [inputValues, setInputValues] = useState<Partial<ProjectInputs>>({});

    // Collapsible states
    const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
    const [chatCollapsed, setChatCollapsed] = useState(false);

    // Mobile responsive states
    const [isMobile, setIsMobile] = useState(false);
    const [mobileFullscreenPanel, setMobileFullscreenPanel] = useState<'sidebar' | 'chat' | null>(null);

    // Auto-fill animation states
    const [aiFilledFields, setAiFilledFields] = useState<Record<string, boolean>>({});
    // Track which fields were generated by AI (persists for star icon)
    const [aiGeneratedFields, setAiGeneratedFields] = useState<Record<string, boolean>>({});
    // Ref to track latest aiGeneratedFields for async operations
    const aiGeneratedFieldsRef = useRef<Record<string, boolean>>({});

    // Chat modes state
    const [availableModes, setAvailableModes] = useState<ChatMode[]>([]);
    const [activeModes, setActiveModes] = useState<string[]>([]);

    // Crunchbase report fields state
    const [crunchbaseKeywords, setCrunchbaseKeywords] = useState<string[]>([]);
    const [crunchbaseTargetDescription, setCrunchbaseTargetDescription] = useState("");
    const [crunchbaseGenerating, setCrunchbaseGenerating] = useState(false);
    const [crunchbaseFieldErrors, setCrunchbaseFieldErrors] = useState<{ keywords: boolean; targetDescription: boolean }>({ keywords: false, targetDescription: false });
    const [crunchbaseValidationMessage, setCrunchbaseValidationMessage] = useState("");

    // Input field validation state
    const [inputFieldErrors, setInputFieldErrors] = useState<Record<string, boolean>>({});
    const [inputValidationMessage, setInputValidationMessage] = useState("");

    // Progress steps collapsed state (per report)
    const [collapsedSteps, setCollapsedSteps] = useState<Record<string, boolean>>({});

    const wsRef = useRef<WebSocket | null>(null);
    const wsReconnectAttempts = useRef<number>(0);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    // Mobile viewport detection
    useEffect(() => {
        const checkMobile = () => {
            const mobile = window.innerWidth <= 768;
            setIsMobile(mobile);
            // On mobile, default both panels to collapsed
            if (mobile) {
                setSidebarCollapsed(true);
                setChatCollapsed(true);
                setMobileFullscreenPanel(null);
            }
        };

        // Initial check
        checkMobile();

        // Listen for resize events
        window.addEventListener('resize', checkMobile);
        return () => window.removeEventListener('resize', checkMobile);
    }, []);


    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push("/login");
        }
    }, [authLoading, isAuthenticated, router]);

    // Keep ref in sync with state for async operations
    useEffect(() => {
        aiGeneratedFieldsRef.current = aiGeneratedFields;
    }, [aiGeneratedFields]);

    useEffect(() => {
        if (token && projectId) {
            fetchProjectData();
            fetchProjects();
            fetchAvailableModes();
            connectWebSocket();
        }
        return () => { wsRef.current?.close(); };
    }, [token, projectId]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const fetchProjectData = async () => {
        try {
            const projRes = await fetch(`${API_URL}/api/projects/${projectId}/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            if (projRes.ok) {
                const projData = await projRes.json();
                setProject(projData);
                setInputValues(projData.inputs || {});

                // Load AI-generated fields from database for persistence
                // These are set by the backend when AI fills fields
                const aiFields = projData.inputs?.ai_generated_fields || {};
                console.log('📥 Loaded ai_generated_fields from DB:', aiFields);
                aiGeneratedFieldsRef.current = aiFields;
                setAiGeneratedFields(aiFields);

                // Load Crunchbase fields
                setCrunchbaseKeywords(projData.inputs?.extracted_keywords || []);
                setCrunchbaseTargetDescription(projData.inputs?.target_description || "");
            }

            try {
                const reportsRes = await fetch(`${API_URL}/api/reports/project/${projectId}/`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (reportsRes.ok) {
                    const reportsData = await reportsRes.json();
                    setReports(Array.isArray(reportsData) ? reportsData : []);
                }
            } catch (reportsError) {
                console.log("Reports not available:", reportsError);
                setReports([]);
            }
        } catch (error) {
            console.error("Failed to fetch project:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchProjects = async () => {
        try {
            const res = await fetch(`${API_URL}/api/projects/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            const data = await res.json();
            setProjects(data.results || data || []);
        } catch (error) {
            console.error("Failed to fetch projects:", error);
        }
    };

    const fetchAvailableModes = async () => {
        console.log('🎛️ Fetching modes from:', `${API_URL}/api/chat/modes/`);
        try {
            const res = await fetch(`${API_URL}/api/chat/modes/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            console.log('🎛️ Modes response status:', res.status);
            if (res.ok) {
                const modesData = await res.json();
                console.log('🎛️ Available modes:', modesData);
                setAvailableModes(modesData);
            } else {
                const errorText = await res.text();
                console.error('🎛️ Modes fetch failed:', res.status, errorText);
            }
        } catch (error) {
            console.error("🎛️ Failed to fetch modes:", error);
        }
    };

    const toggleMode = (modeId: string) => {
        setActiveModes((prev) => {
            if (prev.includes(modeId)) {
                return prev.filter((id) => id !== modeId);
            } else {
                return [...prev, modeId];
            }
        });
    };

    const connectWebSocket = () => {
        // Close existing connection if any
        if (wsRef.current && wsRef.current.readyState !== WebSocket.CLOSED) {
            wsRef.current.close();
        }

        const ws = new WebSocket(`${WS_URL}/ws/projects/${projectId}/chat/?token=${token}`);
        const maxReconnectAttempts = 10;
        const baseDelay = 1000; // 1 second

        ws.onopen = () => {
            console.log('🔌 WebSocket connected');
            wsReconnectAttempts.current = 0; // Reset on successful connection
            // Refresh data when reconnected to ensure UI is up to date
            fetchProjectData();
        };

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            if (data.type === "history") {
                setMessages(data.messages);
            } else if (data.type === "message") {
                setMessages((prev) => [...prev, data.message]);
                setIsTyping(false);
            } else if (data.type === "status") {
                setIsTyping(data.status === "thinking");
            } else if (data.type === "report_progress") {
                updateReportProgress(data);
            } else if (data.type === "auto_fill") {
                // Handle AI auto-fill event
                handleAutoFill(data.field, data.value, data.confidence);
            }
        };

        ws.onerror = (error) => {
            console.error('❌ WebSocket error:', error);
        };

        ws.onclose = (event) => {
            console.log('🔌 WebSocket closed:', event.code, event.reason);

            // Don't reconnect if closed intentionally (code 1000) or auth issues
            if (event.code === 1000 || event.code === 4001) {
                return;
            }

            // Auto-reconnect with exponential backoff
            if (wsReconnectAttempts.current < maxReconnectAttempts) {
                wsReconnectAttempts.current++;
                const delay = Math.min(baseDelay * Math.pow(2, wsReconnectAttempts.current - 1), 30000); // Max 30s
                console.log(`⏳ Reconnecting in ${delay}ms (attempt ${wsReconnectAttempts.current}/${maxReconnectAttempts})...`);
                setTimeout(() => {
                    if (token && projectId) {
                        connectWebSocket();
                    }
                }, delay);
            } else {
                console.error('❌ Max reconnection attempts reached');
            }
        };

        wsRef.current = ws;
    };

    // Handle page visibility changes - refresh data when tab becomes visible again
    useEffect(() => {
        const handleVisibilityChange = () => {
            if (document.visibilityState === 'visible' && token && projectId) {
                console.log('👁️ Page became visible, refreshing data...');
                fetchProjectData();
                // Reconnect WebSocket if it was closed
                if (!wsRef.current || wsRef.current.readyState === WebSocket.CLOSED) {
                    wsReconnectAttempts.current = 0;
                    connectWebSocket();
                }
            }
        };

        document.addEventListener('visibilitychange', handleVisibilityChange);
        return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
    }, [token, projectId]);

    // Handle auto-fill from AI
    const handleAutoFill = (field: string, value: string, confidence: number) => {
        console.log(`🤖 Auto-filling ${field} with: ${value} (confidence: ${confidence})`);

        // Update the input value in local state (functional update for concurrency)
        setInputValues((prev) => ({ ...prev, [field]: value }));

        // Also update the project state if it exists
        setProject((prev) => {
            if (!prev) return prev;
            return {
                ...prev,
                inputs: {
                    ...prev.inputs,
                    [field]: value
                }
            };
        });

        // Mark field as AI-generated in local state (for display)
        // Use functional update to handle rapid concurrent calls correctly
        setAiGeneratedFields((prev) => {
            const updated = { ...prev, [field]: true };
            // Also update ref for other code that reads it
            aiGeneratedFieldsRef.current = updated;
            return updated;
        });

        // Trigger highlight animation (functional update for concurrency)
        setAiFilledFields((prev) => ({ ...prev, [field]: true }));

        // Remove highlight animation after 3 seconds (but keep AI-generated marker)
        setTimeout(() => {
            setAiFilledFields((prev) => ({ ...prev, [field]: false }));
        }, 3000);

        // Note: Don't set editingInputs - AI auto-saves, no manual save needed
    };

    const updateReportProgress = (data: {
        report_type: string;
        progress: number;
        current_step: string;
        status?: string;
        steps?: ProgressStep[];
        time_estimate?: TimeEstimate;
    }) => {
        // Debug: Log received WebSocket data
        console.log('📡 Report progress update received:', {
            report_type: data.report_type,
            progress: data.progress,
            steps_count: data.steps?.length,
            first_step_details: data.steps?.[0]?.details?.length,
            steps: data.steps
        });

        setReports((prev) =>
            prev.map((r) =>
                r.report_type === data.report_type
                    ? {
                        ...r,
                        progress: data.progress,
                        current_step: data.current_step,
                        status: data.status || (data.progress === 100 ? "completed" : "running"),
                        progress_steps: data.steps || r.progress_steps,
                        time_estimate: data.time_estimate || r.time_estimate
                    }
                    : r
            )
        );
        if (data.progress === 100) {
            setTimeout(fetchProjectData, 1000);
        }
    };

    const sendMessage = () => {
        if (!newMessage.trim() || !wsRef.current) return;
        wsRef.current.send(JSON.stringify({
            type: "message",
            message: newMessage,
            active_modes: activeModes  // Include active modes in message
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

    const startReport = async (reportType: string) => {
        const report = reports.find((r) => r.report_type === reportType);
        if (!report) return;

        // Validate required project inputs before starting any report
        // All fields required except Competitors (inspiration_sources)
        const requiredFields = [
            "startup_name",
            "startup_description",
            "target_audience",
            "current_stage",
            "business_model",
            "geographic_focus",
            "research_goal"
        ];
        const currentInputs = project?.inputs || {};
        const errors: Record<string, boolean> = {};
        let hasErrors = false;

        console.log("Validating inputs:", currentInputs);

        for (const field of requiredFields) {
            const value = (currentInputs as Record<string, unknown>)[field];
            console.log(`Field ${field}:`, value, "empty:", !value || (typeof value === "string" && value.trim() === ""));
            if (!value || (typeof value === "string" && value.trim() === "")) {
                errors[field] = true;
                hasErrors = true;
            }
        }

        console.log("Errors:", errors, "hasErrors:", hasErrors);

        if (hasErrors) {
            // Set errors to trigger red highlighting
            console.log("Setting inputFieldErrors:", errors);
            setInputFieldErrors(errors);
            setInputValidationMessage("Please fill in the required fields (Startup Name and Description) before starting the report");

            // Scroll to the project inputs section smoothly
            const inputsSection = document.querySelector('[data-section="project-inputs"]');
            if (inputsSection) {
                inputsSection.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }

            // Clear errors after 5 seconds
            setTimeout(() => {
                setInputFieldErrors({});
                setInputValidationMessage("");
            }, 5000);
            return;
        }

        try {
            const res = await fetch(`${API_URL}/api/reports/project/${projectId}/${report.id}/start/`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
            });

            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                console.error("Failed to start report:", res.status, errorData);
                setInputValidationMessage(errorData.error || "Failed to start report. Please try again.");
                setTimeout(() => setInputValidationMessage(""), 5000);
                return;
            }

            setReports((prev) =>
                prev.map((r) =>
                    r.report_type === reportType
                        ? { ...r, status: "running", progress: 0, current_step: "Starting..." }
                        : r
                )
            );
        } catch (error) {
            console.error("Failed to start report:", error);
            setInputValidationMessage("Network error. Please check your connection and try again.");
            setTimeout(() => setInputValidationMessage(""), 5000);
        }
    };

    // Generate Crunchbase keywords and target description using AI
    const generateCrunchbaseParams = async () => {
        setCrunchbaseGenerating(true);
        setCrunchbaseValidationMessage("");
        try {
            const res = await fetch(`${API_URL}/api/projects/${projectId}/inputs/generate-crunchbase-params/`, {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
            });

            if (res.ok) {
                const data = await res.json();
                setCrunchbaseKeywords(data.keywords || []);
                setCrunchbaseTargetDescription(data.target_description || "");
                // Mark as AI generated
                setAiGeneratedFields(prev => ({
                    ...prev,
                    extracted_keywords: true,
                    target_description: true
                }));
            } else {
                const errorData = await res.json();
                console.error("Failed to generate Crunchbase params:", errorData.error);
                setCrunchbaseValidationMessage(errorData.error || "Failed to generate parameters");
            }
        } catch (error) {
            console.error("Failed to generate Crunchbase params:", error);
            setCrunchbaseValidationMessage("Failed to generate parameters. Please try again.");
        } finally {
            setCrunchbaseGenerating(false);
        }
    };

    // Save Crunchbase fields to backend
    const saveCrunchbaseFields = async () => {
        try {
            await fetch(`${API_URL}/api/projects/${projectId}/inputs/`, {
                method: "PATCH",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    extracted_keywords: crunchbaseKeywords,
                    target_description: crunchbaseTargetDescription
                })
            });
        } catch (error) {
            console.error("Failed to save Crunchbase fields:", error);
        }
    };

    // Remove a keyword from the list
    const removeKeyword = (index: number) => {
        const newKeywords = crunchbaseKeywords.filter((_, i) => i !== index);
        setCrunchbaseKeywords(newKeywords);
        // Clear AI marker when user edits
        setAiGeneratedFields(prev => ({ ...prev, extracted_keywords: false }));
    };

    // Add a new keyword
    const addKeyword = (keyword: string) => {
        if (keyword.trim() && !crunchbaseKeywords.includes(keyword.trim())) {
            setCrunchbaseKeywords([...crunchbaseKeywords, keyword.trim()]);
            // Clear AI marker when user edits
            setAiGeneratedFields(prev => ({ ...prev, extracted_keywords: false }));
        }
    };

    const saveInputs = async () => {
        try {
            // Only send the 9 input fields - no metadata fields
            const inputFieldKeys = [
                'startup_name', 'startup_description', 'target_audience',
                'current_stage', 'business_model', 'geographic_focus',
                'research_goal', 'time_range', 'inspiration_sources'
            ];

            const inputFieldsOnly: Record<string, string> = {};
            for (const key of inputFieldKeys) {
                const value = (inputValues as any)[key];
                if (value !== undefined) {
                    inputFieldsOnly[key] = value;
                }
            }

            // Build final data with current AI markers from ref
            const dataToSave = {
                ...inputFieldsOnly,
                ai_generated_fields: aiGeneratedFieldsRef.current
            };

            console.log('💾 Saving inputs:', inputFieldsOnly);
            console.log('💾 With ai_generated_fields:', aiGeneratedFieldsRef.current);

            const response = await fetch(`${API_URL}/api/projects/${projectId}/inputs/`, {
                method: "PATCH",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(dataToSave),
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Save failed:', errorText);
                alert('Save failed. Please check the console for details.');
            } else {
                console.log('✅ Save successful');
            }

            setEditingInputs(false);
            fetchProjectData();
        } catch (error) {
            console.error("Failed to save inputs:", error);
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
            <TopBar showBackToDashboard />
            <div className="page-with-topbar">
                <div style={{ display: "flex", height: "calc(100vh - 48px)", overflow: "hidden" }}>

                    {/* LEFT SIDEBAR - Projects List (Collapsible) */}
                    <aside style={{
                        width: isMobile && mobileFullscreenPanel === 'sidebar'
                            ? "100vw"
                            : sidebarCollapsed ? "0px" : "260px",
                        minWidth: isMobile && mobileFullscreenPanel === 'sidebar'
                            ? "100vw"
                            : sidebarCollapsed ? "0px" : "260px",
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
                        <div style={{ padding: "16px", borderBottom: "1px solid var(--color-border)" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                                <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Projects</span>
                            </div>
                            <Link
                                href="/projects/new"
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    gap: "6px",
                                    padding: "10px 12px",
                                    background: "var(--gradient-primary)",
                                    color: "#fff",
                                    borderRadius: "var(--radius-sm)",
                                    fontSize: "13px",
                                    fontWeight: 600,
                                    textDecoration: "none"
                                }}
                            >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M12 5v14M5 12h14" />
                                </svg>
                                New Project
                            </Link>
                        </div>
                        <div style={{ flex: 1, overflow: "auto", padding: "8px" }}>
                            {projects.map((proj) => (
                                <button
                                    key={proj.id}
                                    onClick={() => router.push(`/projects/${proj.id}`)}
                                    style={{
                                        width: "100%",
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "10px",
                                        padding: "10px 12px",
                                        marginBottom: "4px",
                                        border: "none",
                                        borderRadius: "var(--radius-sm)",
                                        background: proj.id === projectId ? "rgba(24, 54, 97, 0.15)" : "transparent",
                                        color: proj.id === projectId ? "var(--color-secondary)" : "var(--color-text)",
                                        fontSize: "13px",
                                        cursor: "pointer",
                                        textAlign: "left",
                                        transition: "all 0.15s ease"
                                    }}
                                >
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                                    </svg>
                                    <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{proj.name}</span>
                                </button>
                            ))}
                        </div>
                    </aside>

                    {/* Sidebar Toggle Button - Hide on mobile when any panel is fullscreen */}
                    {!(isMobile && mobileFullscreenPanel) && (
                        <button
                            onClick={() => {
                                if (isMobile) {
                                    // On mobile, toggle fullscreen mode
                                    if (sidebarCollapsed) {
                                        setMobileFullscreenPanel('sidebar');
                                        setSidebarCollapsed(false);
                                    } else {
                                        setMobileFullscreenPanel(null);
                                        setSidebarCollapsed(true);
                                    }
                                } else {
                                    // On desktop, normal toggle
                                    setSidebarCollapsed(!sidebarCollapsed);
                                }
                            }}
                            style={{
                                position: "absolute",
                                left: sidebarCollapsed ? "0" : "260px",
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

                    {/* MAIN CONTENT AREA - Hide on mobile when a panel is fullscreen */}
                    <main style={{
                        flex: 1,
                        overflow: "auto",
                        padding: "24px",
                        background: "var(--color-background)",
                        scrollbarWidth: "none",
                        msOverflowStyle: "none",
                        display: isMobile && mobileFullscreenPanel ? "none" : "block"
                    }} className="hide-scrollbar">
                        {/* Project Header */}
                        <div style={{ marginBottom: "24px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                                <div style={{
                                    width: "40px",
                                    height: "40px",
                                    background: "var(--gradient-primary)",
                                    borderRadius: "10px",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    fontWeight: 700,
                                    fontSize: "18px",
                                    color: "#fff"
                                }}>
                                    {project?.name?.charAt(0).toUpperCase() || "P"}
                                </div>
                                <div>
                                    <h1 style={{ margin: 0, fontSize: "20px", fontWeight: 700, color: "var(--color-heading)" }}>{project?.name}</h1>
                                    <p style={{ margin: "2px 0 0", fontSize: "13px", color: "var(--color-text-muted)" }}>{project?.description || "Market research project"}</p>
                                </div>
                            </div>
                        </div>

                        {/* INPUTS CARD */}
                        <div
                            data-section="project-inputs"
                            style={{
                                background: "var(--color-surface-elevated)",
                                borderRadius: "var(--radius-lg)",
                                padding: "24px",
                                marginBottom: "24px",
                                border: "1px solid var(--color-border)"
                            }}>
                            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
                                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                                    <span style={{ fontSize: "20px" }}>📝</span>
                                    <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>Project Inputs</h2>
                                </div>
                                {!editingInputs ? (
                                    <button
                                        onClick={() => setEditingInputs(true)}
                                        style={{
                                            padding: "8px 16px",
                                            background: "var(--color-surface-muted)",
                                            border: "1px solid var(--color-border)",
                                            borderRadius: "var(--radius-sm)",
                                            color: "var(--color-text)",
                                            cursor: "pointer",
                                            fontSize: "13px",
                                            fontWeight: 500
                                        }}
                                    >
                                        ✏️ Edit Inputs
                                    </button>
                                ) : (
                                    <div style={{ display: "flex", gap: "8px" }}>
                                        <button onClick={() => setEditingInputs(false)} style={{ padding: "8px 16px", background: "transparent", border: "1px solid var(--color-border)", borderRadius: "var(--radius-sm)", color: "var(--color-text-muted)", cursor: "pointer", fontSize: "13px" }}>Cancel</button>
                                        <button onClick={saveInputs} style={{ padding: "8px 16px", background: "var(--gradient-primary)", border: "none", borderRadius: "var(--radius-sm)", color: "#fff", cursor: "pointer", fontSize: "13px", fontWeight: 600 }}>Save Changes</button>
                                    </div>
                                )}
                            </div>

                            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "16px" }}>
                                {INPUT_FIELDS.map((field) => {
                                    const isAiFilled = aiFilledFields[field.key];
                                    const isAiGenerated = aiGeneratedFields[field.key];
                                    const hasError = inputFieldErrors[field.key];
                                    // All fields required except Competitors (inspiration_sources)
                                    const isRequired = field.key !== "inspiration_sources";
                                    // Cast to string since we know input fields are strings (not ai_generated_fields)
                                    const fieldValue = (inputValues[field.key as keyof ProjectInputs] as string) || "";

                                    // Handler for when user manually edits a field
                                    const handleUserEdit = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
                                        const newValue = e.target.value;
                                        setInputValues((prev) => ({ ...prev, [field.key]: newValue }));

                                        // Clear error for this field when user starts typing
                                        if (hasError) {
                                            setInputFieldErrors((prev) => ({ ...prev, [field.key]: false }));
                                        }

                                        // If user edits an AI-generated field, remove the AI marker
                                        if (isAiGenerated) {
                                            const updatedFields = { ...aiGeneratedFieldsRef.current, [field.key]: false };
                                            aiGeneratedFieldsRef.current = updatedFields;
                                            setAiGeneratedFields(updatedFields);
                                        }
                                    };

                                    return (
                                        <div key={field.key} style={{ position: "relative" }}>
                                            <label style={{
                                                display: "block",
                                                fontSize: "11px",
                                                fontWeight: 600,
                                                marginBottom: "6px",
                                                color: hasError ? "var(--color-error)" : isAiFilled ? "var(--color-primary)" : "var(--color-text-muted)",
                                                textTransform: "uppercase",
                                                letterSpacing: "0.03em",
                                                transition: "color 0.5s ease"
                                            }}>
                                                {field.label}{isRequired && " *"}
                                            </label>

                                            {/* Display mode - elegant read-only view */}
                                            <div
                                                className={`${isAiFilled ? "ai-filled-field" : ""} ${hasError ? "error-shake" : ""}`}
                                                style={{
                                                    position: "relative",
                                                    padding: "10px 12px",
                                                    paddingRight: isAiGenerated ? "32px" : "12px",
                                                    background: hasError ? "rgba(239, 68, 68, 0.1)" : isAiFilled ? "var(--color-primary-muted)" : "var(--color-surface-muted)",
                                                    borderRadius: "var(--radius-sm)",
                                                    fontSize: "13px",
                                                    color: fieldValue ? "var(--color-text)" : "var(--color-text-muted)",
                                                    minHeight: field.multiline ? "50px" : "auto",
                                                    border: hasError ? "2px solid var(--color-error)" : isAiFilled ? "2px solid var(--color-primary)" : "1px solid var(--color-border)",
                                                    transition: "all 0.5s cubic-bezier(0.4, 0, 0.2, 1)",
                                                    transform: isAiFilled ? "scale(1.02)" : "scale(1)",
                                                    boxShadow: hasError ? "0 0 10px rgba(239, 68, 68, 0.3)" : isAiFilled ? "0 4px 20px rgba(24, 54, 97, 0.25)" : "none",
                                                    cursor: editingInputs ? "text" : "default"
                                                }}
                                                onClick={() => !editingInputs && setEditingInputs(true)}
                                            >
                                                {editingInputs ? (
                                                    field.multiline ? (
                                                        <textarea
                                                            value={fieldValue}
                                                            onChange={handleUserEdit}
                                                            placeholder={field.placeholder}
                                                            rows={2}
                                                            style={{
                                                                width: "100%",
                                                                resize: "none",
                                                                background: "transparent",
                                                                border: "none",
                                                                outline: "none",
                                                                color: "inherit",
                                                                fontSize: "inherit",
                                                                fontFamily: "inherit",
                                                                padding: 0,
                                                                margin: 0
                                                            }}
                                                        />
                                                    ) : (
                                                        <input
                                                            type="text"
                                                            value={fieldValue}
                                                            onChange={handleUserEdit}
                                                            placeholder={field.placeholder}
                                                            style={{
                                                                width: "100%",
                                                                background: "transparent",
                                                                border: "none",
                                                                outline: "none",
                                                                color: "inherit",
                                                                fontSize: "inherit",
                                                                fontFamily: "inherit",
                                                                padding: 0,
                                                                margin: 0
                                                            }}
                                                        />
                                                    )
                                                ) : (
                                                    <span>{fieldValue || field.placeholder}</span>
                                                )}

                                                {/* AI Star indicator at end of field - only shown for AI-generated content */}
                                                {isAiGenerated && fieldValue && (
                                                    <span style={{
                                                        position: "absolute",
                                                        right: "10px",
                                                        top: field.multiline ? "10px" : "50%",
                                                        transform: field.multiline ? "none" : "translateY(-50%)",
                                                        fontSize: "14px",
                                                        opacity: isAiFilled ? 1 : 0.6,
                                                        transition: "opacity 0.3s ease",
                                                        animation: isAiFilled ? "star-sparkle 1s ease-in-out infinite" : "none",
                                                        filter: "grayscale(1) brightness(0.3)"
                                                    }} title="AI Generated - will disappear if you edit this field">
                                                        ✨
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* REPORTS SECTION */}
                        <div style={{ marginBottom: "24px" }}>
                            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "16px" }}>
                                <span style={{ fontSize: "20px" }}>📊</span>
                                <h2 style={{ margin: 0, fontSize: "16px", fontWeight: 600 }}>Research Reports</h2>
                            </div>

                            {/* Validation message */}
                            {inputValidationMessage && (
                                <div style={{
                                    padding: "12px 16px",
                                    background: "rgba(239, 68, 68, 0.1)",
                                    borderRadius: "var(--radius-sm)",
                                    border: "1px solid var(--color-error)",
                                    color: "var(--color-error)",
                                    fontSize: "13px",
                                    marginBottom: "16px",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "10px"
                                }}>
                                    <span style={{ fontSize: "16px" }}>⚠️</span>
                                    {inputValidationMessage}
                                </div>
                            )}

                            <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
                                {REPORT_TYPES.map((rt) => {
                                    const report = reports.find((r) => r.report_type === rt.type);
                                    const status = report?.status || "not_started";

                                    return (
                                        <div
                                            key={rt.type}
                                            style={{
                                                background: "var(--color-surface-elevated)",
                                                borderRadius: "var(--radius-md)",
                                                padding: "20px",
                                                border: "1px solid var(--color-border)",
                                                transition: "box-shadow 0.2s ease"
                                            }}
                                        >
                                            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
                                                <div style={{
                                                    width: "48px",
                                                    height: "48px",
                                                    borderRadius: "12px",
                                                    background: "var(--color-surface-muted)",
                                                    display: "flex",
                                                    alignItems: "center",
                                                    justifyContent: "center",
                                                    fontSize: "24px",
                                                    marginBottom: "12px"
                                                }}>
                                                    {rt.icon}
                                                </div>
                                                <div style={{ width: "100%" }}>
                                                    <h3 style={{ margin: "0 0 4px", fontSize: "15px", fontWeight: 600 }}>{rt.label}</h3>
                                                    <p style={{ margin: 0, fontSize: "12px", color: "var(--color-text-muted)" }}>{rt.description}</p>
                                                    <div style={{ marginTop: "12px" }}>
                                                        {status === "running" ? (
                                                            <>
                                                                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "6px" }}>
                                                                    <span style={{ fontSize: "12px", color: "var(--color-info)" }}>Running...</span>
                                                                    <span style={{ fontSize: "12px", color: "var(--color-info)" }}>{report?.progress}%</span>
                                                                </div>
                                                                <div className="progress-bar">
                                                                    <div className="progress-bar-fill" style={{ width: `${report?.progress || 0}%` }} />
                                                                </div>

                                                                {/* Progress Steps Timeline */}
                                                                {report?.progress_steps && report.progress_steps.length > 0 && (
                                                                    <div style={{ marginTop: "12px", paddingTop: "12px", borderTop: "1px solid var(--color-border)" }}>
                                                                        {/* Collapse Toggle Header */}
                                                                        <div
                                                                            onClick={() => setCollapsedSteps(prev => ({ ...prev, [rt.type]: !prev[rt.type] }))}
                                                                            style={{
                                                                                display: "flex",
                                                                                alignItems: "center",
                                                                                justifyContent: "space-between",
                                                                                cursor: "pointer",
                                                                                marginBottom: collapsedSteps[rt.type] ? 0 : "8px",
                                                                                padding: "4px 0"
                                                                            }}
                                                                        >
                                                                            <span style={{ fontSize: "11px", fontWeight: 600, color: "var(--color-text-muted)" }}>
                                                                                Progress Details ({report.progress_steps.filter(s => s.status === 'completed').length}/{report.progress_steps.length})
                                                                            </span>
                                                                            <span style={{
                                                                                fontSize: "12px",
                                                                                color: "var(--color-text-muted)",
                                                                                transition: "transform 0.2s ease",
                                                                                transform: collapsedSteps[rt.type] ? "rotate(-90deg)" : "rotate(0deg)"
                                                                            }}>▼</span>
                                                                        </div>

                                                                        {/* Steps List - Collapsible */}
                                                                        {!collapsedSteps[rt.type] && report.progress_steps.map((step, idx) => {
                                                                            // Find matching estimate for pending steps
                                                                            const estimateStep = report.time_estimate?.steps.find(s => s.step_key === step.step_key);
                                                                            const showEstimate = step.status === 'pending' && estimateStep;

                                                                            return (
                                                                                <React.Fragment key={step.step_key}>
                                                                                    <div style={{
                                                                                        display: "flex",
                                                                                        alignItems: "center",
                                                                                        gap: "8px",
                                                                                        padding: "4px 0",
                                                                                        opacity: step.status === 'pending' ? 0.6 : 1
                                                                                    }}>
                                                                                        <span style={{
                                                                                            width: "18px",
                                                                                            height: "18px",
                                                                                            display: "flex",
                                                                                            alignItems: "center",
                                                                                            justifyContent: "center",
                                                                                            fontSize: "11px",
                                                                                            borderRadius: "50%",
                                                                                            background: step.status === 'completed' ? 'var(--color-success)'
                                                                                                : step.status === 'running' ? 'var(--color-info)'
                                                                                                    : step.status === 'failed' ? 'var(--color-error)'
                                                                                                        : 'var(--color-surface-muted)',
                                                                                            color: step.status === 'pending' ? 'var(--color-text-muted)' : '#fff'
                                                                                        }}>
                                                                                            {step.status === 'completed' ? '✓'
                                                                                                : step.status === 'running' ? '⟳'
                                                                                                    : step.status === 'failed' ? '✕'
                                                                                                        : step.status === 'skipped' ? '–'
                                                                                                            : idx + 1}
                                                                                        </span>
                                                                                        <span style={{
                                                                                            flex: 1,
                                                                                            fontSize: "11px",
                                                                                            color: step.status === 'running' ? 'var(--color-info)' : 'var(--color-text)'
                                                                                        }}>
                                                                                            {step.step_name}
                                                                                        </span>
                                                                                        {step.duration_seconds ? (
                                                                                            <span style={{ fontSize: "10px", color: "var(--color-text-muted)" }}>
                                                                                                {step.duration_seconds.toFixed(1)}s
                                                                                            </span>
                                                                                        ) : showEstimate ? (
                                                                                            <span style={{ fontSize: "10px", color: "var(--color-text-muted)", fontStyle: "italic" }}>
                                                                                                ~{Math.round(estimateStep.avg_duration)}s
                                                                                            </span>
                                                                                        ) : step.status === 'running' && (
                                                                                            <span style={{ fontSize: "10px", color: "var(--color-info)" }}>◦◦◦</span>
                                                                                        )}
                                                                                    </div>

                                                                                    {/* Step Details - show keywords, search results, etc */}
                                                                                    {
                                                                                        step.details && step.details.length > 0 && (step.status === 'running' || step.status === 'completed') && (
                                                                                            <div style={{
                                                                                                marginLeft: "32px",
                                                                                                marginTop: "4px",
                                                                                                marginBottom: "8px",
                                                                                                padding: "8px 12px",
                                                                                                background: "var(--color-surface-muted)",
                                                                                                borderRadius: "var(--radius-sm)",
                                                                                                borderLeft: "2px solid var(--color-info)"
                                                                                            }}>
                                                                                                {step.details.map((detail, detailIdx) => (
                                                                                                    <div key={detailIdx} style={{
                                                                                                        fontSize: "11px",
                                                                                                        color: "var(--color-text-muted)",
                                                                                                        marginBottom: detailIdx < step.details.length - 1 ? "4px" : 0
                                                                                                    }}>
                                                                                                        {detail.type === 'keywords' && detail.data?.keywords ? (
                                                                                                            <div>
                                                                                                                <span style={{ color: "var(--color-info)" }}>🔑</span>
                                                                                                                <span style={{ marginLeft: "6px", fontWeight: 500 }}>Keywords:</span>
                                                                                                                <span style={{ marginLeft: "4px" }}>
                                                                                                                    {detail.data.keywords.slice(0, 8).join(', ')}
                                                                                                                    {detail.data.keywords.length > 8 && ` +${detail.data.keywords.length - 8} more`}
                                                                                                                </span>
                                                                                                            </div>
                                                                                                        ) : detail.type === 'keyword' ? (
                                                                                                            /* Individual keyword in step 1 */
                                                                                                            <div>
                                                                                                                <span style={{ color: "var(--color-info)" }}>🔑</span>
                                                                                                                <span style={{ marginLeft: "6px" }}>{detail.message}</span>
                                                                                                            </div>
                                                                                                        ) : detail.type === 'search_result' && detail.data?.top_companies ? (
                                                                                                            /* Search result with top 5 companies and CB rank */
                                                                                                            <div>
                                                                                                                <span style={{ color: "var(--color-success)" }}>🔍</span>
                                                                                                                <span style={{ marginLeft: "6px", fontWeight: 500 }}>{detail.message}</span>
                                                                                                                <div style={{ marginLeft: "24px", marginTop: "4px", fontSize: "10px" }}>
                                                                                                                    {detail.data?.top_companies?.slice(0, 5).map((comp: { name: string, cb_rank: number }, idx: number) => (
                                                                                                                        <span key={idx} style={{ marginRight: "8px", color: "var(--color-text-muted)" }}>
                                                                                                                            {comp.name} <span style={{ opacity: 0.7 }}>(#{comp.cb_rank})</span>
                                                                                                                            {idx < Math.min(detail.data?.top_companies?.length || 0, 5) - 1 && ", "}
                                                                                                                        </span>
                                                                                                                    ))}
                                                                                                                </div>
                                                                                                            </div>
                                                                                                        ) : detail.type === 'search_result' ? (
                                                                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                                                                                                                <div>
                                                                                                                    <span style={{ color: "var(--color-success)" }}>🔍</span>
                                                                                                                    <span style={{ marginLeft: "6px" }}>{detail.message.split(' - Top:')[0]}</span>
                                                                                                                </div>
                                                                                                                {detail.data?.full_text && (
                                                                                                                    <div style={{ marginLeft: "24px", fontSize: "10px", color: "var(--color-text-secondary)" }}>
                                                                                                                        <span style={{ fontWeight: 600 }}>Top Tweet:</span>{" "}
                                                                                                                        <ExpandableText text={detail.data.full_text} maxLength={60} />
                                                                                                                    </div>
                                                                                                                )}
                                                                                                                {!detail.data?.full_text && detail.message.includes('Top:') && (
                                                                                                                    <div style={{ marginLeft: "24px", fontSize: "10px", color: "var(--color-text-secondary)" }}>
                                                                                                                        {detail.message.split(' - Top:')[1]}
                                                                                                                    </div>
                                                                                                                )}
                                                                                                            </div>
                                                                                                        ) : detail.type === 'company_rank' ? (
                                                                                                            /* Sorted company with numbered list, inline description that expands on click */
                                                                                                            (() => {
                                                                                                                const desc = detail.data?.description || '';
                                                                                                                const isLong = desc.length > 60;
                                                                                                                return (
                                                                                                                    <div style={{ marginBottom: "4px", fontSize: "11px" }}>
                                                                                                                        <span style={{ fontWeight: 600, color: "var(--color-text-muted)" }}>
                                                                                                                            {detail.data?.rank || detailIdx + 1}.
                                                                                                                        </span>
                                                                                                                        {" "}
                                                                                                                        <span style={{ fontWeight: 700 }}>
                                                                                                                            {detail.data?.name || 'Unknown'}
                                                                                                                        </span>
                                                                                                                        {" "}
                                                                                                                        <span style={{ fontSize: "10px", color: "var(--color-text-muted)" }}>
                                                                                                                            (CB Rank: {detail.data?.cb_rank || 'N/A'})
                                                                                                                        </span>
                                                                                                                        {" "}
                                                                                                                        <span style={{ fontSize: "10px", color: "var(--color-text-secondary)" }}>
                                                                                                                            — <ExpandableText text={desc} maxLength={60} />
                                                                                                                        </span>
                                                                                                                    </div>
                                                                                                                );
                                                                                                            })()
                                                                                                        ) : detail.type === 'company_found' || detail.type === 'company_processing' ? (
                                                                                                            <div>
                                                                                                                <span style={{ color: "var(--color-warning)" }}>⚡</span>
                                                                                                                <span style={{ marginLeft: "6px" }}>{detail.message}</span>
                                                                                                            </div>
                                                                                                        ) : detail.type === 'top_companies' && detail.data?.companies ? (
                                                                                                            <div>
                                                                                                                <span style={{ color: "var(--color-success)" }}>🏆</span>
                                                                                                                <span style={{ marginLeft: "6px", fontWeight: 500 }}>Top matches:</span>
                                                                                                                <span style={{ marginLeft: "4px" }}>
                                                                                                                    {detail.data.companies.slice(0, 5).join(', ')}
                                                                                                                    {detail.data.companies.length > 5 && ` +${detail.data.companies.length - 5} more`}
                                                                                                                </span>
                                                                                                            </div>
                                                                                                        ) : (
                                                                                                            <div>
                                                                                                                <span>{detail.message}</span>
                                                                                                            </div>
                                                                                                        )}
                                                                                                    </div>
                                                                                                ))}
                                                                                            </div>
                                                                                        )
                                                                                    }
                                                                                </React.Fragment>
                                                                            );
                                                                        })}

                                                                        {/* ETA Summary */}
                                                                        {report.time_estimate && report.time_estimate.remaining_seconds > 0 && (
                                                                            <div style={{
                                                                                marginTop: "12px",
                                                                                paddingTop: "10px",
                                                                                borderTop: "1px dashed var(--color-border)",
                                                                                display: "flex",
                                                                                alignItems: "center",
                                                                                justifyContent: "space-between"
                                                                            }}>
                                                                                <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>
                                                                                    Estimated remaining:
                                                                                </span>
                                                                                <span style={{
                                                                                    fontSize: "12px",
                                                                                    fontWeight: 600,
                                                                                    color: "var(--color-info)"
                                                                                }}>
                                                                                    {report.time_estimate.remaining_seconds >= 60
                                                                                        ? `${Math.floor(report.time_estimate.remaining_seconds / 60)}m ${Math.round(report.time_estimate.remaining_seconds % 60)}s`
                                                                                        : `${Math.round(report.time_estimate.remaining_seconds)}s`
                                                                                    }
                                                                                    <span style={{
                                                                                        marginLeft: "6px",
                                                                                        fontSize: "9px",
                                                                                        color: report.time_estimate.confidence === 'high' ? 'var(--color-success)'
                                                                                            : report.time_estimate.confidence === 'medium' ? 'var(--color-warning)'
                                                                                                : 'var(--color-text-muted)',
                                                                                        textTransform: "uppercase"
                                                                                    }}>
                                                                                        {report.time_estimate.confidence}
                                                                                    </span>
                                                                                </span>
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                )}
                                                            </>
                                                        ) : status === "completed" ? (
                                                            <>
                                                                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "8px" }}>
                                                                    <span style={{ fontSize: "12px", color: "var(--color-success)" }}>✓ Completed</span>
                                                                    {report?.html_content && (
                                                                        <button
                                                                            onClick={(e) => {
                                                                                e.stopPropagation();
                                                                                // Navigate to report page
                                                                                router.push(`/projects/${projectId}/reports/${report.id}`);
                                                                            }}
                                                                            style={{ padding: "4px 12px", background: "var(--color-primary)", border: "none", borderRadius: "var(--radius-sm)", color: "white", cursor: "pointer", fontSize: "11px", fontWeight: 500 }}
                                                                        >
                                                                            View Report
                                                                        </button>
                                                                    )}
                                                                </div>

                                                                {/* Show progress history after completion */}
                                                                {report?.progress_steps && report.progress_steps.length > 0 && (() => {
                                                                    // Calculate total time
                                                                    const totalTime = report.progress_steps.reduce((sum, step) => sum + (step.duration_seconds || 0), 0);
                                                                    const formatTime = (seconds: number) => {
                                                                        if (seconds >= 60) {
                                                                            const mins = Math.floor(seconds / 60);
                                                                            const secs = Math.round(seconds % 60);
                                                                            return `${mins}m ${secs}s`;
                                                                        }
                                                                        return `${seconds.toFixed(1)}s`;
                                                                    };

                                                                    return (
                                                                        <details style={{ marginTop: "8px" }}>
                                                                            <summary style={{
                                                                                fontSize: "11px",
                                                                                color: "var(--color-text-muted)",
                                                                                cursor: "pointer",
                                                                                padding: "4px 0"
                                                                            }}>
                                                                                View progress history
                                                                            </summary>
                                                                            <div style={{ marginTop: "8px", paddingTop: "8px", borderTop: "1px solid var(--color-border)" }}>
                                                                                {/* Total time header row */}
                                                                                <div style={{
                                                                                    display: "flex",
                                                                                    justifyContent: "flex-end",
                                                                                    marginBottom: "8px",
                                                                                    paddingBottom: "6px",
                                                                                    borderBottom: "1px solid var(--color-border)"
                                                                                }}>
                                                                                    <span style={{
                                                                                        fontSize: "10px",
                                                                                        fontWeight: 600,
                                                                                        color: "var(--color-text-secondary)"
                                                                                    }}>
                                                                                        Total: {formatTime(totalTime)}
                                                                                    </span>
                                                                                </div>
                                                                                {report.progress_steps.map((step, idx) => (
                                                                                    <details key={step.step_key} style={{
                                                                                        marginBottom: "4px",
                                                                                        opacity: step.status === 'skipped' ? 0.5 : 1
                                                                                    }}>
                                                                                        <summary style={{
                                                                                            display: "flex",
                                                                                            alignItems: "center",
                                                                                            gap: "8px",
                                                                                            padding: "4px 0",
                                                                                            cursor: step.details && step.details.length > 0 ? "pointer" : "default",
                                                                                            listStyle: "none"
                                                                                        }}>
                                                                                            <span style={{
                                                                                                width: "16px",
                                                                                                height: "16px",
                                                                                                display: "flex",
                                                                                                alignItems: "center",
                                                                                                justifyContent: "center",
                                                                                                fontSize: "10px",
                                                                                                borderRadius: "50%",
                                                                                                background: step.status === 'completed' ? 'var(--color-success)'
                                                                                                    : step.status === 'failed' ? 'var(--color-error)'
                                                                                                        : 'var(--color-surface-muted)',
                                                                                                color: '#fff',
                                                                                                flexShrink: 0
                                                                                            }}>
                                                                                                {step.status === 'completed' ? '✓'
                                                                                                    : step.status === 'failed' ? '✕'
                                                                                                        : step.status === 'skipped' ? '–'
                                                                                                            : idx + 1}
                                                                                            </span>
                                                                                            <span style={{ flex: 1, fontSize: "10px" }}>
                                                                                                {step.step_name}
                                                                                            </span>
                                                                                            {/* Down arrow for expandable steps - before duration */}
                                                                                            {step.details && step.details.length > 0 && (
                                                                                                <svg
                                                                                                    width="10"
                                                                                                    height="10"
                                                                                                    viewBox="0 0 24 24"
                                                                                                    fill="none"
                                                                                                    stroke="currentColor"
                                                                                                    strokeWidth="2"
                                                                                                    style={{ color: "var(--color-text-muted)", transition: "transform 0.2s", flexShrink: 0 }}
                                                                                                    className="expand-arrow"
                                                                                                >
                                                                                                    <path d="M6 9l6 6 6-6" />
                                                                                                </svg>
                                                                                            )}
                                                                                            {/* Duration - fixed width for column alignment */}
                                                                                            <span style={{ fontSize: "9px", color: "var(--color-text-muted)", minWidth: "45px", textAlign: "right" }}>
                                                                                                {step.duration_seconds ? `${step.duration_seconds.toFixed(1)}s` : ''}
                                                                                            </span>
                                                                                        </summary>
                                                                                        {/* Step details - shown when expanded */}
                                                                                        {step.details && step.details.length > 0 && (
                                                                                            <div style={{
                                                                                                marginLeft: "24px",
                                                                                                padding: "4px 8px",
                                                                                                background: "var(--color-surface-muted)",
                                                                                                borderRadius: "var(--radius-sm)",
                                                                                                marginTop: "4px",
                                                                                                marginBottom: "4px"
                                                                                            }}>
                                                                                                {step.details.map((detail: { type: string; message: string; timestamp: number; data?: Record<string, any> }, dIdx: number) => (
                                                                                                    <div key={dIdx} style={{
                                                                                                        fontSize: "9px",
                                                                                                        color: "var(--color-text-secondary)",
                                                                                                        padding: "2px 0",
                                                                                                        borderBottom: dIdx < step.details.length - 1 ? "1px solid var(--color-border)" : "none"
                                                                                                    }}>
                                                                                                        {detail.type === 'search_result' ? (
                                                                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                                                                                                <div>
                                                                                                                    {detail.message.split(' - Top:')[0]}
                                                                                                                </div>
                                                                                                                {detail.data?.full_text && (
                                                                                                                    <div style={{ marginLeft: "12px", fontSize: "9px", color: "var(--color-text-secondary)" }}>
                                                                                                                        <span style={{ fontWeight: 600 }}>Top Tweet:</span>{" "}
                                                                                                                        <ExpandableText text={detail.data.full_text} maxLength={60} />
                                                                                                                    </div>
                                                                                                                )}
                                                                                                                {!detail.data?.full_text && detail.message.includes('Top:') && (
                                                                                                                    <div style={{ marginLeft: "12px", fontSize: "9px", color: "var(--color-text-secondary)" }}>
                                                                                                                        {detail.message.split(' - Top:')[1]}
                                                                                                                    </div>
                                                                                                                )}
                                                                                                            </div>
                                                                                                        ) : (
                                                                                                            detail.message
                                                                                                        )}
                                                                                                    </div>
                                                                                                ))}
                                                                                            </div>
                                                                                        )}
                                                                                    </details>
                                                                                ))}
                                                                            </div>
                                                                        </details>
                                                                    );
                                                                })()}
                                                            </>
                                                        ) : (
                                                            <button
                                                                onClick={(e) => { e.stopPropagation(); startReport(rt.type); }}
                                                                style={{ padding: "8px 16px", background: "var(--gradient-primary)", border: "none", borderRadius: "var(--radius-sm)", color: "#fff", cursor: "pointer", fontSize: "12px", fontWeight: 600 }}
                                                            >
                                                                Start Report
                                                            </button>
                                                        )}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    </main>

                    {/* Chat Toggle Button (when collapsed) - Hide on mobile when sidebar is fullscreen */}
                    {chatCollapsed && !(isMobile && mobileFullscreenPanel === 'sidebar') && (
                        <button
                            onClick={() => {
                                if (isMobile) {
                                    // On mobile, open chat in fullscreen
                                    setMobileFullscreenPanel('chat');
                                    setChatCollapsed(false);
                                } else {
                                    // On desktop, normal expand
                                    setChatCollapsed(false);
                                }
                            }}
                            style={{
                                position: "fixed",
                                right: "0",
                                top: "50%",
                                transform: "translateY(-50%)",
                                width: "32px",
                                height: "80px",
                                background: "var(--gradient-primary)",
                                border: "none",
                                borderRadius: "8px 0 0 8px",
                                cursor: "pointer",
                                display: "flex",
                                flexDirection: "column",
                                alignItems: "center",
                                justifyContent: "center",
                                gap: "6px",
                                zIndex: 100,
                                color: "#fff",
                                boxShadow: "-4px 0 12px rgba(0, 0, 0, 0.15)"
                            }}
                        >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <path d="M15 18l-6-6 6-6" />
                            </svg>
                            <span style={{ writingMode: "vertical-rl", fontSize: "11px", fontWeight: 600 }}>Chat</span>
                        </button>
                    )}

                    {/* RIGHT CHAT PANEL (Collapsible) */}
                    <aside style={{
                        width: isMobile && mobileFullscreenPanel === 'chat'
                            ? "100vw"
                            : chatCollapsed ? "0px" : "380px",
                        minWidth: isMobile && mobileFullscreenPanel === 'chat'
                            ? "100vw"
                            : chatCollapsed ? "0px" : "380px",
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
                        {/* Chat Collapse/Close Button */}
                        {!chatCollapsed && (
                            <button
                                onClick={() => {
                                    if (isMobile) {
                                        // On mobile, close fullscreen and collapse
                                        setMobileFullscreenPanel(null);
                                        setChatCollapsed(true);
                                    } else {
                                        // On desktop, just collapse
                                        setChatCollapsed(true);
                                    }
                                }}
                                style={{
                                    position: "absolute",
                                    left: isMobile && mobileFullscreenPanel === 'chat' ? "auto" : "0",
                                    right: isMobile && mobileFullscreenPanel === 'chat' ? "12px" : "auto",
                                    top: isMobile && mobileFullscreenPanel === 'chat' ? "12px" : "50%",
                                    transform: isMobile && mobileFullscreenPanel === 'chat' ? "none" : "translateY(-50%)",
                                    width: isMobile && mobileFullscreenPanel === 'chat' ? "32px" : "20px",
                                    height: isMobile && mobileFullscreenPanel === 'chat' ? "32px" : "40px",
                                    background: "var(--color-surface-muted)",
                                    border: "1px solid var(--color-border)",
                                    borderLeft: isMobile && mobileFullscreenPanel === 'chat' ? "1px solid var(--color-border)" : "none",
                                    borderRadius: isMobile && mobileFullscreenPanel === 'chat' ? "var(--radius-sm)" : "0 6px 6px 0",
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center",
                                    zIndex: 10,
                                    color: "var(--color-text-muted)"
                                }}
                                title={isMobile ? "Close chat" : "Collapse chat"}
                            >
                                <svg width={isMobile && mobileFullscreenPanel === 'chat' ? "16" : "12"} height={isMobile && mobileFullscreenPanel === 'chat' ? "16" : "12"} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    {isMobile && mobileFullscreenPanel === 'chat'
                                        ? <path d="M18 6L6 18M6 6l12 12" />
                                        : <path d="M9 18l6-6-6-6" />
                                    }
                                </svg>
                            </button>
                        )}

                        {/* Chat Header */}
                        <div style={{
                            padding: "16px",
                            borderBottom: "1px solid var(--color-border)"
                        }}>
                            <div style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "10px"
                            }}>
                                <span style={{ fontSize: "18px" }}>💬</span>
                                <span style={{ fontWeight: 600, fontSize: "14px" }}>AI Research Assistant</span>
                            </div>
                        </div>

                        {/* Chat Messages */}
                        <div style={{ flex: 1, overflow: "auto", padding: "16px", display: "flex", flexDirection: "column", gap: "12px" }}>
                            {messages.length === 0 ? (
                                <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--color-text-muted)" }}>
                                    <div style={{ fontSize: "36px", marginBottom: "12px" }}>👋</div>
                                    <p style={{ margin: 0, fontSize: "14px" }}>Hi! I&apos;m your research assistant.</p>
                                    <p style={{ margin: "6px 0 0", fontSize: "12px" }}>Ask me anything about your project.</p>
                                </div>
                            ) : (
                                messages.map((msg) => (
                                    <div
                                        key={msg.id}
                                        style={{
                                            display: "flex",
                                            flexDirection: "column",
                                            alignItems: msg.is_bot ? "flex-start" : "flex-end"
                                        }}
                                    >
                                        <div style={{
                                            maxWidth: "85%",
                                            padding: "10px 14px",
                                            borderRadius: msg.is_bot ? "14px 14px 14px 4px" : "14px 14px 4px 14px",
                                            background: msg.is_bot ? "var(--color-surface-muted)" : "var(--gradient-primary)",
                                            color: msg.is_bot ? "var(--color-text)" : "#fff",
                                            fontSize: "13px",
                                            lineHeight: 1.5
                                        }}>
                                            {msg.message}
                                        </div>

                                        {/* Time and Mode Badges Row */}
                                        <div style={{
                                            display: "flex",
                                            alignItems: "center",
                                            gap: "8px",
                                            marginTop: "4px",
                                            padding: "0 4px"
                                        }}>
                                            <span style={{ fontSize: "10px", color: "var(--color-text-muted)" }}>
                                                {new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                            </span>

                                            {/* Mode Badges - only show for bot messages with active modes */}
                                            {msg.is_bot && msg.active_modes && msg.active_modes.length > 0 && (
                                                <div style={{
                                                    display: "flex",
                                                    gap: "4px",
                                                    flexWrap: "wrap"
                                                }}>
                                                    {msg.active_modes.map((modeId) => {
                                                        const modeInfo = availableModes.find((m) => m.id === modeId);
                                                        return (
                                                            <span
                                                                key={modeId}
                                                                title={modeInfo?.description || modeId}
                                                                style={{
                                                                    display: "inline-flex",
                                                                    alignItems: "center",
                                                                    gap: "3px",
                                                                    padding: "2px 6px",
                                                                    borderRadius: "10px",
                                                                    background: "var(--color-surface-muted)",
                                                                    border: "1px solid var(--color-border)",
                                                                    fontSize: "9px",
                                                                    color: "var(--color-text-muted)"
                                                                }}
                                                            >
                                                                <span>{modeInfo?.icon || "🔧"}</span>
                                                                <span>{modeInfo?.name || modeId}</span>
                                                            </span>
                                                        );
                                                    })}
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))
                            )}
                            {isTyping && (
                                <div style={{
                                    padding: "10px 14px",
                                    borderRadius: "14px 14px 14px 4px",
                                    background: "var(--color-surface-muted)",
                                    color: "var(--color-text-muted)",
                                    fontSize: "13px",
                                    alignSelf: "flex-start"
                                }}>
                                    Thinking...
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>

                        {/* Chat Input with Fade Effect */}
                        <div style={{
                            position: "relative",
                            background: "var(--color-surface-elevated)",
                            zIndex: 10
                        }}>
                            {/* Fade gradient overlay - positioned above messages */}
                            <div style={{
                                position: "absolute",
                                top: "-80px",
                                left: 0,
                                right: 0,
                                height: "80px",
                                background: "linear-gradient(to bottom, transparent 0%, var(--color-surface-elevated) 100%)",
                                pointerEvents: "none",
                                zIndex: 5
                            }} />

                            {/* Input wrapper */}
                            <div style={{
                                padding: "12px 16px"
                            }}>
                                {/* Mode Toggle Bar - above input */}
                                <div style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                    marginBottom: "10px"
                                }}>
                                    {availableModes.map((mode) => {
                                        const isActive = activeModes.includes(mode.id);
                                        return (
                                            <button
                                                key={mode.id}
                                                onClick={() => toggleMode(mode.id)}
                                                title={mode.description}
                                                style={{
                                                    display: "flex",
                                                    alignItems: "center",
                                                    gap: "6px",
                                                    padding: "6px 14px",
                                                    borderRadius: "20px",
                                                    border: isActive
                                                        ? "2px solid var(--color-primary)"
                                                        : "1px solid var(--color-border)",
                                                    background: isActive
                                                        ? "var(--color-primary-muted)"
                                                        : "var(--color-surface)",
                                                    color: isActive
                                                        ? "var(--color-primary)"
                                                        : "var(--color-text-muted)",
                                                    cursor: "pointer",
                                                    fontSize: "12px",
                                                    fontWeight: isActive ? 600 : 500,
                                                    transition: "all 0.2s ease",
                                                    boxShadow: isActive ? "0 0 8px rgba(99, 102, 241, 0.3)" : "none"
                                                }}
                                            >
                                                <span>{mode.name}</span>
                                                {isActive && (
                                                    <span style={{
                                                        width: "8px",
                                                        height: "8px",
                                                        borderRadius: "50%",
                                                        background: "var(--color-success)",
                                                        marginLeft: "2px",
                                                        boxShadow: "0 0 4px var(--color-success)"
                                                    }} />
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                                <div style={{
                                    display: "flex",
                                    alignItems: "flex-end",
                                    gap: "10px",
                                    padding: "10px",
                                    background: "var(--color-surface-muted)",
                                    borderRadius: "var(--radius-md)",
                                    border: "1px solid var(--color-border)"
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
                                        placeholder="Ask anything..."
                                        rows={1}
                                        style={{
                                            flex: 1,
                                            resize: "none",
                                            border: "none",
                                            background: "transparent",
                                            color: "var(--color-text)",
                                            fontSize: "13px",
                                            lineHeight: 1.5,
                                            outline: "none",
                                            minHeight: "24px",
                                            maxHeight: "100px"
                                        }}
                                    />
                                    <button
                                        onClick={sendMessage}
                                        disabled={!newMessage.trim()}
                                        style={{
                                            width: "32px",
                                            height: "32px",
                                            borderRadius: "var(--radius-sm)",
                                            border: "none",
                                            background: newMessage.trim() ? "var(--gradient-primary)" : "var(--color-surface)",
                                            color: newMessage.trim() ? "#fff" : "var(--color-text-muted)",
                                            cursor: newMessage.trim() ? "pointer" : "not-allowed",
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                            transition: "all 0.15s ease"
                                        }}
                                    >
                                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                            <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
                                        </svg>
                                    </button>
                                </div>
                            </div>
                        </div>
                    </aside>
                </div >
            </div >
        </>
    );
}
