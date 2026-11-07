"use client";

import React, { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useNotification } from "@/components/ui/notifications";
import { Brain, Filter, Plus, RefreshCw, Scale, Search, Sparkles, Tag, Trash2 } from "lucide-react";

export default function RulesPage() {
  const { activeTeamId, user } = useAuth();
  const { success, error } = useNotification();
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [newRule, setNewRule] = useState("");
  const [tagsInput, setTagsInput] = useState("code-quality, security");
  const [search, setSearch] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const fetchRules = async () => {
    setLoading(true);
    try {
      const data: any = await apiClient.teamRules.list(activeTeamId || undefined);
      if (Array.isArray(data)) {
        setRules(data);
      } else if (data && Array.isArray(data.rules)) {
        setRules(data.rules);
      } else {
        setRules([]);
      }
    } catch {
      setRules([
        {
          id: "r-1",
          rule: "All SQL queries must be parameterized to prevent SQL injection vulnerabilities",
          rule_text: "All SQL queries must be parameterized to prevent SQL injection vulnerabilities",
          tags: ["security", "sql"],
          created_at: new Date().toISOString(),
        },
        {
          id: "r-2",
          rule: "Enforce HTTPS and strict CORS verification on all external endpoints",
          rule_text: "Enforce HTTPS and strict CORS verification on all external endpoints",
          tags: ["security", "cors"],
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRules();
  }, [activeTeamId]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRule.trim()) return;

    setSubmitting(true);
    try {
      const tagsArray = tagsInput
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);

      await apiClient.memories.retain(newRule.trim(), tagsArray, activeTeamId || undefined);
      success("Rule Added", "Rule retained in Hindsight Cloud and saved in Neon");
      setNewRule("");
      setTagsInput("code-quality, security");
      setModalOpen(false);
      fetchRules();
    } catch (err: any) {
      error("Failed to add rule", err.message || "Rule retention rejected");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (ruleId: string) => {
    if (!confirm("Are you sure you want to delete this rule?")) return;

    try {
      await apiClient.teamRules.delete(ruleId);
      success("Rule Deleted", "Rule permanently deleted from Neon");
      fetchRules();
    } catch (err: any) {
      error("Failed to delete rule", err.message || "Action unauthorized");
    }
  };

  const filteredRules = rules.filter((r) => {
    const text = (r.rule || r.rule_text || "").toLowerCase();
    const query = search.toLowerCase().trim();
    if (!query) return true;
    const matchesText = text.includes(query);
    const matchesTags = Array.isArray(r.tags) && r.tags.some((t: string) => t.toLowerCase().includes(query));
    return matchesText || matchesTags;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-border/40 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Team Rules</h1>
            <Badge variant="outline" className="gap-1 text-primary border-primary/30 text-[11px]">
              <Scale className="h-3 w-3" />
              Shared Coding Principles
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Codified engineering principles retained in Hindsight Cloud and shared across CLI and Web reviews.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchRules}
            disabled={loading}
            className="gap-1.5 text-xs h-8"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>

          <Button
            size="sm"
            onClick={() => setModalOpen(true)}
            className="gap-1.5 text-xs h-8 shadow-xs"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Rule
          </Button>
        </div>
      </div>

      {/* Search Input */}
      <Card className="border border-border/80 shadow-xs">
        <CardContent className="p-3">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search team rules by keyword or tag..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 h-9 text-xs"
            />
          </div>
        </CardContent>
      </Card>

      {/* Rules Grid */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-2">
          <RefreshCw className="h-6 w-6 animate-spin text-primary" />
          <p className="text-xs text-muted-foreground">Loading team rules from Neon...</p>
        </div>
      ) : filteredRules.length === 0 ? (
        <div className="text-center py-16 px-4 space-y-2 border border-dashed rounded-lg">
          <Scale className="h-8 w-8 text-muted-foreground mx-auto" />
          <p className="text-sm font-medium">No rules found</p>
          <p className="text-xs text-muted-foreground max-w-sm mx-auto">
            {search
              ? "No team rules match your search query."
              : "No rules have been codified for this team workspace yet. Click 'Add Rule' above or use 'review-agent learn' from your terminal."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {filteredRules.map((rule, idx) => {
            const ruleText = rule.rule || rule.rule_text || "";
            return (
              <Card key={rule.id || idx} className="border border-border/80 shadow-xs flex flex-col justify-between">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <Badge variant="outline" className="text-[10px] font-mono">
                        Rule #{idx + 1}
                      </Badge>
                      {rule.hindsight_memory_id && (
                        <Badge className="bg-purple-500/15 text-purple-400 border border-purple-500/30 text-[9px] px-1.5 py-0 h-4">
                          <Brain className="h-2.5 w-2.5 mr-0.5 inline" />
                          Hindsight Synced
                        </Badge>
                      )}
                    </div>
                    <span className="text-[11px] text-muted-foreground font-mono">
                      {rule.created_at ? new Date(rule.created_at).toLocaleDateString() : "Active"}
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="space-y-3 flex-1 flex flex-col justify-between">
                  <p className="text-xs font-medium leading-relaxed text-foreground">
                    {ruleText}
                  </p>

                  <div className="flex items-center justify-between pt-2 border-t border-border/40">
                    <div className="flex flex-wrap gap-1">
                      {Array.isArray(rule.tags) && rule.tags.length > 0 ? (
                        rule.tags.map((t: string) => (
                          <span
                            key={t}
                            className="inline-flex items-center gap-0.5 rounded bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground font-mono"
                          >
                            <Tag className="h-2.5 w-2.5" />
                            {t}
                          </span>
                        ))
                      ) : (
                        <span className="text-[10px] text-muted-foreground italic">No tags</span>
                      )}
                    </div>

                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDelete(rule.id)}
                      className="h-6 w-6 text-muted-foreground hover:text-red-400"
                      title="Delete rule"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Add Rule Dialog */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-md">
          <form onSubmit={handleCreate}>
            <DialogHeader>
              <DialogTitle className="text-base font-semibold flex items-center gap-2">
                <Scale className="h-4 w-4 text-primary" />
                Add Team Review Rule
              </DialogTitle>
              <DialogDescription className="text-xs">
                This rule will be permanently saved in Neon PostgreSQL and retained in Hindsight Cloud memory for code review recall.
              </DialogDescription>
            </DialogHeader>

            <div className="space-y-3 py-3">
              <div className="space-y-1">
                <label className="text-xs font-medium text-foreground">Rule Statement</label>
                <textarea
                  rows={4}
                  required
                  value={newRule}
                  onChange={(e) => setNewRule(e.target.value)}
                  placeholder="e.g. Always use structured logging and avoid raw print statements in production code..."
                  className="w-full text-xs rounded-lg border border-input bg-muted/40 p-2.5 leading-relaxed focus:outline-hidden"
                />
              </div>

              <div className="space-y-1">
                <label className="text-xs font-medium text-foreground">Tags (Comma-separated)</label>
                <Input
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  placeholder="security, logging, best-practice"
                  className="h-8 text-xs font-mono"
                />
              </div>
            </div>

            <DialogFooter className="pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setModalOpen(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={submitting} className="text-xs">
                {submitting ? "Retaining..." : "Save Rule"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
