"use client";

import React from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ArrowRight, BrainCircuit, Database, Layers, Sparkles } from "lucide-react";

interface FactItem {
  id: string;
  content: string;
  hindsight_memory_id?: string;
  tags?: string[];
  created_at: string;
}

interface HindsightOverviewProps {
  bankId: string;
  totalAvailableMemories: number;
  recentFacts: FactItem[];
  loading?: boolean;
}

export function HindsightOverview({
  bankId,
  totalAvailableMemories,
  recentFacts,
  loading = false,
}: HindsightOverviewProps) {
  if (loading) {
    return (
      <Card className="border border-border/80 shadow-xs animate-pulse">
        <CardHeader>
          <div className="h-4 w-36 bg-muted rounded" />
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="h-16 bg-muted/40 rounded" />
          <div className="h-16 bg-muted/40 rounded" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border border-border/80 shadow-xs">
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <BrainCircuit className="h-4 w-4 text-purple-400" />
            Hindsight Overview
          </CardTitle>
          <CardDescription className="text-xs">
            Organizational memory retention bank & synced facts
          </CardDescription>
        </div>
        <Link
          href="/inspector"
          className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          Inspect
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Memory Bank Info Badge Row */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg border border-border/70 bg-muted/20 p-3 space-y-1">
            <span className="text-[11px] text-muted-foreground">Active Bank ID</span>
            <p className="font-mono text-xs font-semibold text-foreground truncate">
              {bankId || "default"}
            </p>
          </div>
          <div className="rounded-lg border border-border/70 bg-muted/20 p-3 space-y-1">
            <span className="text-[11px] text-muted-foreground">Total Available Memories</span>
            <p className="text-xs font-semibold text-purple-400">
              {totalAvailableMemories} active guideline{totalAvailableMemories !== 1 ? "s" : ""}
            </p>
          </div>
        </div>

        {/* Recent Retained Facts */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">
            Recent Retained Facts ({recentFacts.length})
          </p>
          {recentFacts.length === 0 ? (
            <div className="rounded-lg border border-border/50 p-4 text-center text-xs text-muted-foreground">
              No facts retained in this bank yet. Run <code className="bg-muted px-1 py-0.5 rounded">review-agent learn</code> to store rules.
            </div>
          ) : (
            <div className="space-y-2">
              {recentFacts.map((fact) => (
                <div
                  key={fact.id}
                  className="rounded-lg border border-border/60 bg-muted/20 p-2.5 text-xs space-y-1.5"
                >
                  <p className="font-medium text-foreground/90 leading-relaxed">
                    {fact.content}
                  </p>
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground pt-1 border-t border-border/30">
                    <span className="font-mono">
                      {fact.hindsight_memory_id ? `ID: ${fact.hindsight_memory_id.substring(0, 14)}...` : "Synced in Neon"}
                    </span>
                    <span>{new Date(fact.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

