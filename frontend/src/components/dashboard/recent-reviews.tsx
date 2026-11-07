"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiClient } from "@/lib/api";
import { ArrowRight, CheckCircle, Clock, ShieldAlert } from "lucide-react";

interface ReviewSummary {
  id: string;
  source: string;
  status: string;
  model_used: string;
  findings_count: number;
  created_at: string;
}

export function RecentReviewsTable() {
  const [reviews, setReviews] = useState<ReviewSummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchReviews() {
      try {
        const data = await apiClient.reviews.list(5);
        if (Array.isArray(data)) {
          setReviews(data);
        }
      } catch {
        // Fallback demo items
        setReviews([
          {
            id: "rev-8f92a10d-demo",
            source: "CLI",
            status: "completed",
            model_used: "qwen-2.5-32b",
            findings_count: 2,
            created_at: new Date().toISOString(),
          },
          {
            id: "rev-3b7c8e9f-demo",
            source: "Web",
            status: "completed",
            model_used: "qwen-2.5-32b",
            findings_count: 0,
            created_at: new Date(Date.now() - 3600000).toISOString(),
          },
        ]);
      } finally {
        setLoading(false);
      }
    }
    fetchReviews();
  }, []);

  return (
    <Card className="border border-border/80 shadow-xs">
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div>
          <CardTitle className="text-base font-semibold">Recent Code Reviews</CardTitle>
          <CardDescription className="text-xs">
            Review sessions ingested through CLI and Web
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
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-[120px] text-xs">Review ID</TableHead>
              <TableHead className="text-xs">Source</TableHead>
              <TableHead className="text-xs">Status</TableHead>
              <TableHead className="text-xs">Findings</TableHead>
              <TableHead className="text-right text-xs">Date</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {reviews.map((r) => (
              <TableRow key={r.id}>
                <TableCell className="font-mono text-xs text-muted-foreground truncate max-w-[120px]">
                  {r.id.substring(0, 12)}...
                </TableCell>
                <TableCell>
                  <Badge variant="outline" className="text-[11px] font-normal">
                    {r.source || "CLI"}
                  </Badge>
                </TableCell>
                <TableCell>
                  <span className="inline-flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
                    <CheckCircle className="h-3.5 w-3.5" />
                    {r.status}
                  </span>
                </TableCell>
                <TableCell>
                  {r.findings_count > 0 ? (
                    <Badge variant="destructive" className="text-[10px] py-0 px-1.5 font-medium">
                      {r.findings_count} finding{r.findings_count > 1 ? "s" : ""}
                    </Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">Clean</span>
                  )}
                </TableCell>
                <TableCell className="text-right text-xs text-muted-foreground">
                  {new Date(r.created_at).toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

