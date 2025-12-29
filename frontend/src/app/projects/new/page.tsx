"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import TopBar from "@/components/TopBar";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function NewProjectPage() {
    const { token, isAuthenticated, isLoading: authLoading } = useAuth();
    const router = useRouter();
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [error, setError] = useState("");
    const [organizationId, setOrganizationId] = useState<string | null>(null);

    const [formData, setFormData] = useState({
        name: "",
        description: "",
    });

    useEffect(() => {
        if (!authLoading && !isAuthenticated) {
            router.push("/login");
        }
    }, [authLoading, isAuthenticated, router]);

    useEffect(() => {
        if (token) {
            fetchOrCreateOrganization();
        }
    }, [token]);

    const fetchOrCreateOrganization = async () => {
        try {
            const res = await fetch(`${API_URL}/api/organizations/`, {
                headers: { Authorization: `Bearer ${token}` },
            });
            const orgs = await res.json();
            if (orgs.length > 0) {
                setOrganizationId(orgs[0].id);
            } else {
                const createRes = await fetch(`${API_URL}/api/organizations/`, {
                    method: "POST",
                    headers: {
                        Authorization: `Bearer ${token}`,
                        "Content-Type": "application/json",
                    },
                    body: JSON.stringify({ name: "My Organization" }),
                });
                if (createRes.ok) {
                    const newOrg = await createRes.json();
                    setOrganizationId(newOrg.id);
                }
            }
        } catch (err) {
            console.error("Failed to fetch/create organization:", err);
        }
    };

    const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError("");

        if (!formData.name.trim()) {
            setError("Project name is required");
            return;
        }

        if (!organizationId) {
            setError("Please wait while we set up your workspace...");
            return;
        }

        setIsSubmitting(true);
        try {
            const res = await fetch(`${API_URL}/api/projects/`, {
                method: "POST",
                headers: {
                    Authorization: `Bearer ${token}`,
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({
                    name: formData.name,
                    description: formData.description,
                    organization_id: organizationId,
                }),
            });

            if (res.ok) {
                const project = await res.json();
                router.push(`/projects/${project.id}`);
            } else {
                const errData = await res.json();
                setError(Object.values(errData).flat().join(", ") || "Failed to create project");
            }
        } catch (err) {
            console.error("Failed to create project:", err);
            setError("Network error. Please try again.");
        } finally {
            setIsSubmitting(false);
        }
    };

    if (authLoading) {
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
                <div style={{
                    display: "flex",
                    justifyContent: "center",
                    alignItems: "center",
                    minHeight: "calc(100vh - 48px)",
                    padding: "40px 20px"
                }}>
                    <div style={{
                        width: "100%",
                        maxWidth: "440px",
                        background: "var(--color-surface-elevated)",
                        borderRadius: "var(--radius-lg)",
                        padding: "36px",
                        border: "1px solid var(--color-border)",
                        boxShadow: "0 20px 60px rgba(0, 0, 0, 0.2)"
                    }}>
                        <h1 style={{ margin: "0 0 8px", fontSize: "22px", fontWeight: 700, color: "var(--color-heading)" }}>
                            Create New Project
                        </h1>
                        <p style={{ margin: "0 0 28px", color: "var(--color-text-muted)", fontSize: "14px" }}>
                            Start a new market research project
                        </p>

                        {error && (
                            <div className="error-message" style={{ marginBottom: "20px" }}>
                                {error}
                            </div>
                        )}

                        <form onSubmit={handleSubmit}>
                            <div className="form-group">
                                <label htmlFor="name" style={{ fontSize: "13px" }}>Project Name *</label>
                                <input
                                    id="name"
                                    name="name"
                                    type="text"
                                    value={formData.name}
                                    onChange={handleChange}
                                    placeholder="e.g., FinTech Competitor Analysis"
                                    autoFocus
                                    style={{ fontSize: "14px" }}
                                />
                            </div>

                            <div className="form-group">
                                <label htmlFor="description" style={{ fontSize: "13px" }}>Description (optional)</label>
                                <textarea
                                    id="description"
                                    name="description"
                                    value={formData.description}
                                    onChange={handleChange}
                                    placeholder="Brief description of your research goals..."
                                    rows={3}
                                    style={{ resize: "none", fontSize: "14px" }}
                                />
                            </div>

                            <button
                                type="submit"
                                className="btn-primary"
                                disabled={isSubmitting || !organizationId}
                                style={{ marginTop: "12px", fontSize: "14px" }}
                            >
                                {isSubmitting ? (
                                    <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "8px" }}>
                                        <span className="spinner" style={{ width: "16px", height: "16px", borderWidth: "2px" }}></span>
                                        Creating...
                                    </span>
                                ) : (
                                    "Create Project →"
                                )}
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        </>
    );
}
