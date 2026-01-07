"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";

// Admin emails that can see the admin dashboard link
const ADMIN_EMAILS = ["thehamidrezamafi@gmail.com"];

interface TopBarProps {
    showBackToDashboard?: boolean;
}

export default function TopBar({ showBackToDashboard = false }: TopBarProps) {
    const { user, logout } = useAuth();
    const [theme, setTheme] = useState<"dark" | "light">("dark");
    const [showProfileMenu, setShowProfileMenu] = useState(false);

    // Check if current user is admin
    const isAdmin = user?.email && ADMIN_EMAILS.includes(user.email);

    useEffect(() => {
        // Check for saved theme preference
        const savedTheme = localStorage.getItem("theme") as "dark" | "light" | null;
        if (savedTheme) {
            setTheme(savedTheme);
            document.documentElement.setAttribute("data-theme", savedTheme);
        }
    }, []);

    const toggleTheme = () => {
        const newTheme = theme === "dark" ? "light" : "dark";
        setTheme(newTheme);
        localStorage.setItem("theme", newTheme);
        document.documentElement.setAttribute("data-theme", newTheme);
    };

    const getInitials = () => {
        if (user?.full_name) {
            return user.full_name.split(" ").map((n: string) => n[0]).join("").toUpperCase().slice(0, 2);
        }
        if (user?.username) {
            return user.username.slice(0, 2).toUpperCase();
        }
        return "U";
    };

    return (
        <header className="top-bar">
            <div className="top-bar-left">
                {showBackToDashboard && (
                    <Link href="/dashboard" className="top-bar-back">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M19 12H5M12 19l-7-7 7-7" />
                        </svg>
                    </Link>
                )}
                <Link href="/dashboard" className="top-bar-logo">
                    <span className="logo-icon">M</span>
                    <span className="logo-text">MarketNavigator</span>
                </Link>
            </div>

            <div className="top-bar-right">
                {/* Language Toggle (placeholder) */}
                <button className="top-bar-icon-btn" title="Language">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="10" />
                        <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                    </svg>
                </button>

                {/* Theme Toggle */}
                <button className="top-bar-icon-btn" onClick={toggleTheme} title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}>
                    {theme === "dark" ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <circle cx="12" cy="12" r="5" />
                            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                        </svg>
                    ) : (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                        </svg>
                    )}
                </button>

                {/* Profile */}
                <div className="top-bar-profile">
                    <button
                        className="profile-avatar-btn"
                        onClick={() => setShowProfileMenu(!showProfileMenu)}
                    >
                        {getInitials()}
                    </button>

                    {showProfileMenu && (
                        <div className="profile-dropdown">
                            <div className="profile-dropdown-header">
                                <span className="profile-name">{user?.full_name || user?.username || "User"}</span>
                                <span className="profile-email">{user?.email || ""}</span>
                            </div>
                            <div className="profile-dropdown-divider" />
                            {isAdmin && (
                                <Link href="/admin" className="profile-dropdown-item" style={{ textDecoration: "none", color: "inherit" }}>
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                        <rect x="3" y="3" width="7" height="7" />
                                        <rect x="14" y="3" width="7" height="7" />
                                        <rect x="14" y="14" width="7" height="7" />
                                        <rect x="3" y="14" width="7" height="7" />
                                    </svg>
                                    Admin Dashboard
                                </Link>
                            )}
                            <button className="profile-dropdown-item" onClick={logout}>
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                                    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
                                </svg>
                                Log out
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </header>
    );
}
