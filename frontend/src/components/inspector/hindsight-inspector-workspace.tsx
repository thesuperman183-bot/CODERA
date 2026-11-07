"use client";

import React, { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useNotification } from "@/components/ui/notifications";
import {
  AlertCircle,
  ArrowRight,
  BookOpen,
  Bot,
  Brain,
  BrainCircuit,
  CheckCircle2,
  Clock,
  Code2,
  Database,
  ExternalLink,
  History,
  Layers,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Shield,
  Sparkles,
  Tag,
  Users,
} from "lucide-react";

interface ActiveBank {
  bank_id: string;
  team_id?: string;
  team_name?: string;
  bank_type: string;
  status: string;
  is_active: boolean;
  total_facts: number;
  total_rules: number;
  total_available_memories: number;
}

interface RetainedFact {
  id: string;
  memory_id?: string;
  content: string;
  tags: string[];
  created_at: string;
  team_id?: string;
}

interface SearchResult {
  text: string;
  relevance_rank: number;
  source_type: string;
  metadata?: any;
}

interface ReviewOption {
  id: string;
  source: string;
  status: string;
  model_used: string;
  created_at: string;
  findings_count: number;
  memories_count: number;
}

interface InjectedMemory {
  id: string;
  memory_text: string;
  hindsight_memory_id?: string;
  source_type: string;
  bank_id?: string;
}

export function HindsightInspectorWorkspace() {
  const { activeTeamId, user } = useAuth();
  const { success, error } = useNotification();

  // 1. Active Bank State
  const [bank, setBank] = useState<ActiveBank | null>(null);
  const [bankLoading, setBankLoading] = useState(true);

  // 2. Retained Facts State
  const [facts, setFacts] = useState<RetainedFact[]>([]);
  const [factsLoading, setFactsLoading] = useState(true);

  // 3. Memory Search State
  const [searchQuery, setSearchQuery] = useState("SQL injection vulnerability prevention");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);

  // 4. Add Team Rule State
  const [newRuleText, setNewRuleText] = useState("");
  const [ruleTags, setRuleTags] = useState("security, code-quality");
  const [addingRule, setAddingRule] = useState(false);

  // 5. Review Memory Inspector State
  const [recentReviews, setRecentReviews] = useState<ReviewOption[]>([]);
  const [selectedReviewId, setSelectedReviewId] = useState<string>("");
  const [injectedMemories, setInjectedMemories] = useState<InjectedMemory[]>([]);
  const [traceLoading, setTraceLoading] = useState(false);

  const fetchBankInfo = async () => {
    setBankLoading(true);
    try {
      const data = await apiClient.memories.activeBank(activeTeamId || undefined);
      setBank(data);
    } catch {
      setBank({
        bank_id: "default",
        bank_type: "team",
        status: "active",
        is_active: true,
        total_facts: 0,
        total_rules: 0,
        total_available_memories: 0,
      });
    } finally {
      setBankLoading(false);
    }
  };

  const fetchFacts = async () => {
    setFactsLoading(true);
    try {
      const data = await apiClient.memories.facts(activeTeamId || undefined, 50);
      setFacts(data || []);
    } catch {
      setFacts([]);
    } finally {
      setFactsLoading(false);
    }
  };

  const fetchRecentReviews = async () => {
    try {
      const list = await apiClient.reviews.list(15);
      if (Array.isArray(list)) {
        setRecentReviews(list);
        if (list.length > 0 && !selectedReviewId) {
          handleSelectReview(list[0].id);
        }
      }
    } catch {
      // Ignored
    }
  };

  useEffect(() => {
    fetchBankInfo();
    fetchFacts();
    fetchRecentReviews();
  }, [activeTeamId]);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setSearching(true);
    try {
      const res = await apiClient.memories.search(searchQuery.trim(), 5, activeTeamId || undefined);
      setSearchResults(res.results || []);
      success("Memory Search Completed", `Retrieved ${res.count || 0} memory candidates from Hindsight`);
    } catch (err: any) {
      error("Memory Search Failed", err.message || "Failed to query Hindsight");
    } finally {
      setSearching(false);
    }
  };

  const handleAddRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRuleText.trim()) return;

    setAddingRule(true);
    try {
      const tagsArray = ruleTags
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);

      const res = await apiClient.memories.retain(newRuleText.trim(), tagsArray, activeTeamId || undefined);
      success(
        "Rule Saved & Retained",
        `Confirmed in Neon and Hindsight (Memory ID: ${res.memory_id?.substring(0, 10)}...)`
      );
      setNewRuleText("");
      // Refresh memory telemetry and facts list
      fetchBankInfo();
      fetchFacts();
    } catch (err: any) {
      error("Failed to Retain Rule", err.message || "Rule retention error");
    } finally {
      setAddingRule(false);
    }
  };

  const handleSelectReview = async (reviewId: string) => {
    setSelectedReviewId(reviewId);
    if (!reviewId) {
      setInjectedMemories([]);
      return;
    }
    setTraceLoading(true);
    try {
      const trace = await apiClient.memories.reviewTrace(reviewId);
      setInjectedMemories(trace.injected_memories || []);
    } catch {
      setInjectedMemories([]);
    } finally {
      setTraceLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-border/40 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Hindsight Inspector</h1>
            <Badge variant="outline" className="gap-1 text-purple-400 border-purple-500/30 text-[11px]">
              <BrainCircuit className="h-3 w-3" />
              Vector Memory Transparency
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Audit the agent's long-term memory banks, search vector recall candidates, manage rules, and trace memories injected into code reviews.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            fetchBankInfo();
            fetchFacts();
          }}
          className="gap-1.5 text-xs h-8"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh Bank
        </Button>
      </div>

      {/* 1. Active Bank Metadata Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="border border-border/80 shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Active Bank ID</CardTitle>
            <Brain className="h-4 w-4 text-purple-400" />
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="font-mono text-base font-bold truncate">
              {bankLoading ? "Loading..." : bank?.bank_id || "default"}
            </p>
            <p className="text-[11px] text-muted-foreground capitalize">
              Type: {bank?.bank_type || "team"} bank
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border/80 shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Associated Team</CardTitle>
            <Users className="h-4 w-4 text-blue-400" />
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-base font-bold truncate">
              {bank?.team_name || "Personal Workspace"}
            </p>
            <p className="text-[11px] text-muted-foreground font-mono truncate">
              ID: {bank?.team_id ? bank.team_id.substring(0, 14) + "..." : "default"}
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border/80 shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Bank Status</CardTitle>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </CardHeader>
          <CardContent className="space-y-1">
            <div className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
              <p className="text-base font-bold capitalize text-emerald-500">
                {bank?.status || "Active"}
              </p>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Hindsight Cloud connected
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border/80 shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Total Available Memories</CardTitle>
            <Sparkles className="h-4 w-4 text-amber-400" />
          </CardHeader>
          <CardContent className="space-y-1">
            <p className="text-base font-bold tabular-nums">
              {bank?.total_available_memories || 0}
            </p>
            <p className="text-[11px] text-muted-foreground">
              {bank?.total_facts || 0} facts + {bank?.total_rules || 0} rules
            </p>
          </CardContent>
        </Card>
      </div>

      {/* 2-Column Grid: Memory Search & Add Team Rule */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Memory Search */}
        <Card className="border border-border/80 shadow-xs flex flex-col">
          <CardHeader className="pb-3 border-b border-border/40">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Search className="h-4 w-4 text-primary" />
              Memory Search
            </CardTitle>
            <CardDescription className="text-xs">
              Query vector recall candidates in real time directly from the active Hindsight bank.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col pt-4 space-y-4">
            <form onSubmit={handleSearch} className="flex gap-2">
              <Input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Enter query (e.g. SQL injection, password hashing, CORS)..."
                required
                className="text-xs flex-1"
              />
              <Button type="submit" disabled={searching || !searchQuery.trim()} className="h-9 px-4 text-xs gap-1.5 shrink-0 shadow-xs">
                {searching ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                Search
              </Button>
            </form>

            <div className="flex-1 space-y-2.5 max-h-80 overflow-y-auto pr-1">
              {searching ? (
                <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                  <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
                  Querying vector bank...
                </div>
              ) : searchResults.length === 0 ? (
                <div className="p-8 text-center text-xs text-muted-foreground">
                  Enter a query above to inspect semantic memory matches.
                </div>
              ) : (
                searchResults.map((r) => (
                  <div
                    key={r.relevance_rank}
                    className="rounded-lg border border-purple-500/20 bg-purple-950/10 p-3 text-xs space-y-1.5"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-purple-400 text-[11px]">
                        Rank #{r.relevance_rank}
                      </span>
                      <Badge variant="outline" className="text-[10px] font-mono">
                        Bank: {r.metadata?.bank_id || "default"}
                      </Badge>
                    </div>
                    <p className="font-medium text-foreground leading-relaxed">
                      {r.text}
                    </p>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Add Team Rule */}
        <Card className="border border-border/80 shadow-xs flex flex-col">
          <CardHeader className="pb-3 border-b border-border/40">
            <CardTitle className="text-base font-semibold flex items-center gap-2">
              <Plus className="h-4 w-4 text-primary" />
              Add Team Rule
            </CardTitle>
            <CardDescription className="text-xs">
              Codify an organizational guideline. The rule is saved in Neon and retained in Hindsight Cloud.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col pt-4">
            <form onSubmit={handleAddRule} className="space-y-4 flex-1 flex flex-col justify-between">
              <div className="space-y-3">
                <div>
                  <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                    Rule Text or Guideline
                  </label>
                  <textarea
                    rows={4}
                    value={newRuleText}
                    onChange={(e) => setNewRuleText(e.target.value)}
                    placeholder="e.g. All database queries must use prepared statements to prevent SQL injection..."
                    required
                    className="w-full text-xs rounded-lg border border-input bg-card p-3 leading-relaxed focus:outline-none focus:ring-1 focus:ring-ring"
                  />
                </div>

                <div>
                  <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                    Tags (comma-separated)
                  </label>
                  <Input
                    value={ruleTags}
                    onChange={(e) => setRuleTags(e.target.value)}
                    placeholder="security, sql, owasp"
                    className="text-xs"
                  />
                </div>
              </div>

              <div className="pt-2 border-t border-border/40 flex items-center justify-between">
                <span className="text-[11px] text-muted-foreground">
                  Synchronized with active team bank
                </span>
                <Button type="submit" disabled={addingRule || !newRuleText.trim()} className="gap-1.5 text-xs h-8 px-4 shadow-xs">
                  {addingRule ? (
                    <>
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Retaining in Hindsight...
                    </>
                  ) : (
                    <>
                      <Plus className="h-3.5 w-3.5" />
                      Add Team Rule
                    </>
                  )}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>

      {/* 3. Review Memory Inspector: Injected Memories Trace */}
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="pb-3 border-b border-border/40">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <BrainCircuit className="h-4 w-4 text-purple-400" />
                Review Memory Inspector
              </CardTitle>
              <CardDescription className="text-xs">
                Inspect which specific Hindsight memories and team rules were injected into a selected code review session.
              </CardDescription>
            </div>

            {/* Select Review Session */}
            <div className="flex items-center gap-2">
              <span className="text-[11px] text-muted-foreground shrink-0">Select Review:</span>
              <select
                value={selectedReviewId}
                onChange={(e) => handleSelectReview(e.target.value)}
                className="text-xs rounded-lg border border-input bg-card p-1.5 font-mono max-w-xs truncate"
              >
                {recentReviews.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.id.substring(0, 10)}... ({r.source} - {new Date(r.created_at).toLocaleDateString()})
                  </option>
                ))}
              </select>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          {traceLoading ? (
            <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
              Loading injected memory trace...
            </div>
          ) : injectedMemories.length === 0 ? (
            <div className="p-8 text-center text-xs text-muted-foreground">
              No memories were recorded for this review session.
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground">
                Injected Guidance Memories ({injectedMemories.length})
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {injectedMemories.map((m) => (
                  <div
                    key={m.id}
                    className="rounded-lg border border-border/70 bg-card p-3 text-xs space-y-2 transition-shadow hover:shadow-xs"
                  >
                    <div className="flex items-center justify-between">
                      <Badge
                        variant={m.source_type === "team_rule" ? "secondary" : "default"}
                        className="text-[10px] capitalize"
                      >
                        {m.source_type === "team_rule" ? "Team Rule" : "Hindsight Semantic Recall"}
                      </Badge>
                      {m.hindsight_memory_id && (
                        <span className="font-mono text-[10px] text-muted-foreground truncate max-w-[140px]">
                          ID: {m.hindsight_memory_id}
                        </span>
                      )}
                    </div>
                    <p className="font-medium text-foreground/90 leading-relaxed">
                      {m.memory_text}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* 4. Retained Facts Permanent Neon Ledger */}
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="pb-3 border-b border-border/40">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Database className="h-4 w-4 text-primary" />
                Retained Facts
              </CardTitle>
              <CardDescription className="text-xs">
                Permanent ledger of facts synchronized between Hindsight Cloud and Neon PostgreSQL.
              </CardDescription>
            </div>
            <Badge variant="outline" className="text-xs">
              {facts.length} facts logged
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {factsLoading ? (
            <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              Loading facts ledger...
            </div>
          ) : facts.length === 0 ? (
            <div className="p-8 text-center text-xs text-muted-foreground">
              No facts retained yet. Use the "Add Team Rule" box above or <code className="bg-muted px-1 rounded">review-agent learn</code> to store rules.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[140px]">Memory ID</TableHead>
                  <TableHead>Fact Content</TableHead>
                  <TableHead>Tags</TableHead>
                  <TableHead className="text-right">Creation Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {facts.map((f) => (
                  <TableRow key={f.id}>
                    <TableCell className="font-mono text-xs text-muted-foreground">
                      {f.memory_id ? f.memory_id.substring(0, 14) + "..." : "Neon Synced"}
                    </TableCell>
                    <TableCell className="font-medium text-xs leading-relaxed max-w-md">
                      {f.content}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {f.tags && f.tags.length > 0 ? (
                          f.tags.map((t) => (
                            <Badge key={t} variant="secondary" className="text-[10px] py-0 px-1">
                              {t}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-[11px] text-muted-foreground">-</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right text-xs text-muted-foreground font-mono">
                      {new Date(f.created_at).toLocaleDateString([], {
                        month: "short",
                        day: "numeric",
                        year: "numeric",
                      })}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

