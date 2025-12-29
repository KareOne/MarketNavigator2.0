"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import TopBar from "@/components/TopBar";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Project {
    id: string;
    name: string;
    description: string;
    status: string;
    created_at: string;
    inputs?: {
        completion_status: string;
        startup_name: string;
    };
}

interface Organization {
    id: string;
    name: string;
    slug: string;
    plan_tier: string;
}

export default function DashboardPage() {
    const { user, token, isLoading, isAuthenticated } = useAuth();
    const router = useRouter();
    const [projects, setProjects] = useState<Project[]>([]);
    const [organization, setOrganization] = useState<Organization | null>(null);
    const [isLoadingData, setIsLoadingData] = useState(true);
    const [searchQuery, setSearchQuery] = useState("");

    useEffect(() => {
        if (!isLoading && !isAuthenticated) {
            router.push("/login");
        }
    }, [isLoading, isAuthenticated, router]);

    useEffect(() => {
        if (token) {
            fetchOrganizationAndProjects();
        }
    }, [token]);

    const fetchOrganizationAndProjects = async () => {
        try {
            // Fetch or create organization
            const orgRes = await fetch(`${API_URL}/api/organizations/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            const orgData = await orgRes.json();
            const orgs = orgData.results || orgData || [];

            let org = orgs[0];

            if (!org) {
                const createRes = await fetch(`${API_URL}/api/organizations/`, {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ name: `${user?.username}'s Workspace` }),
                });
                org = await createRes.json();
            }

            setOrganization(org);

            // Fetch ALL projects for this user (no organization filter)
            const projRes = await fetch(`${API_URL}/api/projects/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            const projs = await projRes.json();
            setProjects(projs.results || projs || []);
        } catch (error) {
            console.error("Failed to fetch data:", error);
        } finally {
            setIsLoadingData(false);
        }
    };

    const filteredProjects = projects.filter((p) =>
        p.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.description?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    if (isLoading || !isAuthenticated) {
        return (
            <div className="loading" style={{ height: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <div className="spinner"></div>
            </div>
        );
    }

    return (
        <>
            <TopBar />
            <div className="page-with-topbar" style={{ background: "transparent" }}>
                {/* Dashboard Content */}
                <div style={{ maxWidth: "1200px", margin: "0 auto", padding: "32px 24px" }}>
                    {/* Header */}
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "32px", flexWrap: "wrap", gap: "16px" }}>
                        <div>
                            <h1 style={{ margin: "0 0 6px", fontSize: "28px", fontWeight: 700, color: "var(--color-heading)" }}>
                                My Projects
                            </h1>
                            <p style={{ margin: 0, color: "var(--color-text-muted)", fontSize: "14px" }}>
                                {projects.length} project{projects.length !== 1 ? "s" : ""}
                            </p>
                        </div>

                        <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                            {/* Search */}
                            <div style={{ position: "relative" }}>
                                <svg
                                    width="16"
                                    height="16"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                    style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", color: "var(--color-text-muted)" }}
                                >
                                    <circle cx="11" cy="11" r="8" />
                                    <path d="M21 21l-4.35-4.35" />
                                </svg>
                                <input
                                    type="text"
                                    placeholder="Search projects..."
                                    value={searchQuery}
                                    onChange={(e) => setSearchQuery(e.target.value)}
                                    style={{
                                        padding: "10px 14px 10px 38px",
                                        width: "220px",
                                        borderRadius: "var(--radius-sm)",
                                        border: "1px solid var(--color-border)",
                                        background: "var(--color-surface-muted)",
                                        color: "var(--color-text)",
                                        fontSize: "13px"
                                    }}
                                />
                            </div>

                            {/* New Project Button */}
                            <Link
                                href="/projects/new"
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: "8px",
                                    padding: "10px 20px",
                                    background: "var(--gradient-primary)",
                                    color: "#fff",
                                    borderRadius: "var(--radius-sm)",
                                    fontWeight: 600,
                                    fontSize: "14px",
                                    textDecoration: "none",
                                    transition: "transform 0.15s ease, box-shadow 0.15s ease"
                                }}
                            >
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M12 5v14M5 12h14" />
                                </svg>
                                New Project
                            </Link>
                        </div>
                    </div>

                    {isLoadingData ? (
                        <div style={{ display: "flex", justifyContent: "center", padding: "60px" }}>
                            <div className="spinner"></div>
                        </div>
                    ) : filteredProjects.length === 0 ? (
                        <div style={{
                            textAlign: "center",
                            padding: "80px 40px",
                            background: "var(--color-surface-elevated)",
                            borderRadius: "var(--radius-lg)",
                            border: "2px dashed var(--color-border)"
                        }}>
                            <div style={{ fontSize: "48px", marginBottom: "16px" }}>📁</div>
                            <p style={{ color: "var(--color-text-muted)", fontSize: "16px", margin: "0 0 24px" }}>
                                {searchQuery ? "No projects match your search." : "No projects yet. Create your first project to start researching."}
                            </p>
                            {!searchQuery && (
                                <Link
                                    href="/projects/new"
                                    style={{
                                        display: "inline-flex",
                                        alignItems: "center",
                                        gap: "8px",
                                        padding: "12px 24px",
                                        background: "var(--gradient-primary)",
                                        color: "#fff",
                                        borderRadius: "var(--radius-sm)",
                                        fontWeight: 600,
                                        textDecoration: "none"
                                    }}
                                >
                                    Create Project
                                </Link>
                            )}
                        </div>
                    ) : (
                        <div style={{
                            display: "grid",
                            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
                            gap: "20px"
                        }}>
                            {filteredProjects.map((project) => (
                                <div
                                    key={project.id}
                                    onClick={() => router.push(`/projects/${project.id}`)}
                                    style={{
                                        background: "var(--color-surface-elevated)",
                                        borderRadius: "var(--radius-md)",
                                        padding: "24px",
                                        cursor: "pointer",
                                        transition: "transform 0.2s ease, box-shadow 0.2s ease",
                                        border: "1px solid var(--color-border)"
                                    }}
                                    onMouseEnter={(e) => {
                                        e.currentTarget.style.transform = "translateY(-4px)";
                                        e.currentTarget.style.boxShadow = "0 12px 32px rgba(0, 0, 0, 0.15)";
                                    }}
                                    onMouseLeave={(e) => {
                                        e.currentTarget.style.transform = "translateY(0)";
                                        e.currentTarget.style.boxShadow = "none";
                                    }}
                                >
                                    <div style={{ display: "flex", alignItems: "flex-start", gap: "14px", marginBottom: "16px" }}>
                                        <div style={{
                                            width: "42px",
                                            height: "42px",
                                            borderRadius: "10px",
                                            background: "var(--gradient-primary)",
                                            display: "flex",
                                            alignItems: "center",
                                            justifyContent: "center",
                                            fontWeight: 700,
                                            fontSize: "16px",
                                            color: "#fff",
                                            flexShrink: 0
                                        }}>
                                            {project.name.charAt(0).toUpperCase()}
                                        </div>
                                        <div style={{ flex: 1, minWidth: 0 }}>
                                            <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 600, color: "var(--color-heading)" }}>
                                                {project.name}
                                            </h3>
                                            <p style={{
                                                margin: "4px 0 0",
                                                color: "var(--color-text-muted)",
                                                fontSize: "13px",
                                                overflow: "hidden",
                                                textOverflow: "ellipsis",
                                                whiteSpace: "nowrap"
                                            }}>
                                                {project.description || "No description"}
                                            </p>
                                        </div>
                                    </div>

                                    <div style={{
                                        display: "flex",
                                        justifyContent: "space-between",
                                        alignItems: "center",
                                        paddingTop: "14px",
                                        borderTop: "1px solid var(--color-border)"
                                    }}>
                                        <span style={{ color: "var(--color-text-muted)", fontSize: "12px" }}>
                                            {new Date(project.created_at).toLocaleDateString()}
                                        </span>
                                        <span style={{
                                            padding: "3px 8px",
                                            borderRadius: "12px",
                                            fontSize: "11px",
                                            fontWeight: 600,
                                            background: project.inputs?.completion_status === "complete"
                                                ? "var(--color-success-bg)"
                                                : "var(--color-warning-bg)",
                                            color: project.inputs?.completion_status === "complete"
                                                ? "var(--color-success)"
                                                : "var(--color-warning)"
                                        }}>
                                            {project.inputs?.completion_status || "incomplete"}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </>
    );
}
