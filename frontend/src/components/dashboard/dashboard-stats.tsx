"use client";

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Delta, DeltaIcon, DeltaValue } from "@/components/dashboard/delta";
import { CheckCircle2, Clock, FileCode, ShieldAlert } from "lucide-react";

interface StatsProps {
  totalReviews: number;
  criticalIssues: number;
  retainedMemories: number;
  activeRules: number;
  loading?: boolean;
}

export function DashboardStats({
  totalReviews,
  criticalIssues,
  retainedMemories,
  activeRules,
  loading = false,
}: StatsProps) {
  const statCards = [
    {
      label: "Total Reviews",
      value: totalReviews,
      delta: totalReviews > 0 ? 12.5 : 0,
      footnote: "via CLI & Web",
      icon: FileCode,
      color: "text-blue-500",
    },
    {
      label: "Critical Issues",
      value: criticalIssues,
      delta: criticalIssues > 0 ? -8.4 : 0,
      footnote: "identified by Groq",
      icon: ShieldAlert,
      color: criticalIssues > 0 ? "text-rose-500" : "text-emerald-500",
    },
    {
      label: "Retained Memories",
      value: retainedMemories,
      delta: retainedMemories > 0 ? 15.0 : 0,
      footnote: "facts stored in Hindsight",
      icon: CheckCircle2,
      color: "text-amber-500",
    },
    {
      label: "Active Team Rules",
      value: activeRules,
      delta: activeRules > 0 ? 5.2 : 0,
      footnote: "recalled per review",
      icon: Clock,
      color: "text-purple-500",
    },
  ];

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="border border-border/80 shadow-xs animate-pulse">
            <CardHeader className="pb-2">
              <div className="h-3 w-24 bg-muted rounded" />
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="h-8 w-16 bg-muted rounded" />
              <div className="h-3 w-32 bg-muted rounded" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {statCards.map((s) => {
        const Icon = s.icon;
        return (
          <Card key={s.label} className="border border-border/80 shadow-xs transition-shadow hover:shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-xs font-medium text-muted-foreground">
                {s.label}
              </CardTitle>
              <Icon className={`h-4 w-4 ${s.color}`} />
            </CardHeader>
            <CardContent className="flex flex-col gap-1.5">
              <p className="text-2xl font-bold tabular-nums tracking-tight">
                {s.value}
              </p>
              <div className="flex items-center gap-1.5 text-xs">
                {s.delta !== 0 ? (
                  <Delta value={s.delta}>
                    <DeltaIcon variant="trend" />
                    <DeltaValue />
                  </Delta>
                ) : (
                  <span className="text-[11px] text-muted-foreground font-mono">Synced</span>
                )}
                <span className="text-muted-foreground text-[11px]">
                  {s.footnote}
                </span>
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}
