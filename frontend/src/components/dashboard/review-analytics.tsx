"use client";

import React from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, AlertTriangle, FileCode, PieChart as PieIcon } from "lucide-react";

interface ReviewAnalyticsProps {
  timeline: Array<{ day: string; reviews: number }>;
  severityData: Record<string, number>;
  projectIssues: Array<{ project_or_file: string; issues: number; criticals: number }>;
  loading?: boolean;
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#f43f5e",
  high: "#fb923c",
  medium: "#facc15",
  low: "#38bdf8",
  info: "#a3e635",
};

export function ReviewAnalytics({
  timeline,
  severityData,
  projectIssues,
  loading = false,
}: ReviewAnalyticsProps) {
  const pieData = Object.entries(severityData).map(([name, value]) => ({
    name: name.toUpperCase(),
    value,
    color: SEVERITY_COLORS[name.toLowerCase()] || "#94a3b8",
  }));

  const totalFindings = Object.values(severityData).reduce((a, b) => a + b, 0);

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3 animate-pulse">
        <div className="h-72 bg-muted/40 rounded-xl lg:col-span-2" />
        <div className="h-72 bg-muted/40 rounded-xl" />
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      {/* 1. Review Activity Over Time */}
      <Card className="border border-border/80 shadow-xs lg:col-span-2">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Activity className="h-4 w-4 text-primary" />
              Review Activity Over Time
            </CardTitle>
            <CardDescription className="text-xs">
              Daily code review throughput verified in Neon PostgreSQL
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          {timeline.length === 0 ? (
            <div className="flex h-56 flex-col items-center justify-center text-center text-muted-foreground text-xs">
              <Activity className="h-8 w-8 stroke-1 mb-2 opacity-30" />
              No timeline data yet. Run code reviews to plot activity.
            </div>
          ) : (
            <div className="h-56 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={timeline} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="reviewsGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="day" stroke="#888888" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="#888888" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      borderColor: "hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "12px",
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="reviews"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    fillOpacity={1}
                    fill="url(#reviewsGrad)"
                    name="Reviews"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 2. Findings Grouped by Severity */}
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <div>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <PieIcon className="h-4 w-4 text-primary" />
              Findings by Severity
            </CardTitle>
            <CardDescription className="text-xs">
              Distribution of issues detected ({totalFindings} total)
            </CardDescription>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          {pieData.length === 0 ? (
            <div className="flex h-56 flex-col items-center justify-center text-center text-muted-foreground text-xs">
              <AlertTriangle className="h-8 w-8 stroke-1 mb-2 opacity-30" />
              No findings recorded in system.
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <div className="h-44 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={70}
                      paddingAngle={3}
                    >
                      {pieData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        borderColor: "hsl(var(--border))",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex flex-wrap justify-center gap-2 pt-2 text-[11px]">
                {pieData.map((d) => (
                  <div key={d.name} className="flex items-center gap-1.5">
                    <span
                      className="h-2 w-2 rounded-full"
                      style={{ backgroundColor: d.color }}
                    />
                    <span className="text-muted-foreground">{d.name}:</span>
                    <span className="font-semibold">{d.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 3. Issues Detected Across Projects & Files */}
      {projectIssues.length > 0 && (
        <Card className="border border-border/80 shadow-xs lg:col-span-3">
          <CardHeader>
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <FileCode className="h-4 w-4 text-primary" />
              Issues Detected Across Projects & Files
            </CardTitle>
            <CardDescription className="text-xs">
              Top impacted files identified across reviews
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="divide-y divide-border">
              {projectIssues.map((p, idx) => (
                <div key={idx} className="flex items-center justify-between p-3.5 text-xs">
                  <div className="flex items-center gap-2 overflow-hidden">
                    <FileCode className="h-4 w-4 text-muted-foreground shrink-0" />
                    <span className="font-mono truncate">{p.project_or_file}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="secondary" className="text-[10px]">
                      {p.issues} issue{p.issues > 1 ? "s" : ""}
                    </Badge>
                    {p.criticals > 0 && (
                      <Badge variant="destructive" className="text-[10px]">
                        {p.criticals} critical
                      </Badge>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

