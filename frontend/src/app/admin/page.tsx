"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import TopBar from "@/components/TopBar";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

export default function AdminPage() {
    const { token, isLoading, isAuthenticated } = useAuth();
    const router = useRouter();

    const [health, setHealth] = useState<OrchestratorHealth | null>(null);
    const [workers, setWorkers] = useState<Worker[]>([]);
    const [workerStats, setWorkerStats] = useState<Record<string, WorkerStats>>({});
    const [queueStats, setQueueStats] = useState<QueueStats | null>(null);
    const [isLoadingData, setIsLoadingData] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

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

    useEffect(() => {
        if (token) {
            fetchOrchestratorData();
            // Refresh every 5 seconds
            const interval = setInterval(fetchOrchestratorData, 5000);
            return () => clearInterval(interval);
        }
    }, [token, fetchOrchestratorData]);

    if (isLoading || !isAuthenticated) {
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

    const formatTime = (timestamp: string) => {
        const date = new Date(timestamp);
        return date.toLocaleTimeString();
    };

    const formatDuration = (timestamp: string) => {
        const now = new Date();
        const then = new Date(timestamp);
        const diffMs = now.getTime() - then.getTime();
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);

        if (diffHours > 0) return `${diffHours}h ${diffMins % 60}m ago`;
        if (diffMins > 0) return `${diffMins}m ago`;
        return "Just now";
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
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Worker ID</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Type</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Status</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Current Task</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Last Heartbeat</th>
                                                    <th style={{ padding: "12px 16px", textAlign: "left", fontSize: "12px", fontWeight: 600, color: "var(--color-text-muted)", textTransform: "uppercase" }}>Connected</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                {workers.map((worker) => (
                                                    <tr key={worker.worker_id} style={{ borderTop: "1px solid var(--color-border)" }}>
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
                                                                <code style={{ fontSize: "11px", color: "#eab308" }}>
                                                                    {worker.current_task_id.substring(0, 12)}...
                                                                </code>
                                                            ) : "—"}
                                                        </td>
                                                        <td style={{ padding: "14px 16px", color: "var(--color-text-muted)", fontSize: "13px" }}>
                                                            {formatDuration(worker.last_heartbeat)}
                                                        </td>
                                                        <td style={{ padding: "14px 16px", color: "var(--color-text-muted)", fontSize: "13px" }}>
                                                            {formatTime(worker.connected_at)}
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
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
