"use client";

import React from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ArrowRight, CheckCircle2, Clock, Globe, Terminal, XCircle } from "lucide-react";

interface ReviewItem {
  id: string;
  source: string;
  status: string;
  model_used: string;
  findings_count: number;
  critical_count?: number;
  created_at: string;
}

interface RecentActivityProps {
  reviews: ReviewItem[];
  loading?: boolean;
}

export function RecentActivity({ reviews, loading = false }: RecentActivityProps) {
  if (loading) {
    return (
      <Card className="border border-border/80 shadow-xs">
        <CardHeader>
          <div className="h-4 w-32 bg-muted rounded animate-pulse" />
        </CardHeader>
        <CardContent className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-10 bg-muted/40 rounded animate-pulse" />
          ))}
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border border-border/80 shadow-xs">
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div>
          <CardTitle className="text-base font-semibold">Recent Activity</CardTitle>
          <CardDescription className="text-xs">
            Latest code reviews triggered via CLI or Web
          </CardDescription>
        </div>
        <Link
          href="/history"
          className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          View all
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </CardHeader>
      <CardContent className="p-0">
        {reviews.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground">
            <Clock className="h-8 w-8 stroke-1 mb-2 opacity-40" />
            <p className="text-xs font-medium">No reviews logged yet</p>
            <p className="text-[11px] text-muted-foreground/80 mt-1">
              Run <code className="bg-muted px-1 py-0.5 rounded">review-agent check</code> from terminal or submit via Web.
            </p>
          </div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="w-[120px] text-xs">Review ID</TableHead>
                <TableHead className="text-xs">Source</TableHead>
                <TableHead className="text-xs">Status</TableHead>
                <TableHead className="text-xs">Findings</TableHead>
                <TableHead className="text-right text-xs">Timestamp</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {reviews.map((r) => (
                <TableRow key={r.id}>
                  <TableCell className="font-mono text-xs text-muted-foreground truncate max-w-[120px]">
                    {r.id.substring(0, 10)}...
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="gap-1 text-[10px] font-normal">
                      {r.source === "CLI" ? (
                        <Terminal className="h-3 w-3 text-emerald-400" />
                      ) : (
                        <Globe className="h-3 w-3 text-blue-400" />
                      )}
                      {r.source || "CLI"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                      <CheckCircle2 className="h-3.5 w-3.5" />
                      {r.status}
                    </span>
                  </TableCell>
                  <TableCell>
                    {r.findings_count > 0 ? (
                      <div className="flex items-center gap-1">
                        <Badge variant="secondary" className="text-[10px] py-0 px-1.5 font-medium">
                          {r.findings_count} total
                        </Badge>
                        {(r.critical_count ?? 0) > 0 && (
                          <Badge variant="destructive" className="text-[10px] py-0 px-1.5 font-medium">
                            {r.critical_count} critical
                          </Badge>
                        )}
                      </div>
                    ) : (
                      <span className="text-xs text-muted-foreground">Clean</span>
                    )}
                  </TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground font-mono">
                    {new Date(r.created_at).toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                      month: "short",
                      day: "numeric",
                    })}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}

