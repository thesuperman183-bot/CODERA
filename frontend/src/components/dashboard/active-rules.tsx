"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { ArrowRight, Brain, Sparkles } from "lucide-react";

interface TeamRuleItem {
  id: string;
  rule_text: string;
  created_at: string;
}

export function ActiveRulesWidget() {
  const { activeTeamId } = useAuth();
  const [rules, setRules] = useState<TeamRuleItem[]>([]);

  useEffect(() => {
    async function loadRules() {
      try {
        const data = await apiClient.teamRules.list(activeTeamId || undefined);
        if (Array.isArray(data)) {
          setRules(data.slice(0, 4));
        }
      } catch {
        // Fallback demo rules
        setRules([
          {
            id: "r1",
            rule_text: "Always parameterize SQL queries to prevent injection attacks",
            created_at: new Date().toISOString(),
          },
          {
            id: "r2",
            rule_text: "Enforce HTTPS and validate external API response schemas",
            created_at: new Date().toISOString(),
          },
          {
            id: "r3",
            rule_text: "Never log plaintext passwords, access tokens, or sensitive user PII",
            created_at: new Date().toISOString(),
          },
        ]);
      }
    }
    loadRules();
  }, [activeTeamId]);

  return (
    <Card className="border border-border/80 shadow-xs">
      <CardHeader className="flex flex-row items-center justify-between pb-3">
        <div>
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Brain className="h-4 w-4 text-primary" />
            Hindsight Active Rules
          </CardTitle>
          <CardDescription className="text-xs">
            Organizational memory recalled for every code review
          </CardDescription>
        </div>
        <Link
          href="/rules"
          className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
        >
          Manage
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      </CardHeader>
      <CardContent className="space-y-3">
        {rules.map((rule, idx) => (
          <div
            key={rule.id || idx}
            className="flex items-start gap-2.5 rounded-lg border border-border/60 bg-muted/30 p-2.5 text-xs"
          >
            <Sparkles className="h-3.5 w-3.5 text-amber-500 shrink-0 mt-0.5" />
            <p className="line-clamp-2 text-foreground/90 font-medium leading-relaxed">
              {rule.rule_text}
            </p>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

