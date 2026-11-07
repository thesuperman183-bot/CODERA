"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useNotification } from "@/components/ui/notifications";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bot,
  Brain,
  CheckCircle2,
  ChevronRight,
  Code2,
  Copy,
  ExternalLink,
  FileCode,
  FileText,
  FileUp,
  Folder,
  GitBranch,
  GitCommit,
  GitFork,
  GitPullRequest,
  History,
  Info,
  Key,
  Layers,
  Loader2,
  Play,
  RotateCcw,
  Search,
  ShieldAlert,
  Sparkles,
  Star,
  Terminal,
} from "lucide-react";

interface Finding {
  id?: string;
  title: string;
  description: string;
  severity: "critical" | "high" | "medium" | "low" | "info";
  file_path?: string;
  line_number?: number;
  recommendation?: string;
}

interface ReviewResult {
  review_id: string;
  review: string;
  status: string;
  model_used: string;
  memories_used: string[];
  findings: Finding[];
  repository?: string;
  commit_sha?: string;
  pr_number?: number;
  file_path?: string;
}

interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  owner: string;
  default_branch: string;
  private: boolean;
  description?: string;
  language?: string;
  updated_at?: string;
  html_url?: string;
}

interface PullRequestItem {
  number: number;
  title: string;
  author?: string;
  author_avatar?: string;
  state: string;
  html_url?: string;
  base_branch?: string;
  head_branch?: string;
  head_sha?: string;
  created_at?: string;
  updated_at?: string;
  additions: number;
  deletions: number;
  changed_files_count: number;
  languages: string[];
  has_tests: boolean;
  recommendation_score: number;
  recommendation_priority: "high" | "medium" | "low";
  recommendation_reasons: string[];
}

const SAMPLE_DIFFS: Record<string, { label: string; diff: string }> = {
  sqlInjection: {
    label: "SQL Injection Flaw",
    diff: `--- a/user_repository.py
+++ b/user_repository.py
@@ -10,4 +10,4 @@ class UserRepository:
     def get_user_by_id(self, user_id: str):
-        query = f"SELECT * FROM users WHERE id = '{user_id}'"
-        return self.db.execute(query)
+        # Vulnerable inline interpolation
+        return self.db.execute(f"SELECT * FROM users WHERE id = '{user_id}'")
`,
  },
  hardcodedSecret: {
    label: "Hardcoded API Secret",
    diff: `--- a/payment_gateway.py
+++ b/payment_gateway.py
@@ -4,3 +4,4 @@
 import os
+STRIPE_SECRET_KEY = "dummy_fake_test_key_for_code_review_demo"
 
 def initialize_payment():
`,
  },
  cleanPatch: {
    label: "Safe Clean Patch",
    diff: `--- a/math_utils.py
+++ b/math_utils.py
@@ -1,3 +1,6 @@
+def safe_divide(numerator: float, denominator: float) -> float:
+    if denominator == 0:
+        raise ValueError("denominator cannot be zero")
+    return numerator / denominator
`,
  },
};

export function CodeReviewWorkspace() {
  const { activeTeamId } = useAuth();
  const { success, error } = useNotification();

  // Mode: "manual" diff paste vs "github" repo / PR explorer
  const [activeTab, setActiveTab] = useState<"manual" | "github" | "prs">("manual");

  // Manual Diff State
  const [diff, setDiff] = useState<string>(SAMPLE_DIFFS.sqlInjection.diff);
  const [loading, setLoading] = useState(false);
  const [activeStep, setActiveStep] = useState<number>(0);
  const [result, setResult] = useState<ReviewResult | null>(null);
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [copied, setCopied] = useState(false);

  // GitHub Integration State
  const [ghConnected, setGhConnected] = useState<boolean>(false);
  const [ghUsername, setGhUsername] = useState<string>("");
  const [connectModalOpen, setConnectModalOpen] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const [connecting, setConnecting] = useState(false);

  // Repositories & Tree State
  const [repos, setRepos] = useState<GitHubRepo[]>([]);
  const [selectedRepo, setSelectedRepo] = useState<GitHubRepo | null>(null);
  const [branches, setBranches] = useState<any[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>("main");
  const [treeItems, setTreeItems] = useState<any[]>([]);
  const [treeLoading, setTreeLoading] = useState(false);
  const [selectedFilePath, setSelectedFilePath] = useState<string | null>(null);

  // Pull Request Intelligence State
  const [prs, setPrs] = useState<PullRequestItem[]>([]);
  const [prsLoading, setPrsLoading] = useState(false);
  const [prLanguageFilter, setPrLanguageFilter] = useState<string>("");
  const [selectedPR, setSelectedPR] = useState<PullRequestItem | null>(null);

  const steps = [
    "Resolving user team & Hindsight memory bank",
    "Recalling relevant engineering guidelines",
    "Generating deep code review via Groq LLM",
    "Parsing findings & saving permanently in Neon",
  ];

  // 1. Check GitHub connection status on mount
  useEffect(() => {
    async function checkStatus() {
      try {
        const res = await apiClient.github.status();
        setGhConnected(res.connected);
        if (res.connected && res.github_username) {
          setGhUsername(res.github_username);
          loadRepositories();
        }
      } catch {
        setGhConnected(false);
      }
    }
    checkStatus();
  }, []);

  const loadRepositories = async () => {
    try {
      const data = await apiClient.github.repositories();
      if (Array.isArray(data)) {
        setRepos(data);
        if (data.length > 0 && !selectedRepo) {
          handleSelectRepo(data[0]);
        }
      }
    } catch {
      // Ignored if unconfigured
    }
  };

  const handleConnectToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!tokenInput.trim()) return;
    setConnecting(true);
    try {
      const res = await apiClient.github.connect(tokenInput.trim());
      setGhConnected(true);
      setGhUsername(res.github_username || "connected");
      setConnectModalOpen(false);
      setTokenInput("");
      success("GitHub Connected", `Authenticated as ${res.github_username}`);
      loadRepositories();
    } catch (err: any) {
      error("Connection Failed", err.message || "Failed to authenticate token");
    } finally {
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    try {
      await apiClient.github.disconnect();
      setGhConnected(false);
      setGhUsername("");
      setRepos([]);
      setSelectedRepo(null);
      setPrs([]);
      success("Disconnected", "GitHub credentials removed");
    } catch (err: any) {
      error("Disconnect Failed", err.message);
    }
  };

  const handleSelectRepo = async (repo: GitHubRepo) => {
    setSelectedRepo(repo);
    setSelectedFilePath(null);
    setSelectedBranch(repo.default_branch || "main");

    // Load branches
    try {
      const bData = await apiClient.github.branches(repo.owner, repo.name);
      setBranches(bData || []);
    } catch {
      setBranches([]);
    }

    // Load file tree
    loadRepoTree(repo.owner, repo.name, repo.default_branch || "main");

    // Load intelligent PR recommendations
    loadPullRequests(repo.owner, repo.name);
  };

  const loadRepoTree = async (owner: string, repo: string, ref: string) => {
    setTreeLoading(true);
    try {
      const tree = await apiClient.github.tree(owner, repo, ref, false);
      setTreeItems(tree || []);
    } catch {
      setTreeItems([]);
    } finally {
      setTreeLoading(false);
    }
  };

  const loadPullRequests = async (owner: string, repo: string, langFilter?: string) => {
    setPrsLoading(true);
    try {
      const data = await apiClient.pullRequests.list(owner, repo, {
        language: langFilter || prLanguageFilter || undefined,
        team_id: activeTeamId || undefined,
      });
      setPrs(data || []);
    } catch {
      setPrs([]);
    } finally {
      setPrsLoading(false);
    }
  };

  // Review GitHub file
  const handleReviewFile = async (filePath: string) => {
    if (!selectedRepo) return;
    setLoading(true);
    setResult(null);
    setActiveStep(1);

    try {
      const res = await apiClient.github.reviewResource({
        owner: selectedRepo.owner,
        repo: selectedRepo.name,
        ref: selectedBranch,
        file_path: filePath,
        team_id: activeTeamId || undefined,
      });
      setResult(res);
      success("Review Completed", `Review for ${filePath} saved in Neon`);
    } catch (err: any) {
      error("Review Failed", err.message);
    } finally {
      setLoading(false);
    }
  };

  // Review Pull Request
  const handleReviewPR = async (prNumber: number) => {
    if (!selectedRepo) return;
    setLoading(true);
    setResult(null);
    setActiveStep(1);

    try {
      const res = await apiClient.pullRequests.review(
        selectedRepo.owner,
        selectedRepo.name,
        prNumber,
        activeTeamId || undefined
      );
      setResult(res);
      success("PR Review Completed", `Pull Request #${prNumber} analyzed and saved in Neon`);
    } catch (err: any) {
      error("PR Review Failed", err.message);
    } finally {
      setLoading(false);
    }
  };

  // Manual Review Submit
  const handleRunReview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!diff.trim()) return;

    setLoading(true);
    setResult(null);
    setActiveStep(1);

    try {
      const res = await apiClient.reviews.submit(diff, activeTeamId || undefined);
      setResult(res);
      success("Review Completed", `Session ${res.review_id?.substring(0, 8)} saved in Neon`);
    } catch (err: any) {
      error("Review Failed", err?.message || "Encountered an error executing review.");
    } finally {
      setLoading(false);
    }
  };

  const copyReviewText = () => {
    if (!result?.review) return;
    navigator.clipboard.writeText(result.review);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const filteredFindings = result?.findings?.filter((f) => {
    if (severityFilter === "all") return true;
    return f.severity?.toLowerCase() === severityFilter;
  }) || [];

  return (
    <div className="space-y-6">
      {/* Top Workspace Header & Navigation Tabs */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-border/40 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Code Review Workspace</h1>
            {ghConnected ? (
              <Badge variant="outline" className="gap-1 text-emerald-500 border-emerald-500/30 text-[11px]">
                <GitBranch className="h-3 w-3" />
                GitHub: {ghUsername}
              </Badge>
            ) : (
              <Badge variant="secondary" className="text-[11px]">
                GitHub Disconnected
              </Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Manual diffs, GitHub repository exploration, and intelligent PR recommendations powered by Groq & Hindsight.
          </p>
        </div>

        {/* Tab Controls & Connect Button */}
        <div className="flex items-center gap-2">
          <div className="flex rounded-lg border border-border/80 bg-muted/40 p-1 text-xs">
            <button
              type="button"
              onClick={() => setActiveTab("manual")}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                activeTab === "manual" ? "bg-primary text-primary-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              Manual Diff
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("github")}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                activeTab === "github" ? "bg-primary text-primary-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              GitHub Repo
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("prs")}
              className={`rounded-md px-3 py-1 font-medium transition-colors ${
                activeTab === "prs" ? "bg-primary text-primary-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              PR Intelligence
            </button>
          </div>

          {!ghConnected ? (
            <Button size="sm" onClick={() => setConnectModalOpen(true)} className="gap-1.5 text-xs h-8">
              <Key className="h-3.5 w-3.5" />
              Connect GitHub
            </Button>
          ) : (
            <Button size="sm" variant="outline" onClick={handleDisconnect} className="text-xs h-8 text-muted-foreground hover:text-red-400">
              Disconnect
            </Button>
          )}
        </div>
      </div>

      {/* Main Review Layout */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ========================================================================= */}
        {/* LEFT COLUMN: Controls (Manual Diff OR GitHub Browser OR PR Recommendations) */}
        {/* ========================================================================= */}
        {activeTab === "manual" && (
          <Card className="border border-border/80 shadow-xs flex flex-col">
            <CardHeader className="pb-3 border-b border-border/40">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <Code2 className="h-4 w-4 text-primary" />
                  Unified Diff Input
                </CardTitle>
                <div className="flex items-center gap-1.5">
                  <span className="text-[11px] text-muted-foreground mr-1 hidden sm:inline">Presets:</span>
                  {Object.entries(SAMPLE_DIFFS).map(([k, item]) => (
                    <button
                      key={k}
                      type="button"
                      onClick={() => setDiff(item.diff)}
                      className="rounded border border-border/70 bg-muted/40 px-2 py-0.5 text-[10px] font-medium hover:bg-accent transition-colors"
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
              <CardDescription className="text-xs">
                Paste raw git diff/patch text to review with team rules & Hindsight memory.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col pt-4 space-y-4">
              <form onSubmit={handleRunReview} className="flex-1 flex flex-col space-y-3">
                <div className="relative flex-1">
                  <textarea
                    value={diff}
                    onChange={(e) => setDiff(e.target.value)}
                    placeholder="Paste diff or git patch here..."
                    rows={16}
                    required
                    className="w-full h-full min-h-[360px] font-mono text-xs rounded-lg border border-input bg-card p-3 leading-relaxed focus:outline-none focus:ring-1 focus:ring-ring resize-y"
                  />
                </div>
                <div className="flex items-center justify-between gap-2 pt-1">
                  <Button
                    type="submit"
                    disabled={loading || !diff.trim()}
                    className="gap-2 h-8 px-4 text-xs font-semibold shadow-xs ml-auto"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        Analyzing...
                      </>
                    ) : (
                      <>
                        <Play className="h-3.5 w-3.5" />
                        Run AI Review
                      </>
                    )}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        {activeTab === "github" && (
          <Card className="border border-border/80 shadow-xs flex flex-col">
            <CardHeader className="pb-3 border-b border-border/40">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Folder className="h-4 w-4 text-primary" />
                Repository & File Explorer
              </CardTitle>
              <CardDescription className="text-xs">
                Browse repository files or branches and trigger reviews on demand.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {!ghConnected ? (
                <div className="flex flex-col items-center justify-center p-8 text-center text-muted-foreground space-y-3">
                  <Key className="h-10 w-10 stroke-1 opacity-40 text-primary" />
                  <div>
                    <p className="text-sm font-semibold">GitHub Not Connected</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Connect your GitHub Personal Access Token to browse repositories and review files.
                    </p>
                  </div>
                  <Button size="sm" onClick={() => setConnectModalOpen(true)} className="gap-2 text-xs">
                    Connect Account
                  </Button>
                </div>
              ) : (
                <div className="space-y-4">
                  {/* Select Repo & Branch */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                        Select Repository
                      </label>
                      <select
                        value={selectedRepo?.full_name || ""}
                        onChange={(e) => {
                          const r = repos.find((x) => x.full_name === e.target.value);
                          if (r) handleSelectRepo(r);
                        }}
                        className="w-full text-xs rounded-lg border border-input bg-card p-2 font-mono"
                      >
                        {repos.map((r) => (
                          <option key={r.id} value={r.full_name}>
                            {r.full_name} ({r.language || "code"})
                          </option>
                        ))}
                      </select>
                    </div>

                    <div>
                      <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                        Active Branch
                      </label>
                      <select
                        value={selectedBranch}
                        onChange={(e) => {
                          setSelectedBranch(e.target.value);
                          if (selectedRepo) loadRepoTree(selectedRepo.owner, selectedRepo.name, e.target.value);
                        }}
                        className="w-full text-xs rounded-lg border border-input bg-card p-2 font-mono"
                      >
                        {branches.map((b) => (
                          <option key={b.name} value={b.name}>
                            {b.name}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* File List / Tree */}
                  <div className="border border-border/60 rounded-lg bg-card/60 divide-y divide-border/40 max-h-72 overflow-y-auto">
                    {treeLoading ? (
                      <div className="p-6 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Loading tree...
                      </div>
                    ) : treeItems.length === 0 ? (
                      <div className="p-6 text-center text-xs text-muted-foreground">
                        No files found in root.
                      </div>
                    ) : (
                      treeItems.map((item) => (
                        <div
                          key={item.sha}
                          className="flex items-center justify-between p-2.5 text-xs hover:bg-muted/40 transition-colors"
                        >
                          <div className="flex items-center gap-2 overflow-hidden">
                            {item.type === "tree" ? (
                              <Folder className="h-3.5 w-3.5 text-blue-400 shrink-0" />
                            ) : (
                              <FileCode className="h-3.5 w-3.5 text-emerald-400 shrink-0" />
                            )}
                            <span className="font-mono truncate">{item.path}</span>
                          </div>
                          {item.type === "blob" && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => handleReviewFile(item.path)}
                              disabled={loading}
                              className="h-6 px-2 text-[10px] gap-1 shrink-0"
                            >
                              <Play className="h-2.5 w-2.5" />
                              Review File
                            </Button>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {activeTab === "prs" && (
          <Card className="border border-border/80 shadow-xs flex flex-col">
            <CardHeader className="pb-3 border-b border-border/40">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <GitPullRequest className="h-4 w-4 text-purple-400" />
                    Pull Request Intelligence & Recommendations
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Ranked by security impact, test coverage, and organizational coding standards.
                  </CardDescription>
                </div>
                {selectedRepo && (
                  <Badge variant="outline" className="font-mono text-[10px]">
                    {selectedRepo.name}
                  </Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="pt-4 space-y-4">
              {/* Language Filter Toolbar */}
              <div className="flex items-center gap-2 text-xs">
                <span className="text-[11px] text-muted-foreground">Stack Filter:</span>
                {["", "Python", "TypeScript", "SQL"].map((lang) => (
                  <button
                    key={lang}
                    type="button"
                    onClick={() => {
                      setPrLanguageFilter(lang);
                      if (selectedRepo) loadPullRequests(selectedRepo.owner, selectedRepo.name, lang);
                    }}
                    className={`rounded px-2 py-0.5 text-[10px] font-medium border ${
                      prLanguageFilter === lang
                        ? "bg-primary text-primary-foreground border-primary"
                        : "border-border/60 bg-muted/20 text-muted-foreground hover:bg-muted"
                    }`}
                  >
                    {lang || "All Languages"}
                  </button>
                ))}
              </div>

              {/* PRs Recommendation List */}
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {prsLoading ? (
                  <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin text-purple-400" />
                    Analyzing pull requests with Hindsight rules...
                  </div>
                ) : prs.length === 0 ? (
                  <div className="p-8 text-center text-xs text-muted-foreground">
                    No pull requests found matching the current filters.
                  </div>
                ) : (
                  prs.map((pr) => (
                    <div
                      key={pr.number}
                      className={`rounded-xl border p-3.5 text-xs space-y-2.5 transition-shadow hover:shadow-xs ${
                        pr.recommendation_priority === "high"
                          ? "border-purple-500/30 bg-purple-950/10"
                          : "border-border/70 bg-card"
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="space-y-1">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-semibold text-sm">
                              #{pr.number} {pr.title}
                            </span>
                            <Badge
                              variant={
                                pr.recommendation_priority === "high"
                                  ? "destructive"
                                  : pr.recommendation_priority === "medium"
                                  ? "warning"
                                  : "secondary"
                              }
                              className="text-[10px] font-medium"
                            >
                              Priority Score: {pr.recommendation_score}/100
                            </Badge>
                          </div>
                          <p className="text-[11px] text-muted-foreground">
                            by <span className="font-medium text-foreground">{pr.author}</span> • {pr.changed_files_count} files changed (+{pr.additions} / -{pr.deletions})
                          </p>
                        </div>

                        <Button
                          size="sm"
                          onClick={() => handleReviewPR(pr.number)}
                          disabled={loading}
                          className="gap-1.5 text-xs h-7 shrink-0 shadow-xs"
                        >
                          <Bot className="h-3.5 w-3.5" />
                          Review PR
                        </Button>
                      </div>

                      {/* Explicit Human-Readable Reasons */}
                      <div className="rounded-lg border border-border/50 bg-muted/30 p-2.5 text-[11px] space-y-1">
                        <p className="font-semibold text-muted-foreground flex items-center gap-1">
                          <Sparkles className="h-3 w-3 text-purple-400" />
                          Recommendation Reasons:
                        </p>
                        <ul className="list-disc list-inside space-y-0.5 text-foreground/80">
                          {pr.recommendation_reasons.map((reason, idx) => (
                            <li key={idx}>{reason}</li>
                          ))}
                        </ul>
                      </div>

                      {/* Badges for Languages & Test Coverage */}
                      <div className="flex items-center gap-2 pt-1">
                        {pr.languages.map((l) => (
                          <Badge key={l} variant="outline" className="text-[10px]">
                            {l}
                          </Badge>
                        ))}
                        {pr.has_tests ? (
                          <span className="text-[10px] text-emerald-400 flex items-center gap-1 font-medium">
                            <CheckCircle2 className="h-3 w-3" /> Includes Tests
                          </span>
                        ) : (
                          <span className="text-[10px] text-amber-400 flex items-center gap-1 font-medium">
                            <AlertTriangle className="h-3 w-3" /> Needs Test Verification
                          </span>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* ========================================================================= */}
        {/* RIGHT COLUMN: Review Findings, Structured Output & Memories Utilized */}
        {/* ========================================================================= */}
        <Card className="border border-border/80 shadow-xs flex flex-col">
          <CardHeader className="pb-3 border-b border-border/40">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Bot className="h-4 w-4 text-primary" />
                Review Feedback & Findings
              </CardTitle>
              {result && (
                <div className="flex items-center gap-1.5">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={copyReviewText}
                    className="h-7 px-2 text-xs text-muted-foreground"
                  >
                    <Copy className="h-3 w-3 mr-1" />
                    {copied ? "Copied" : "Copy"}
                  </Button>
                  <Badge variant="outline" className="text-[10px] font-mono">
                    {result.model_used}
                  </Badge>
                </div>
              )}
            </div>
            <CardDescription className="text-xs">
              {result
                ? `Session: ${result.review_id} ${result.repository ? `• ${result.repository}` : ""} ${result.pr_number ? `• PR #${result.pr_number}` : ""}`
                : "Select a diff, file, or PR to trigger review analysis."}
            </CardDescription>
          </CardHeader>

          <CardContent className="flex-1 flex flex-col pt-4">
            {loading ? (
              <div className="flex-1 flex flex-col items-center justify-center p-12 text-center text-muted-foreground space-y-3">
                <Loader2 className="h-10 w-10 animate-spin text-primary" />
                <p className="text-sm font-semibold">Running Code Review Pipeline</p>
                <p className="text-xs text-muted-foreground max-w-xs">
                  Recalling Hindsight memories, inspecting applicable rules, and querying Groq LLM...
                </p>
              </div>
            ) : result ? (
              <div className="space-y-4">
                {/* Status Badges */}
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="success" className="text-xs capitalize">
                    {result.status}
                  </Badge>
                  {result.memories_used && result.memories_used.length > 0 && (
                    <Badge variant="secondary" className="gap-1 text-xs">
                      <Sparkles className="h-3 w-3 text-purple-400" />
                      {result.memories_used.length} memory rules recalled
                    </Badge>
                  )}
                  {result.findings && (
                    <Badge
                      variant={result.findings.length > 0 ? "destructive" : "secondary"}
                      className="text-xs"
                    >
                      {result.findings.length} findings extracted
                    </Badge>
                  )}
                </div>

                {/* Recalled Memories Summary Banner */}
                {result.memories_used && result.memories_used.length > 0 && (
                  <div className="rounded-lg border border-purple-500/20 bg-purple-500/5 p-3 text-xs space-y-1.5">
                    <p className="font-semibold text-purple-400 flex items-center gap-1.5">
                      <Brain className="h-3.5 w-3.5" />
                      Rules Guided by Hindsight Memory:
                    </p>
                    <ul className="list-disc list-inside space-y-1 text-muted-foreground">
                      {result.memories_used.map((m, i) => (
                        <li key={i} className="line-clamp-2">
                          {m}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Structured Findings Filter Tabs */}
                {result.findings && result.findings.length > 0 && (
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between border-b border-border/40 pb-1.5">
                      <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                        Structured Findings
                      </span>
                      <div className="flex gap-1 text-[10px]">
                        {["all", "critical", "high", "medium", "low", "info"].map((sev) => (
                          <button
                            key={sev}
                            type="button"
                            onClick={() => setSeverityFilter(sev)}
                            className={`rounded px-1.5 py-0.5 capitalize transition-colors ${
                              severityFilter === sev
                                ? "bg-primary text-primary-foreground font-semibold"
                                : "text-muted-foreground hover:bg-muted"
                            }`}
                          >
                            {sev}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                      {filteredFindings.map((f, idx) => (
                        <div
                          key={idx}
                          className={`rounded-lg border p-3 text-xs space-y-1.5 ${
                            f.severity === "critical"
                              ? "border-red-500/30 bg-red-950/20 text-red-200"
                              : f.severity === "high"
                              ? "border-orange-500/30 bg-orange-950/20 text-orange-200"
                              : f.severity === "medium"
                              ? "border-amber-500/30 bg-amber-950/20 text-amber-200"
                              : "border-border/60 bg-muted/20 text-foreground"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-semibold flex items-center gap-1.5">
                              {f.severity === "critical" ? (
                                <ShieldAlert className="h-3.5 w-3.5 text-red-400" />
                              ) : f.severity === "high" ? (
                                <AlertTriangle className="h-3.5 w-3.5 text-orange-400" />
                              ) : (
                                <Info className="h-3.5 w-3.5 text-amber-400" />
                              )}
                              [{f.severity?.toUpperCase()}] {f.title}
                            </span>
                            {f.line_number && (
                              <span className="font-mono text-[10px] text-muted-foreground">
                                {f.file_path ? `${f.file_path}:` : "line "}
                                {f.line_number}
                              </span>
                            )}
                          </div>
                          {f.description && (
                            <p className="text-muted-foreground leading-relaxed">
                              {f.description}
                            </p>
                          )}
                          {f.recommendation && (
                            <div className="rounded bg-black/40 p-2 font-mono text-[11px] text-emerald-400 mt-1">
                              Fix: {f.recommendation}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Full Markdown Review Text */}
                <div className="space-y-1.5">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                    Complete LLM Output
                  </p>
                  <div className="rounded-lg bg-muted/40 p-4 font-mono text-xs whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto border border-border/50">
                    {result.review}
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex-1 flex flex-col items-center justify-center text-center p-12 text-muted-foreground">
                <FileCode className="h-12 w-12 stroke-1 mb-3 opacity-30 text-primary" />
                <p className="text-sm font-medium">Ready to Review</p>
                <p className="text-xs text-muted-foreground/80 max-w-xs mt-1">
                  Choose a preset diff, repository file, or pull request to see live memory-guided findings.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Connect GitHub Dialog */}
      <Dialog open={connectModalOpen} onOpenChange={setConnectModalOpen}>
        <form onSubmit={handleConnectToken}>
          <DialogHeader>
            <DialogTitle>Connect GitHub Account</DialogTitle>
            <DialogDescription>
              Provide a GitHub Personal Access Token with <code className="bg-muted px-1 rounded">repo</code> scope or install your GitHub App.
            </DialogDescription>
          </DialogHeader>
          <div className="py-4 space-y-3">
            <Input
              type="password"
              value={tokenInput}
              onChange={(e) => setTokenInput(e.target.value)}
              placeholder="ghp_... or github_pat_..."
              required
              className="font-mono text-xs"
            />
            <p className="text-[11px] text-muted-foreground">
              Tokens are stored on the server in Neon PostgreSQL. They are never exposed in frontend code.
            </p>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConnectModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={connecting}>
              {connecting ? "Verifying..." : "Connect GitHub"}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}
