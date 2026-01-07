"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import TopBar from "@/components/TopBar";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Admin emails that can access this page
const ADMIN_EMAILS = ["thehamidrezamafi@gmail.com"];

interface Worker {
    worker_id: string;
    api_type: string;
    status: "idle" | "working" | "offline";
    current_task_id: string | null;
    last_heartbeat: string;
    connected_at: string;
    metadata: Record<string, unknown>;
}

interface WorkerStats {
    api_type: string;
    total: number;
    idle: number;
    working: number;
    offline: number;
}

interface QueueStats {
    pending: Record<string, number>;
    assigned: Record<string, number>;
    running: Record<string, number>;
    total_workers: Record<string, number>;
    idle_workers: Record<string, number>;
}

interface OrchestratorHealth {
    status: string;
    redis: string;
    workers_connected: number;
    timestamp: string;
}

interface TestResult {
    success: boolean;
    task_id?: string;
    status?: string;
    result?: Record<string, unknown>;
    error?: string;
}

// Enrichment interfaces
interface EnrichmentKeyword {
    id: number;
    keyword: string;
    num_companies: number;
    status: "pending" | "processing" | "completed" | "paused" | "failed";
    priority: number;
    created_at: string;
    times_processed: number;
    last_processed_at: string | null;
}

interface EnrichmentHistory {
    id: number;
    keyword_text: string;
    started_at: string;
    completed_at: string | null;
    status: "running" | "completed" | "failed" | "paused";
    companies_found: number;
    companies_scraped: number;
    companies_skipped: number;
    worker_id: string | null;
    error_message: string | null;
    duration_seconds: number | null;
}

interface EnrichmentStatus {
    is_paused: boolean;
    is_active: boolean;
    current_keyword: string | null;
    pending_count: number;
    processing_count: number;
    completed_count: number;
    total_companies_scraped: number;
    idle_workers: number;
    days_threshold: number;
}

// Enrichment Panel Component
function EnrichmentPanel({ token }: { token: string | null }) {
    const [status, setStatus] = useState<EnrichmentStatus | null>(null);
    const [keywords, setKeywords] = useState<EnrichmentKeyword[]>([]);
    const [history, setHistory] = useState<EnrichmentHistory[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [newKeywords, setNewKeywords] = useState("");
    const [numCompanies, setNumCompanies] = useState(50);
    const [isSubmitting, setIsSubmitting] = useState(false);

    const fetchEnrichmentData = useCallback(async () => {
        if (!token) return;

        try {
            const [statusRes, keywordsRes, historyRes] = await Promise.all([
                fetch(`${API_URL}/api/admin/enrichment/status/`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_URL}/api/admin/enrichment/keywords/`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_URL}/api/admin/enrichment/history/?limit=20`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
            ]);

            if (statusRes.ok) setStatus(await statusRes.json());

            // Handle paginated responses from DRF ListViews
            if (keywordsRes.ok) {
                const keywordsData = await keywordsRes.json();
                // DRF pagination returns {count, next, previous, results}
                setKeywords(Array.isArray(keywordsData) ? keywordsData : keywordsData.results || []);
            }
            if (historyRes.ok) {
                const historyData = await historyRes.json();
                setHistory(Array.isArray(historyData) ? historyData : historyData.results || []);
            }
        } catch (err) {
            console.error("Failed to fetch enrichment data:", err);
        } finally {
            setIsLoading(false);
        }
    }, [token]);

    useEffect(() => {
        fetchEnrichmentData();
        const interval = setInterval(fetchEnrichmentData, 10000);
        return () => clearInterval(interval);
    }, [fetchEnrichmentData]);

    const handleAddKeywords = async () => {
        if (!newKeywords.trim() || !token) return;
        setIsSubmitting(true);

        const keywordList = newKeywords
            .split(/[,\n]+/)
            .map(k => k.trim())
            .filter(k => k.length > 0);

        try {
            const res = await fetch(`${API_URL}/api/admin/enrichment/keywords/`, {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    keywords: keywordList,
                    num_companies: numCompanies,
                    priority: 0,
                }),
            });

            if (res.ok) {
                setNewKeywords("");
                fetchEnrichmentData();
            }
        } catch (err) {
            console.error("Failed to add keywords:", err);
        } finally {
            setIsSubmitting(false);
        }
    };

    const handlePauseResume = async (action: "pause" | "resume") => {
        if (!token) return;
        try {
            await fetch(`${API_URL}/api/admin/enrichment/pause-resume/`, {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ action }),
            });
            fetchEnrichmentData();
        } catch (err) {
            console.error("Failed to pause/resume:", err);
        }
    };

    const handleDeleteKeyword = async (id: number) => {
        if (!token) return;
        try {
            await fetch(`${API_URL}/api/admin/enrichment/keywords/${id}/`, {
                method: "DELETE",
                headers: { Authorization: `Bearer ${token}` },
            });
            fetchEnrichmentData();
        } catch (err) {
            console.error("Failed to delete keyword:", err);
        }
    };

    const handleResetStuck = async () => {
        if (!token) return;
        try {
            const response = await fetch(`${API_URL}/api/admin/enrichment/reset-stuck/`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
            });
            if (response.ok) {
                fetchEnrichmentData();
            }
        } catch (err) {
            console.error("Failed to reset stuck keywords:", err);
        }
    };

    const getStatusColor = (s: string) => {
        switch (s) {
            case "pending": return "#3b82f6";
            case "processing": case "running": return "#eab308";
            case "completed": return "#22c55e";
            case "failed": return "#ef4444";
            case "paused": return "#6b7280";
            default: return "#6b7280";
        }
    };

    if (isLoading) {
        return <div style={{ padding: "40px", textAlign: "center" }}><div className="spinner"></div></div>;
    }

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
            {/* Status Card */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "16px" }}>
                <div style={{ padding: "16px", background: "var(--color-surface-muted)", borderRadius: "var(--radius-md)" }}>
                    <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Status</div>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        <span style={{
                            width: "10px", height: "10px", borderRadius: "50%",
                            background: status?.is_paused ? "#6b7280" : status?.is_active ? "#eab308" : "#22c55e"
                        }} />
                        <span style={{ fontWeight: 600, color: "var(--color-heading)" }}>
                            {status?.is_paused ? "Paused" : status?.is_active ? "Active" : "Idle"}
                        </span>
                    </div>
                </div>
                <div style={{ padding: "16px", background: "var(--color-surface-muted)", borderRadius: "var(--radius-md)" }}>
                    <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Pending</div>
                    <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--color-primary)" }}>{status?.pending_count || 0}</div>
                </div>
                <div style={{ padding: "16px", background: "var(--color-surface-muted)", borderRadius: "var(--radius-md)" }}>
                    <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Completed</div>
                    <div style={{ fontSize: "24px", fontWeight: 700, color: "#22c55e" }}>{status?.completed_count || 0}</div>
                </div>
                <div style={{ padding: "16px", background: "var(--color-surface-muted)", borderRadius: "var(--radius-md)" }}>
                    <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "4px" }}>Companies Scraped</div>
                    <div style={{ fontSize: "24px", fontWeight: 700, color: "var(--color-heading)" }}>{status?.total_companies_scraped || 0}</div>
                </div>
            </div>

            {/* Pause/Resume + Current Keyword */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                {status?.current_keyword && (
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                        {status.is_active && status.idle_workers < 1 ? (
                            <div className="spinner" style={{ width: "14px", height: "14px" }}></div>
                        ) : (
                            <span style={{ color: "#f97316", fontSize: "12px" }}>⚠️</span>
                        )}
                        <span style={{ color: "var(--color-text-muted)", fontSize: "14px" }}>
                            {status.is_active && status.idle_workers < 1 ? "Processing: " : "Stuck: "}
                            <strong style={{ color: "var(--color-heading)" }}>{status.current_keyword}</strong>
                        </span>
                        {status.is_active && status.idle_workers >= 1 && (
                            <button
                                onClick={handleResetStuck}
                                style={{
                                    padding: "4px 10px",
                                    background: "#f97316",
                                    border: "none",
                                    borderRadius: "var(--radius-sm)",
                                    color: "#fff",
                                    fontSize: "11px",
                                    cursor: "pointer"
                                }}
                            >Reset</button>
                        )}
                    </div>
                )}
                <button
                    onClick={() => handlePauseResume(status?.is_paused ? "resume" : "pause")}
                    style={{
                        padding: "8px 16px",
                        background: status?.is_paused ? "#22c55e" : "#ef4444",
                        border: "none",
                        borderRadius: "var(--radius-sm)",
                        color: "#fff",
                        fontSize: "13px",
                        fontWeight: 500,
                        cursor: "pointer",
                        marginLeft: "auto"
                    }}
                >
                    {status?.is_paused ? "▶ Resume Enrichment" : "⏸ Pause Enrichment"}
                </button>
            </div>

            {/* Add Keywords Form */}
            <div style={{ padding: "20px", background: "var(--color-surface-muted)", borderRadius: "var(--radius-md)" }}>
                <h4 style={{ margin: "0 0 12px", fontSize: "14px", fontWeight: 600, color: "var(--color-heading)" }}>
                    Add Keywords
                </h4>
                <div style={{ display: "flex", gap: "12px", alignItems: "flex-end" }}>
                    <div style={{ flex: 1 }}>
                        <textarea
                            value={newKeywords}
                            onChange={(e) => setNewKeywords(e.target.value)}
                            placeholder="Enter keywords (comma or newline separated)..."
                            rows={2}
                            style={{
                                width: "100%",
                                padding: "10px 12px",
                                background: "var(--color-surface-elevated)",
                                border: "1px solid var(--color-border)",
                                borderRadius: "var(--radius-sm)",
                                color: "var(--color-text)",
                                fontSize: "14px",
                                resize: "vertical"
                            }}
                        />
                    </div>
                    <div style={{ width: "120px" }}>
                        <label style={{ fontSize: "11px", color: "var(--color-text-muted)", display: "block", marginBottom: "4px" }}>
                            Companies/keyword
                        </label>
                        <input
                            type="number"
                            value={numCompanies}
                            onChange={(e) => setNumCompanies(parseInt(e.target.value) || 50)}
                            min={1}
                            max={500}
                            style={{
                                width: "100%",
                                padding: "10px 12px",
                                background: "var(--color-surface-elevated)",
                                border: "1px solid var(--color-border)",
                                borderRadius: "var(--radius-sm)",
                                color: "var(--color-text)",
                                fontSize: "14px"
                            }}
                        />
                    </div>
                    <button
                        onClick={handleAddKeywords}
                        disabled={isSubmitting || !newKeywords.trim()}
                        style={{
                            padding: "10px 20px",
                            background: isSubmitting ? "var(--color-surface-muted)" : "var(--gradient-primary)",
                            border: "none",
                            borderRadius: "var(--radius-sm)",
                            color: "#fff",
                            fontSize: "14px",
                            fontWeight: 500,
                            cursor: isSubmitting ? "not-allowed" : "pointer"
                        }}
                    >
                        {isSubmitting ? "Adding..." : "Add Keywords"}
                    </button>
                </div>
            </div>

            {/* Keywords Queue */}
            {keywords.length > 0 && (
                <div>
                    <h4 style={{ margin: "0 0 12px", fontSize: "14px", fontWeight: 600, color: "var(--color-heading)" }}>
                        Keyword Queue ({keywords.length})
                    </h4>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                        {keywords.slice(0, 20).map((kw) => (
                            <div key={kw.id} style={{
                                display: "flex",
                                alignItems: "center",
                                gap: "8px",
                                padding: "6px 12px",
                                background: "var(--color-surface-muted)",
                                borderRadius: "16px",
                                border: `1px solid ${getStatusColor(kw.status)}30`,
                            }}>
                                <span style={{ width: "6px", height: "6px", borderRadius: "50%", background: getStatusColor(kw.status) }} />
                                <span style={{ fontSize: "13px", color: "var(--color-text)" }}>{kw.keyword}</span>
                                <span style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>({kw.num_companies})</span>
                                {kw.status === "pending" && (
                                    <button
                                        onClick={() => handleDeleteKeyword(kw.id)}
                                        style={{
                                            background: "none",
                                            border: "none",
                                            color: "#ef4444",
                                            cursor: "pointer",
                                            fontSize: "14px",
                                            padding: "0 4px"
                                        }}
                                    >×</button>
                                )}
                            </div>
                        ))}
                        {keywords.length > 20 && (
                            <span style={{ fontSize: "13px", color: "var(--color-text-muted)", alignSelf: "center" }}>
                                +{keywords.length - 20} more
                            </span>
                        )}
                    </div>
                </div>
            )}

            {/* History Table */}
            <div>
                <h4 style={{ margin: "0 0 12px", fontSize: "14px", fontWeight: 600, color: "var(--color-heading)" }}>
                    Recent History
                </h4>
                {history.length === 0 ? (
                    <div style={{ padding: "20px", textAlign: "center", color: "var(--color-text-muted)", fontSize: "14px" }}>
                        No enrichment history yet
                    </div>
                ) : (
                    <div style={{ overflowX: "auto" }}>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
                            <thead>
                                <tr style={{ background: "var(--color-surface-muted)" }}>
                                    <th style={{ padding: "10px 12px", textAlign: "left", fontWeight: 600, color: "var(--color-text-muted)" }}>Keyword</th>
                                    <th style={{ padding: "10px 12px", textAlign: "left", fontWeight: 600, color: "var(--color-text-muted)" }}>Status</th>
                                    <th style={{ padding: "10px 12px", textAlign: "right", fontWeight: 600, color: "var(--color-text-muted)" }}>Scraped</th>
                                    <th style={{ padding: "10px 12px", textAlign: "right", fontWeight: 600, color: "var(--color-text-muted)" }}>Duration</th>
                                    <th style={{ padding: "10px 12px", textAlign: "left", fontWeight: 600, color: "var(--color-text-muted)" }}>Started</th>
                                </tr>
                            </thead>
                            <tbody>
                                {history.map((h) => (
                                    <tr key={h.id} style={{ borderTop: "1px solid var(--color-border)" }}>
                                        <td style={{ padding: "10px 12px", color: "var(--color-heading)" }}>{h.keyword_text}</td>
                                        <td style={{ padding: "10px 12px" }}>
                                            <span style={{
                                                padding: "2px 8px",
                                                borderRadius: "10px",
                                                fontSize: "11px",
                                                fontWeight: 500,
                                                background: `${getStatusColor(h.status)}20`,
                                                color: getStatusColor(h.status)
                                            }}>
                                                {h.status}
                                            </span>
                                        </td>
                                        <td style={{ padding: "10px 12px", textAlign: "right", color: "var(--color-text)" }}>{h.companies_scraped}</td>
                                        <td style={{ padding: "10px 12px", textAlign: "right", color: "var(--color-text-muted)" }}>
                                            {h.duration_seconds ? `${Math.round(h.duration_seconds)}s` : "—"}
                                        </td>
                                        <td style={{ padding: "10px 12px", color: "var(--color-text-muted)" }}>
                                            {new Date(h.started_at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
}



// Test Worker Panel Component
function TestWorkerPanel({ token, workers }: { token: string | null; workers: Worker[] }) {
    const [selectedWorkerId, setSelectedWorkerId] = useState<string>("");
    const [selectedAction, setSelectedAction] = useState("health");
    const [testPayload, setTestPayload] = useState("{}");
    const [isTestRunning, setIsTestRunning] = useState(false);
    const [testResult, setTestResult] = useState<TestResult | null>(null);

    // Get selected worker's api_type
    const selectedWorker = workers.find(w => w.worker_id === selectedWorkerId);
    const selectedApiType = selectedWorker?.api_type || "crunchbase";

    const actions: Record<string, { value: string; label: string }[]> = {
        crunchbase: [
            { value: "health", label: "Health Check" },
            { value: "search_with_rank", label: "Search with Rank" },
            { value: "search_batch", label: "Batch Search" },
        ],
        tracxn: [
            { value: "health", label: "Health Check" },
            { value: "search_with_rank", label: "Search with Rank" },
        ],
        social: [
            { value: "health", label: "Health Check" },
            { value: "analyze", label: "Analyze" },
        ],
    };

    const samplePayloads: Record<string, string> = {
        health: "{}",
        search_with_rank: JSON.stringify({
            keywords: ["fintech", "payment"],
            target_description: "A fintech startup focused on payment solutions",
            num_companies: 5
        }, null, 2),
        search_batch: JSON.stringify({
            keywords: ["AI", "machine learning"],
            num_companies: 3
        }, null, 2),
        analyze: JSON.stringify({
            company_name: "Example Corp"
        }, null, 2),
    };

    const [taskStatus, setTaskStatus] = useState<string>("");

    const handleTest = async () => {
        setIsTestRunning(true);
        setTestResult(null);
        setTaskStatus("Connecting...");

        let payload = {};
        try {
            payload = JSON.parse(testPayload);
        } catch {
            setTestResult({ success: false, error: "Invalid JSON payload" });
            setIsTestRunning(false);
            return;
        }

        // Build WebSocket URL
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsHost = API_URL.replace(/^https?:\/\//, '');
        const wsUrl = `${wsProtocol}//${wsHost}/ws/admin/tasks/?token=${token}`;

        try {
            const ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                setTaskStatus("Submitting task...");
                ws.send(JSON.stringify({
                    type: 'submit_test',
                    api_type: selectedApiType,
                    action: selectedAction,
                    payload,
                    target_worker_id: selectedWorkerId || undefined,
                }));
            };

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);

                switch (data.type) {
                    case 'task_submitted':
                        setTaskStatus("Task submitted, waiting for worker...");
                        break;
                    case 'task_started':
                        setTestResult(prev => ({ ...prev, task_id: data.task_id } as TestResult));
                        setTaskStatus(`Running on worker (${data.task_id?.substring(0, 8)}...)`);
                        break;
                    case 'task_status':
                        setTaskStatus(`Status: ${data.status}`);
                        break;
                    case 'task_complete':
                        setTestResult({
                            success: data.success,
                            task_id: data.task_id,
                            status: data.success ? 'completed' : 'failed',
                            result: data.result,
                            error: data.error,
                        });
                        setTaskStatus("");
                        setIsTestRunning(false);
                        ws.close();
                        break;
                    case 'task_error':
                    case 'error':
                        setTestResult({
                            success: false,
                            error: data.error || data.message,
                        });
                        setTaskStatus("");
                        setIsTestRunning(false);
                        ws.close();
                        break;
                }
            };

            ws.onerror = (error) => {
                console.error("WebSocket error:", error);
                setTestResult({ success: false, error: "WebSocket connection failed" });
                setTaskStatus("");
                setIsTestRunning(false);
            };

            ws.onclose = () => {
                if (isTestRunning) {
                    setTaskStatus("");
                    setIsTestRunning(false);
                }
            };

        } catch (err) {
            setTestResult({ success: false, error: String(err) });
            setTaskStatus("");
            setIsTestRunning(false);
        }
    };

    return (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {/* Controls */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: "16px", alignItems: "end" }}>
                <div>
                    <label style={{ display: "block", fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "6px" }}>
                        Worker
                    </label>
                    <select
                        value={selectedWorkerId}
                        onChange={(e) => {
                            setSelectedWorkerId(e.target.value);
                            setSelectedAction("health");
                        }}
                        style={{
                            width: "100%",
                            padding: "10px 12px",
                            background: "var(--color-surface-muted)",
                            border: "1px solid var(--color-border)",
                            borderRadius: "var(--radius-sm)",
                            color: "var(--color-text)",
                            fontSize: "14px"
                        }}
                    >
                        <option value="">Select a worker...</option>
                        {workers.filter(w => w.status === "idle").map((w) => (
                            <option key={w.worker_id} value={w.worker_id}>
                                {(w.metadata?.name as string) || w.worker_id.substring(0, 8)} ({w.api_type})
                            </option>
                        ))}
                    </select>
                </div>

                <div>
                    <label style={{ display: "block", fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "6px" }}>
                        Action
                    </label>
                    <select
                        value={selectedAction}
                        onChange={(e) => {
                            setSelectedAction(e.target.value);
                            setTestPayload(samplePayloads[e.target.value] || "{}");
                        }}
                        style={{
                            width: "100%",
                            padding: "10px 12px",
                            background: "var(--color-surface-muted)",
                            border: "1px solid var(--color-border)",
                            borderRadius: "var(--radius-sm)",
                            color: "var(--color-text)",
                            fontSize: "14px"
                        }}
                    >
                        {(actions[selectedApiType] || []).map((a) => (
                            <option key={a.value} value={a.value}>{a.label}</option>
                        ))}
                    </select>
                </div>

                <div>
                    <label style={{ display: "block", fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "6px" }}>
                        Payload (JSON)
                    </label>
                    <input
                        type="text"
                        value={testPayload.replace(/\s+/g, " ")}
                        onChange={(e) => setTestPayload(e.target.value)}
                        style={{
                            width: "100%",
                            padding: "10px 12px",
                            background: "var(--color-surface-muted)",
                            border: "1px solid var(--color-border)",
                            borderRadius: "var(--radius-sm)",
                            color: "var(--color-text)",
                            fontSize: "13px",
                            fontFamily: "monospace"
                        }}
                    />
                </div>

                <button
                    onClick={handleTest}
                    disabled={isTestRunning}
                    style={{
                        padding: "10px 24px",
                        background: isTestRunning ? "var(--color-surface-muted)" : "var(--gradient-primary)",
                        border: "none",
                        borderRadius: "var(--radius-sm)",
                        color: "#fff",
                        fontSize: "14px",
                        fontWeight: 500,
                        cursor: isTestRunning ? "not-allowed" : "pointer",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px"
                    }}
                >
                    {isTestRunning ? (
                        <>
                            <div className="spinner" style={{ width: "14px", height: "14px" }}></div>
                            Testing...
                        </>
                    ) : (
                        <>
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <polygon points="5 3 19 12 5 21 5 3" />
                            </svg>
                            Run Test
                        </>
                    )}
                </button>
            </div>

            {/* Real-time Status */}
            {taskStatus && (
                <div style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "12px 16px",
                    background: "rgba(59, 130, 246, 0.1)",
                    border: "1px solid rgba(59, 130, 246, 0.3)",
                    borderRadius: "var(--radius-md)",
                }}>
                    <div className="spinner" style={{ width: "16px", height: "16px", borderColor: "#3b82f6", borderTopColor: "transparent" }}></div>
                    <span style={{ color: "#3b82f6", fontSize: "14px" }}>{taskStatus}</span>
                </div>
            )}

            {/* Result */}
            {testResult && (
                <div style={{
                    padding: "16px",
                    background: testResult.success ? "rgba(34, 197, 94, 0.1)" : "rgba(239, 68, 68, 0.1)",
                    border: `1px solid ${testResult.success ? "rgba(34, 197, 94, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
                    borderRadius: "var(--radius-md)",
                }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                        <span style={{ fontSize: "18px" }}>{testResult.success ? "✅" : "❌"}</span>
                        <span style={{
                            fontWeight: 600,
                            color: testResult.success ? "#22c55e" : "#ef4444"
                        }}>
                            {testResult.success ? "Test Passed" : "Test Failed"}
                        </span>
                        {testResult.task_id && (
                            <code style={{
                                fontSize: "11px",
                                color: "var(--color-text-muted)",
                                background: "var(--color-surface-muted)",
                                padding: "2px 6px",
                                borderRadius: "4px"
                            }}>
                                {testResult.task_id.substring(0, 12)}...
                            </code>
                        )}
                    </div>

                    {testResult.error && (
                        <div style={{ color: "#ef4444", fontSize: "13px", marginBottom: "8px" }}>
                            Error: {testResult.error}
                        </div>
                    )}

                    {testResult.result && (
                        <pre style={{
                            margin: 0,
                            padding: "12px",
                            background: "var(--color-surface-muted)",
                            borderRadius: "var(--radius-sm)",
                            fontSize: "12px",
                            color: "var(--color-text)",
                            overflow: "auto",
                            maxHeight: "200px"
                        }}>
                            {JSON.stringify(testResult.result, null, 2)}
                        </pre>
                    )}
                </div>
            )}
        </div>
    );
}
export default function AdminPage() {
    const { user, token, isLoading, isAuthenticated } = useAuth();
    const router = useRouter();

    const [health, setHealth] = useState<OrchestratorHealth | null>(null);
    const [workers, setWorkers] = useState<Worker[]>([]);
    const [workerStats, setWorkerStats] = useState<Record<string, WorkerStats>>({});
    const [queueStats, setQueueStats] = useState<QueueStats | null>(null);
    const [isLoadingData, setIsLoadingData] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

    // Check if current user is admin
    const isAdmin = user?.email && ADMIN_EMAILS.includes(user.email);

    const fetchOrchestratorData = useCallback(async () => {
        try {
            setError(null);

            // Fetch all data from backend proxy endpoints
            const [healthRes, workersRes, queueRes] = await Promise.all([
                fetch(`${API_URL}/api/admin/orchestrator/health/`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_URL}/api/admin/orchestrator/workers/`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
                fetch(`${API_URL}/api/admin/orchestrator/queue/`, {
                    headers: { Authorization: `Bearer ${token}` },
                }),
            ]);

            if (healthRes.ok) {
                const healthData = await healthRes.json();
                setHealth(healthData);
            }

            if (workersRes.ok) {
                const workersData = await workersRes.json();
                setWorkers(workersData.workers || []);
                setWorkerStats(workersData.stats || {});
            }

            if (queueRes.ok) {
                const queueData = await queueRes.json();
                setQueueStats(queueData);
            }

            setLastUpdated(new Date());
        } catch (err) {
            console.error("Failed to fetch orchestrator data:", err);
            setError("Failed to connect to orchestrator. Is it running?");
        } finally {
            setIsLoadingData(false);
        }
    }, [token]);

    useEffect(() => {
        if (!isLoading && !isAuthenticated) {
            router.push("/login");
        }
    }, [isLoading, isAuthenticated, router]);

    // Redirect non-admin users
    useEffect(() => {
        if (!isLoading && isAuthenticated && !isAdmin) {
            router.push("/dashboard");
        }
    }, [isLoading, isAuthenticated, isAdmin, router]);

    useEffect(() => {
        if (token && isAdmin) {
            fetchOrchestratorData();
            // Refresh every 5 seconds
            const interval = setInterval(fetchOrchestratorData, 5000);
            return () => clearInterval(interval);
        }
    }, [token, isAdmin, fetchOrchestratorData]);

    if (isLoading || !isAuthenticated || !isAdmin) {
        return (
            <div className="loading" style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <div className="spinner"></div>
            </div>
        );
    }

    const getStatusColor = (status: string) => {
        switch (status) {
            case "idle": return "#22c55e";
            case "working": return "#eab308";
            case "offline": return "#ef4444";
            case "healthy": return "#22c55e";
            case "degraded": return "#f97316";
            default: return "#6b7280";
        }
    };

    const getStatusBg = (status: string) => {
        switch (status) {
            case "idle": return "rgba(34, 197, 94, 0.1)";
            case "working": return "rgba(234, 179, 8, 0.1)";
            case "offline": return "rgba(239, 68, 68, 0.1)";
            case "healthy": return "rgba(34, 197, 94, 0.1)";
            case "degraded": return "rgba(249, 115, 22, 0.1)";
            default: return "rgba(107, 114, 128, 0.1)";
        }
    };

    // Tehran timezone
    const TEHRAN_TIMEZONE = "Asia/Tehran";

    // Helper to ensure timestamp is treated as UTC
    const parseUtcTimestamp = (timestamp: string): Date => {
        const utcTimestamp = timestamp.endsWith('Z') || timestamp.includes('+') || timestamp.includes('-', 10)
            ? timestamp
            : timestamp + 'Z';
        return new Date(utcTimestamp);
    };

    const formatTime = (timestamp: string) => {
        const date = parseUtcTimestamp(timestamp);
        return date.toLocaleTimeString("fa-IR", {
            timeZone: TEHRAN_TIMEZONE,
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false
        });
    };

    const formatDateTime = (timestamp: string) => {
        const date = parseUtcTimestamp(timestamp);
        return date.toLocaleString("en-US", {
            timeZone: TEHRAN_TIMEZONE,
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false
        });
    };

    const formatDuration = (timestamp: string) => {
        const now = new Date();
        const then = parseUtcTimestamp(timestamp);
        const diffMs = now.getTime() - then.getTime();
        const diffSecs = Math.floor(diffMs / 1000);
        const diffMins = Math.floor(diffSecs / 60);
        const diffHours = Math.floor(diffMins / 60);

        if (diffHours > 0) return `${diffHours}h ${diffMins % 60}m ago`;
        if (diffMins > 0) return `${diffMins}m ago`;
        if (diffSecs > 10) return `${diffSecs}s ago`;
        return "Just now";
    };

    const getWorkerName = (worker: Worker) => {
        return (worker.metadata?.name as string) || worker.worker_id.substring(0, 8);
    };

    return (
        <>
            <TopBar />
            <div className="page-with-topbar" style={{ background: "transparent" }}>
                <div style={{ maxWidth: "1400px", margin: "0 auto", padding: "32px 24px" }}>
                    {/* Header */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "32px" }}>
                        <div>
                            <h1 style={{ margin: "0 0 6px", fontSize: "28px", fontWeight: 700, color: "var(--color-heading)" }}>
                                🎛️ Admin Dashboard
                            </h1>
                            <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: "14px" }}>
                                Monitor orchestrator status and connected workers
                            </p>
                        </div>
                        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                            {lastUpdated && (
                                <span style={{ color: "var(--color-text-muted)", fontSize: "12px" }}>
                                    Last updated: {lastUpdated.toLocaleTimeString()}
                                </span>
                            )}
                            <button
                                onClick={fetchOrchestratorData}
                                style={{
                                    padding: "8px 16px",
                                    background: "var(--color-surface-elevated)",
                                    border: "1px solid var(--color-border)",
                                    borderRadius: "var(--radius-sm)",
                                    color: "var(--color-text)",
                                    fontSize: "13px",
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "6px"
                                }}
                            >
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M23 4v6h-6M1 20v-6h6M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15" />
                                </svg>
                                Refresh
                            </button>
                        </div>
                    </div>

                    {error && (
                        <div style={{
                            padding: "16px 20px",
                            background: "rgba(239, 68, 68, 0.1)",
                            border: "1px solid rgba(239, 68, 68, 0.3)",
                            borderRadius: "var(--radius-md)",
                            color: "#ef4444",
                            marginBottom: "24px",
                            display: "flex",
                            alignItems: "center",
                            gap: "10px"
                        }}>
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                <circle cx="12" cy="12" r="10" />
                                <line x1="12" y1="8" x2="12" y2="12" />
                                <line x1="12" y1="16" x2="12.01" y2="16" />
                            </svg>
                            {error}
                        </div>
                    )}

                    {isLoadingData ? (
                        <div style={{ display: "flex", justifyContent: "center", padding: "60px" }}>
                            <div className="spinner"></div>
                        </div>
                    ) : (
                        <>
                            {/* Orchestrator Health Card */}
                            <div style={{
                                background: "var(--color-surface-elevated)",
                                borderRadius: "var(--radius-lg)",
                                border: "1px solid var(--color-border)",
                                padding: "24px",
                                marginBottom: "24px"
                            }}>
                                <h2 style={{ margin: "0 0 20px", fontSize: "18px", fontWeight: 600, color: "var(--color-heading)", display: "flex", alignItems: "center", gap: "10px" }}>
                                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <circle cx="12" cy="12" r="10" />
                                        <polyline points="12,6 12,12 16,14" />
                                    </svg>
                                    Orchestrator Status
                                </h2>

                                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "20px" }}>
                                    <div style={{ padding: "16px", background: "var(--color-surface-muted)", borderRadius: "var(--radius-md)" }}>
                                        <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "6px" }}>Status</div>
                                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                            <span style={{
                                                width: "10px",
                                                height: "10px",
                                                borderRadius: "50%",
                                                background: getStatusColor(health?.status || "offline"),
                                                animation: health?.status === "healthy" ? "pulse 2s infinite" : "none"
                                            }} />
                                            <span style={{ fontSize: "16px", fontWeight: 600, color: "var(--color-heading)", textTransform: "capitalize" }}>
                                                {health?.status || "Unknown"}
                                            </span>
                                        </div>
                                    </div>

                                    <div style={{ padding: "16px", background: "var(--color-surface-muted)", borderRadius: "var(--radius-md)" }}>
                                        <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "6px" }}>Redis Connection</div>
                                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                            <span style={{
                                                width: "10px",
                                                height: "10px",
                                                borderRadius: "50%",
                                                background: health?.redis === "connected" ? "#22c55e" : "#ef4444"
                                            }} />
                                            <span style={{ fontSize: "16px", fontWeight: 600, color: "var(--color-heading)", textTransform: "capitalize" }}>
                                                {health?.redis || "Unknown"}
                                            </span>
                                        </div>
                                    </div>

                                    <div style={{ padding: "16px", background: "var(--color-surface-muted)", borderRadius: "var(--radius-md)" }}>
                                        <div style={{ fontSize: "12px", color: "var(--color-text-muted)", marginBottom: "6px" }}>Workers Connected</div>
                                        <div style={{ fontSize: "28px", fontWeight: 700, color: "var(--color-primary)" }}>
                                            {health?.workers_connected ?? 0}
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Worker Stats by Type */}
                            <div style={{
                                display: "grid",
                                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                                gap: "20px",
                                marginBottom: "24px"
                            }}>
                                {["crunchbase", "tracxn", "social"].map(apiType => {
                                    const stats = workerStats[apiType] || { total: 0, idle: 0, working: 0, offline: 0 };
                                    const pending = queueStats?.pending?.[apiType] || 0;

                                    return (
                                        <div key={apiType} style={{
                                            background: "var(--color-surface-elevated)",
                                            borderRadius: "var(--radius-lg)",
                                            border: "1px solid var(--color-border)",
                                            padding: "24px",
                                        }}>
                                            <h3 style={{
                                                margin: "0 0 16px",
                                                fontSize: "16px",
                                                fontWeight: 600,
                                                color: "var(--color-heading)",
                                                textTransform: "capitalize",
                                                display: "flex",
                                                alignItems: "center",
                                                gap: "10px"
                                            }}>
                                                <span style={{
                                                    width: "32px",
                                                    height: "32px",
                                                    borderRadius: "8px",
                                                    background: "var(--gradient-primary)",
                                                    display: "flex",
                                                    alignItems: "center",
                                                    justifyContent: "center",
                                                    fontSize: "14px"
                                                }}>
                                                    {apiType === "crunchbase" ? "🅒" : apiType === "tracxn" ? "📊" : "🌐"}
                                                </span>
                                                {apiType} Workers
                                            </h3>

                                            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                                                <div style={{ padding: "12px", background: getStatusBg("idle"), borderRadius: "var(--radius-sm)" }}>
                                                    <div style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>Idle</div>
                                                    <div style={{ fontSize: "20px", fontWeight: 700, color: getStatusColor("idle") }}>
                                                        {stats.idle}
                                                    </div>
                                                </div>
                                                <div style={{ padding: "12px", background: getStatusBg("working"), borderRadius: "var(--radius-sm)" }}>
                                                    <div style={{ fontSize: "11px", color: "var(--color-text-muted)" }}>Working</div>
                                                    <div style={{ fontSize: "20px", fontWeight: 700, color: getStatusColor("working") }}>
                                                        {stats.working}
                                                    </div>
                                                </div>
                                            </div>

                                            <div style={{
                                                marginTop: "12px",
                                                padding: "10px 12px",
                                                background: "var(--color-surface-muted)",
                                                borderRadius: "var(--radius-sm)",
                                                display: "flex",
                                                justifyContent: "space-between",
                                                alignItems: "center"
                                            }}>
                                                <span style={{ fontSize: "12px", color: "var(--color-text-muted)" }}>Pending Tasks</span>
                                                <span style={{
                                                    fontSize: "14px",
                                                    fontWeight: 600,
                                                    color: pending > 0 ? "#f97316" : "var(--color-text-muted)"
                                                }}>
                                                    {pending}
                                                </span>
                                                {pending > 0 && (
                                                    <button
                                                        onClick={async () => {
                                                            if (!confirm(`Are you sure you want to clear ${pending} pending tasks for ${apiType}?`)) return;
                                                            try {
                                                                await fetch(`${API_URL}/api/admin/orchestrator/queue/clear/?api_type=${apiType}`, {
                                                                    method: "DELETE",
                                                                    headers: { Authorization: `Bearer ${token}` },
                                                                });
                                                                fetchOrchestratorData();
                                                            } catch (err) {
                                                                console.error("Failed to clear queue:", err);
                                                                alert("Failed to clear queue");
                                                            }
                                                        }}
                                                        style={{
                                                            background: "none",
                                                            border: "none",
                                                            color: "#ef4444",
                                                            fontSize: "11px",
                                                            cursor: "pointer",
                                                            textDecoration: "underline",
                                                            padding: 0
                                                        }}
                                                    >
                                                        Clear
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Connected Workers Table */}
                            <div style={{
                                background: "var(--color-surface-elevated)",
                                borderRadius: "var(--radius-lg)",
                                border: "1px solid var(--color-border)",
                                overflow: "hidden"
                            }}>
                                <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--color-border)" }}>
                                    <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 600, color: "var(--color-heading)" }}>
                                        Connected Workers ({workers.length})
                                    </h2>
                                </div>

                                {workers.length === 0 ? (
                                    <div style={{ padding: "40px", textAlign: "center", color: "var(--color-text-muted)" }}>
                                        <div style={{ fontSize: "32px", marginBottom: "8px" }}>🔌</div>
                                        <p style={{ margin: 0 }}>No workers connected. Deploy remote workers to get started.</p>
                                    </div>
                                ) : (
                                    <div style={{ overflowX: "auto" }}>
                                        <table style={{ width: "100%", borderCollapse: "collapse" }}>
                                            <thead>
                                                <tr style={{ background: "var(--color-surface-muted)" }}>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Name</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Worker ID</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Type</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Status</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Current Task</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Last Heartbeat</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Connected (Tehran)</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {workers.map((worker) => (
                                                    <tr key={worker.worker_id} style={{ borderTop: "1px solid var(--color-border)" }}>
                                                        <td style={{ padding: "14px 16px" }}>
                                                            <span style={{ fontWeight: 500, color: "var(--color-heading)" }}>
                                                                {getWorkerName(worker)}
                                                            </span>
                                                        </td>
                                                        <td style={{ padding: "14px 16px" }}>
                                                            <code style={{ fontSize: "12px", color: "var(--color-text)", background: "var(--color-surface-muted)", padding: "2px 6px", borderRadius: "4px" }}>
                                                                {worker.worker_id.substring(0, 8)}...
                                                            </code>
                                                        </td>
                                                        <td style={{ padding: "14px 16px" }}>
                                                            <span style={{
                                                                padding: "4px 10px",
                                                                borderRadius: "12px",
                                                                fontSize: "12px",
                                                                fontWeight: 500,
                                                                background: "var(--gradient-primary)",
                                                                color: "#fff",
                                                                textTransform: "capitalize"
                                                            }}>
                                                                {worker.api_type}
                                                            </span>
                                                        </td>
                                                        <td style={{ padding: "14px 16px" }}>
                                                            <span style={{
                                                                display: "inline-flex",
                                                                alignItems: "center",
                                                                gap: "6px",
                                                                padding: "4px 10px",
                                                                borderRadius: "12px",
                                                                fontSize: "12px",
                                                                fontWeight: 500,
                                                                background: getStatusBg(worker.status),
                                                                color: getStatusColor(worker.status),
                                                                textTransform: "capitalize"
                                                            }}>
                                                                <span style={{
                                                                    width: "6px",
                                                                    height: "6px",
                                                                    borderRadius: "50%",
                                                                    background: getStatusColor(worker.status)
                                                                }} />
                                                                {worker.status}
                                                            </span>
                                                        </td>
                                                        <td style={{ padding: "14px 16px", color: "var(--color-text-muted)", fontSize: "13px" }}>
                                                            {worker.current_task_id ? (
                                                                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                                                                    <code style={{ fontSize: "11px", color: "#eab308" }}>
                                                                        {worker.current_task_id.substring(0, 8)}...
                                                                    </code>
                                                                    <button
                                                                        onClick={async () => {
                                                                            if (!confirm(`Are you sure you want to STOP this task?`)) return;
                                                                            try {
                                                                                await fetch(`${API_URL}/api/admin/orchestrator/queue/clear/?task_id=${worker.current_task_id}`, {
                                                                                    method: "DELETE",
                                                                                    headers: { Authorization: `Bearer ${token}` },
                                                                                });
                                                                                fetchOrchestratorData();
                                                                            } catch (err) {
                                                                                console.error("Failed to stop task:", err);
                                                                                alert("Failed to stop task");
                                                                            }
                                                                        }}
                                                                        title="Force Stop Task"
                                                                        style={{
                                                                            background: "rgba(239, 68, 68, 0.1)",
                                                                            border: "1px solid rgba(239, 68, 68, 0.2)",
                                                                            borderRadius: "4px",
                                                                            color: "#ef4444",
                                                                            cursor: "pointer",
                                                                            fontSize: "10px",
                                                                            padding: "2px 6px",
                                                                            lineHeight: 1
                                                                        }}
                                                                    >
                                                                        STOP
                                                                    </button>
                                                                </div>
                                                            ) : "—"}
                                                        </td>
                                                        <td style={{ padding: "14px 16px", color: "var(--color-text-muted)", fontSize: "13px" }}>
                                                            {formatDuration(worker.last_heartbeat)}
                                                        </td>
                                                        <td style={{ padding: "14px 16px", color: "var(--color-text-muted)", fontSize: "13px" }}>
                                                            {formatDateTime(worker.connected_at)}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>

                            {/* Database Enrichment Panel */}
                            <div style={{
                                background: "var(--color-surface-elevated)",
                                borderRadius: "var(--radius-lg)",
                                border: "1px solid var(--color-border)",
                                overflow: "hidden",
                                marginTop: "24px"
                            }}>
                                <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--color-border)" }}>
                                    <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 600, color: "var(--color-heading)" }}>
                                        📚 Database Enrichment
                                    </h2>
                                    <p style={{ margin: "4px 0 0", fontSize: "13px", color: "var(--color-text-muted)" }}>
                                        Background scraping using idle workers (180-day freshness)
                                    </p>
                                </div>

                                <div style={{ padding: "24px" }}>
                                    <EnrichmentPanel token={token} />
                                </div>
                            </div>

                            {/* Worker Test Panel */}
                            <div style={{
                                background: "var(--color-surface-elevated)",
                                borderRadius: "var(--radius-lg)",
                                border: "1px solid var(--color-border)",
                                overflow: "hidden",
                                marginTop: "24px"
                            }}>
                                <div style={{ padding: "20px 24px", borderBottom: "1px solid var(--color-border)" }}>
                                    <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 600, color: "var(--color-heading)" }}>
                                        🧪 Test Workers
                                    </h2>
                                </div>

                                <div style={{ padding: "24px" }}>
                                    <TestWorkerPanel token={token} workers={workers} />
                                </div>
                            </div>
                        </>
                    )}
                </div>
            </div>

            <style jsx>{`
                @keyframes pulse {
                    0%, 100% { opacity: 1; }
                    50% { opacity: 0.5; }
                }
            `}</style>
        </>
    );
}
