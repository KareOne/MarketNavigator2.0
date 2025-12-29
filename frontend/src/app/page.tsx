"use client";

import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import { useRouter } from "next/navigation";

export default function Home() {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  // Redirect to dashboard if authenticated
  if (!isLoading && isAuthenticated) {
    router.push("/dashboard");
    return null;
  }

  return (
    <div style={{ minHeight: "100vh" }}>
      {/* Navbar */}
      <nav className="navbar">
        <div className="navbar-content">
          <h2>MarketNavigator</h2>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <Link href="/login" style={{ color: "var(--color-text-muted)", fontWeight: 500 }}>
              Login
            </Link>
            <Link
              href="/register"
              className="btn-new-project"
              style={{ padding: "10px 24px" }}
            >
              Get Started
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <div style={{
        maxWidth: "900px",
        margin: "0 auto",
        padding: "80px 20px",
        textAlign: "center"
      }}>
        <h1 style={{
          fontSize: "48px",
          fontWeight: 700,
          color: "var(--color-heading)",
          marginBottom: "20px",
          lineHeight: 1.2
        }}>
          AI-Powered Market Research
          <br />
          <span style={{
            background: "var(--gradient-primary)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent"
          }}>
            For Entrepreneurs
          </span>
        </h1>
        <p style={{
          fontSize: "18px",
          color: "var(--color-text-muted)",
          maxWidth: "600px",
          margin: "0 auto 40px",
          lineHeight: 1.6
        }}>
          Analyze competitors, track social presence, and generate pitch decks
          with our intelligent research platform designed for startups.
        </p>
        <div style={{ display: "flex", gap: "16px", justifyContent: "center" }}>
          <Link href="/register" className="btn-new-project" style={{ padding: "14px 32px", fontSize: "16px" }}>
            Start Free Trial
          </Link>
          <Link
            href="#features"
            style={{
              padding: "14px 32px",
              border: "1px solid var(--color-border)",
              borderRadius: "var(--radius-sm)",
              color: "var(--color-text)",
              fontWeight: 600,
              fontSize: "16px",
              transition: "all 0.2s ease"
            }}
          >
            Learn More
          </Link>
        </div>
      </div>

      {/* Features */}
      <div id="features" style={{
        maxWidth: "1100px",
        margin: "0 auto",
        padding: "40px 20px 80px"
      }}>
        <div className="projects-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(250px, 1fr))" }}>
          <FeatureCard icon="🔍" title="Crunchbase Analysis" description="Find competitors, funding data, and market insights." />
          <FeatureCard icon="📊" title="Tracxn Research" description="Analyze startup landscape and sector trends." />
          <FeatureCard icon="📱" title="Social Analysis" description="Track brand mentions on Twitter and LinkedIn." />
          <FeatureCard icon="🎯" title="Pitch Deck" description="Auto-generate pitch decks from research data." />
        </div>
      </div>
    </div>
  );
}

function FeatureCard({ icon, title, description }: { icon: string; title: string; description: string }) {
  return (
    <div className="project-card" style={{ cursor: "default" }}>
      <div style={{ fontSize: "32px", marginBottom: "12px" }}>{icon}</div>
      <h3 style={{ marginBottom: "8px" }}>{title}</h3>
      <p className="project-description" style={{ marginBottom: 0 }}>{description}</p>
    </div>
  );
}
