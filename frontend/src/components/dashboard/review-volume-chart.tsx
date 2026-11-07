"use client";

import React from "react";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Delta, DeltaIcon, DeltaValue } from "@/components/dashboard/delta";

const volumeData = [
  { day: "Mon", reviews: 4, findings: 7 },
  { day: "Tue", reviews: 8, findings: 12 },
  { day: "Wed", reviews: 15, findings: 9 },
  { day: "Thu", reviews: 11, findings: 14 },
  { day: "Fri", reviews: 19, findings: 18 },
  { day: "Sat", reviews: 6, findings: 3 },
  { day: "Sun", reviews: 9, findings: 5 },
];

export function ReviewVolumeChart() {
  return (
    <Card className="border border-border/80 shadow-xs lg:col-span-2">
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <div className="space-y-1">
          <CardTitle className="text-base font-semibold">Review Volume & Findings</CardTitle>
          <CardDescription className="text-xs">
            Daily throughput across CLI checks and web submissions
          </CardDescription>
        </div>
        <Delta value={18.4} variant="badge">
          <DeltaIcon variant="trend" />
          <DeltaValue />
        </Delta>
      </CardHeader>
      <CardContent className="pt-4">
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={volumeData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="reviewGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                </linearGradient>
                <linearGradient id="findingGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#f43f5e" stopOpacity={0.0} />
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
                fill="url(#reviewGrad)"
                name="Reviews"
              />
              <Area
                type="monotone"
                dataKey="findings"
                stroke="#f43f5e"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#findingGrad)"
                name="Findings"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

