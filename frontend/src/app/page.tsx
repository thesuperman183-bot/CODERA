"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { DashboardStats } from "@/components/dashboard/dashboard-stats";
import { ReviewAnalytics } from "@/components/dashboard/review-analytics";
import { RecentActivity } from "@/components/dashboard/recent-activity";
import { HindsightOverview } from "@/components/dashboard/hindsight-overview";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { AlertCircle, Code2, Plus, RefreshCw, Sparkles } from "lucide-react";

interface DashboardData {
  total_reviews: number;
  total_rules: number;
  critical_issues: number;
  retained_memories: number;
  system_status: string;
  groq_model: string;
  hindsight_configured: boolean;
  hindsight_bank_id: string;
  total_available_memories: number;
  recent_retained_facts: any[];
  recent_reviews: any[];
  findings_by_severity: Record<string, number>;
  activity_timeline: any[];
  project_issues: any[];
}

export default function OverviewPage() {
  const { user, activeTeamId, loading: authLoading, login } = useAuth();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [emailInput, setEmailInput] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);

  const fetchDashboardData = async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const stats = await apiClient.dashboard.stats(activeTeamId || undefined);
      setData(stats);
    } catch (err: any) {
      setError(err?.message || "Failed to load dashboard data from backend.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!authLoading) {
      fetchDashboardData();
    }
  }, [authLoading, user, activeTeamId]);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Overview</h1>
            {data?.system_status && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Neon Connected
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Real-time code review telemetry, team intelligence, and Hindsight memory bank.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            onClick={fetchDashboardData}
            disabled={loading}
            className="gap-1.5 text-xs"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <Link href="/review">
            <Button size="sm" className="gap-1.5 text-xs shadow-xs">
              <Code2 className="h-3.5 w-3.5" />
              New Review
            </Button>
          </Link>
          <Link href="/rules">
            <Button size="sm" variant="secondary" className="gap-1.5 text-xs">
              <Plus className="h-3.5 w-3.5" />
              Add Rule
            </Button>
          </Link>
        </div>
      </div>

      {/* Unauthenticated / Sign-in Banner */}
      {!user && !authLoading && (
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4 rounded-xl border border-primary/20 bg-card/60 p-5 text-xs">
          <div className="space-y-1">
            <p className="font-semibold text-sm text-foreground">Sign In to CODERA</p>
            <p className="text-muted-foreground">
              Connect with your developer email to sync reviews, pull requests, and Hindsight memory bank.
            </p>
          </div>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              if (!emailInput.trim()) return;
              setLoggingIn(true);
              try {
                await login(emailInput.trim());
              } catch (err: any) {
                setError(err?.message || "Sign in failed");
              } finally {
                setLoggingIn(false);
              }
            }}
            className="flex items-center gap-2 w-full sm:w-auto"
          >
            <input
              type="email"
              placeholder="developer@example.com"
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              className="rounded-lg border border-border bg-background px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-hidden focus:ring-1 focus:ring-primary"
            />
            <Button size="sm" type="submit" disabled={loggingIn} className="text-xs shrink-0">
              {loggingIn ? "Connecting..." : "Sign In"}
            </Button>
          </form>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-red-300 text-xs">
          <AlertCircle className="h-4 w-4 shrink-0 text-red-400 mt-0.5" />
          <div className="flex-1">
            <p className="font-semibold">Backend Connection Issue</p>
            <p className="mt-0.5 opacity-90">{error}</p>
          </div>
          <Button size="sm" variant="outline" onClick={fetchDashboardData} className="text-xs h-7 px-2">
            Retry
          </Button>
        </div>
      )}

      {/* 1. Statistics Cards */}
      <DashboardStats
        totalReviews={data?.total_reviews ?? 0}
        criticalIssues={data?.critical_issues ?? 0}
        retainedMemories={data?.retained_memories ?? 0}
        activeRules={data?.total_rules ?? 0}
        loading={loading}
      />

      {/* 2. Review Analytics Section (Activity Over Time, Severity Breakdown, Project Issues) */}
      <ReviewAnalytics
        timeline={data?.activity_timeline ?? []}
        severityData={data?.findings_by_severity ?? {}}
        projectIssues={data?.project_issues ?? []}
        loading={loading}
      />

      {/* 3. Recent Activity & Hindsight Overview Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <RecentActivity
          reviews={data?.recent_reviews ?? []}
          loading={loading}
        />
        <HindsightOverview
          bankId={data?.hindsight_bank_id ?? "default"}
          totalAvailableMemories={data?.total_available_memories ?? 0}
          recentFacts={data?.recent_retained_facts ?? []}
          loading={loading}
        />
      </div>
    </div>
  );
}
