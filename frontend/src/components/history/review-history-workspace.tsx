"use client";

import React, { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useNotification } from "@/components/ui/notifications";
import {
  AlertCircle,
  AlertTriangle,
  ArrowUpDown,
  BookOpen,
  Brain,
  BrainCircuit,
  CheckCircle,
  ChevronLeft,
  ChevronRight,
  Clock,
  Code2,
  Copy,
  ExternalLink,
  Eye,
  FileCode,
  Filter,
  GitCommit,
  GitFork,
  GitPullRequest,
  History,
  Info,
  Layers,
  Loader2,
  RefreshCw,
  Search,
  ShieldAlert,
  Terminal,
  XCircle,
} from "lucide-react";

interface SeverityCounts {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

interface ReviewHistoryItem {
  id: string;
  repository?: string;
  commit_sha?: string;
  pr_number?: number;
  file_path?: string;
  created_at: string;
  source: string;
  status: string;
  model_used: string;
  findings_count: number;
  severity_counts: SeverityCounts;
  memories_count: number;
}

interface ReviewFinding {
  id: string;
  title: string;
  description: string;
  severity: string;
  file_path?: string;
  line_number?: number;
  recommendation?: string;
}

interface ReviewMemoryItem {
  id: string;
  memory_text: string;
  hindsight_memory_id?: string;
  relevance_metadata?: Record<string, any>;
}

interface FullReviewData {
  id: string;
  code_diff: string;
  review: string;
  model_used: string;
  source: string;
  status: string;
  repository?: string;
  commit_sha?: string;
  pr_number?: number;
  file_path?: string;
  created_at: string;
  findings: ReviewFinding[];
  memories: ReviewMemoryItem[];
}

export function ReviewHistoryWorkspace() {
  const { activeTeamId } = useAuth();
  const { success, error } = useNotification();

  // Data states
  const [reviews, setReviews] = useState<ReviewHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalCount, setTotalCount] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [uniqueRepos, setUniqueRepos] = useState<string[]>([]);

  // Query & filter states
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [search, setSearch] = useState("");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [repoFilter, setRepoFilter] = useState("all");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");

  // Full review modal
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [reviewDetail, setReviewDetail] = useState<FullReviewData | null>(null);
  const [activeTab, setActiveTab] = useState<"findings" | "report" | "diff" | "memories">("findings");

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await apiClient.reviews.history({
        page,
        page_size: pageSize,
        search: search.trim() || undefined,
        source: sourceFilter !== "all" ? sourceFilter : undefined,
        status: statusFilter !== "all" ? statusFilter : undefined,
        severity: severityFilter !== "all" ? severityFilter : undefined,
        repository: repoFilter !== "all" ? repoFilter : undefined,
        team_id: activeTeamId || undefined,
        sort_by: sortBy,
        sort_order: sortOrder,
      });

      setReviews(res.items || []);
      setTotalCount(res.total || 0);
      setTotalPages(res.total_pages || 1);
      if (res.unique_repositories) {
        setUniqueRepos(res.unique_repositories);
      }
    } catch (err: any) {
      error("Failed to load review history", err.message || "Failed to query Neon");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [page, pageSize, sourceFilter, statusFilter, severityFilter, repoFilter, sortBy, sortOrder, activeTeamId]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchHistory();
  };

  const handleOpenReview = async (reviewId: string, initialTab: "findings" | "report" | "diff" | "memories" = "findings") => {
    setSelectedReviewId(reviewId);
    setActiveTab(initialTab);
    setModalOpen(true);
    setDetailLoading(true);

    try {
      const data = await apiClient.reviews.get(reviewId);
      setReviewDetail(data);
    } catch (err: any) {
      error("Failed to fetch full review", err.message || "Review session could not be retrieved");
      setModalOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const copyToClipboard = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    success("Copied", `${label} copied to clipboard`);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-border/40 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Review History</h1>
            <Badge variant="outline" className="gap-1 text-emerald-400 border-emerald-500/30 text-[11px]">
              <History className="h-3 w-3" />
              Neon Permanent Ledger
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Audit historical code reviews, examine severity breakdowns, filter across repositories, and inspect recalled Hindsight memories.
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            setPage(1);
            fetchHistory();
          }}
          disabled={loading}
          className="gap-1.5 text-xs h-8"
        >
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Search and Filters Bar */}
      <Card className="border border-border/80 shadow-xs">
        <CardContent className="p-4 space-y-3">
          <form onSubmit={handleSearchSubmit} className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search reviews by repository, review ID, commit SHA, PR number, or file path..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-9 h-9 text-xs"
              />
            </div>
            <Button type="submit" size="sm" className="h-9 px-4 text-xs gap-1.5">
              <Search className="h-3.5 w-3.5" />
              Search
            </Button>
            {search && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-9 text-xs"
                onClick={() => {
                  setSearch("");
                  setPage(1);
                  setTimeout(fetchHistory, 0);
                }}
              >
                Clear
              </Button>
            )}
          </form>

          {/* Filter Dropdowns */}
          <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-border/40 text-xs">
            <div className="flex items-center gap-1.5 text-muted-foreground mr-1">
              <Filter className="h-3.5 w-3.5" />
              <span className="font-medium text-[11px] uppercase tracking-wider">Filters:</span>
            </div>

            {/* Source Filter */}
            <select
              value={sourceFilter}
              onChange={(e) => {
                setSourceFilter(e.target.value);
                setPage(1);
              }}
              className="h-7 rounded-md border border-input bg-background px-2 text-xs focus:outline-hidden"
            >
              <option value="all">Source: All</option>
              <option value="CLI">CLI Reviews</option>
              <option value="Web">Web Reviews</option>
            </select>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value);
                setPage(1);
              }}
              className="h-7 rounded-md border border-input bg-background px-2 text-xs focus:outline-hidden"
            >
              <option value="all">Status: All</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>

            {/* Severity Filter */}
            <select
              value={severityFilter}
              onChange={(e) => {
                setSeverityFilter(e.target.value);
                setPage(1);
              }}
              className="h-7 rounded-md border border-input bg-background px-2 text-xs focus:outline-hidden"
            >
              <option value="all">Severity: All</option>
              <option value="critical">Has Critical Issues</option>
              <option value="high">Has High Severity</option>
              <option value="medium">Has Medium Severity</option>
              <option value="low">Has Low Severity</option>
            </select>

            {/* Repository Filter */}
            {uniqueRepos.length > 0 && (
              <select
                value={repoFilter}
                onChange={(e) => {
                  setRepoFilter(e.target.value);
                  setPage(1);
                }}
                className="h-7 rounded-md border border-input bg-background px-2 text-xs focus:outline-hidden max-w-[200px] truncate"
              >
                <option value="all">Repo: All Repositories</option>
                {uniqueRepos.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            )}

            {/* Sort Field & Order */}
            <div className="ml-auto flex items-center gap-1.5">
              <span className="text-[11px] text-muted-foreground">Sort:</span>
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value)}
                className="h-7 rounded-md border border-input bg-background px-2 text-xs focus:outline-hidden"
              >
                <option value="created_at">Date / Timestamp</option>
                <option value="findings_count">Findings Count</option>
              </select>

              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                onClick={() => setSortOrder(sortOrder === "desc" ? "asc" : "desc")}
                title={`Sort ${sortOrder === "desc" ? "Ascending" : "Descending"}`}
              >
                <ArrowUpDown className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Main Review History Table */}
      <Card className="border border-border/80 shadow-xs">
        <CardHeader className="py-3 px-4 border-b border-border/40">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <History className="h-4 w-4 text-primary" />
              Review Sessions ({totalCount})
            </CardTitle>
            <span className="text-xs text-muted-foreground">
              Showing page {page} of {totalPages}
            </span>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <p className="text-xs text-muted-foreground">Retrieving Neon review records...</p>
            </div>
          ) : reviews.length === 0 ? (
            <div className="text-center py-16 px-4 space-y-2">
              <Code2 className="h-8 w-8 text-muted-foreground mx-auto" />
              <p className="text-sm font-medium">No review sessions found</p>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                No code reviews match your current filters. Try adjusting your search query, or run a new review from the Review Workspace or CLI.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent">
                    <TableHead className="w-[180px]">Review ID</TableHead>
                    <TableHead>Project / Repository</TableHead>
                    <TableHead className="w-[100px]">Source</TableHead>
                    <TableHead className="w-[110px]">Status</TableHead>
                    <TableHead className="w-[220px]">Findings Breakdown</TableHead>
                    <TableHead className="w-[90px]">Memories</TableHead>
                    <TableHead className="w-[150px]">Date & Time</TableHead>
                    <TableHead className="text-right w-[140px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {reviews.map((r) => (
                    <TableRow key={r.id} className="hover:bg-muted/40 transition-colors">
                      {/* Review ID */}
                      <TableCell className="font-mono text-xs">
                        <div className="flex items-center gap-1.5">
                          <span className="font-medium">{r.id.substring(0, 8)}...</span>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-5 w-5 text-muted-foreground hover:text-foreground"
                            onClick={() => copyToClipboard(r.id, "Review ID")}
                            title="Copy full Review ID"
                          >
                            <Copy className="h-3 w-3" />
                          </Button>
                        </div>
                      </TableCell>

                      {/* Project / Repository */}
                      <TableCell>
                        {r.repository ? (
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-1 text-xs font-medium text-foreground">
                              <GitFork className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                              <span className="truncate max-w-[180px]">{r.repository}</span>
                            </div>
                            <div className="flex items-center gap-2 text-[10px] text-muted-foreground font-mono">
                              {r.pr_number && (
                                <span className="flex items-center gap-0.5 text-purple-400">
                                  <GitPullRequest className="h-2.5 w-2.5" />
                                  PR #{r.pr_number}
                                </span>
                              )}
                              {r.commit_sha && (
                                <span className="flex items-center gap-0.5">
                                  <GitCommit className="h-2.5 w-2.5" />
                                  {r.commit_sha.substring(0, 7)}
                                </span>
                              )}
                            </div>
                          </div>
                        ) : r.file_path ? (
                          <div className="flex items-center gap-1 text-xs text-muted-foreground font-mono">
                            <FileCode className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="truncate max-w-[180px]">{r.file_path}</span>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground italic">Direct Diff Upload</span>
                        )}
                      </TableCell>

                      {/* Source */}
                      <TableCell>
                        <Badge
                          variant="outline"
                          className={`gap-1 text-[11px] font-medium ${
                            r.source === "CLI"
                              ? "border-emerald-500/30 text-emerald-400"
                              : "border-blue-500/30 text-blue-400"
                          }`}
                        >
                          {r.source === "CLI" ? (
                            <Terminal className="h-3 w-3" />
                          ) : (
                            <Code2 className="h-3 w-3" />
                          )}
                          {r.source || "CLI"}
                        </Badge>
                      </TableCell>

                      {/* Status */}
                      <TableCell>
                        <span
                          className={`inline-flex items-center gap-1 text-xs font-medium ${
                            r.status === "completed"
                              ? "text-emerald-500"
                              : r.status === "failed"
                              ? "text-red-500"
                              : "text-amber-500"
                          }`}
                        >
                          {r.status === "completed" ? (
                            <CheckCircle className="h-3.5 w-3.5" />
                          ) : r.status === "failed" ? (
                            <XCircle className="h-3.5 w-3.5" />
                          ) : (
                            <Clock className="h-3.5 w-3.5" />
                          )}
                          <span className="capitalize">{r.status}</span>
                        </span>
                      </TableCell>

                      {/* Findings Breakdown */}
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center gap-1 text-xs">
                            <span className="font-semibold">{r.findings_count}</span>
                            <span className="text-muted-foreground text-[11px]">
                              {r.findings_count === 1 ? "finding" : "findings"}
                            </span>
                          </div>

                          <div className="flex items-center gap-1">
                            {r.severity_counts.critical > 0 && (
                              <Badge className="bg-red-500/15 text-red-400 border border-red-500/30 text-[10px] px-1.5 py-0 h-4">
                                {r.severity_counts.critical} crit
                              </Badge>
                            )}
                            {r.severity_counts.high > 0 && (
                              <Badge className="bg-orange-500/15 text-orange-400 border border-orange-500/30 text-[10px] px-1.5 py-0 h-4">
                                {r.severity_counts.high} high
                              </Badge>
                            )}
                            {r.severity_counts.medium > 0 && (
                              <Badge className="bg-amber-500/15 text-amber-400 border border-amber-500/30 text-[10px] px-1.5 py-0 h-4">
                                {r.severity_counts.medium} med
                              </Badge>
                            )}
                            {r.severity_counts.low > 0 && (
                              <Badge className="bg-blue-500/15 text-blue-400 border border-blue-500/30 text-[10px] px-1.5 py-0 h-4">
                                {r.severity_counts.low} low
                              </Badge>
                            )}
                            {r.findings_count === 0 && (
                              <span className="text-[10px] text-emerald-400 font-medium">Clean</span>
                            )}
                          </div>
                        </div>
                      </TableCell>

                      {/* Memories Recalled */}
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleOpenReview(r.id, "memories")}
                          className="h-6 px-1.5 text-xs text-purple-400 hover:text-purple-300 gap-1"
                          title="Inspect recalled Hindsight memories"
                        >
                          <Brain className="h-3 w-3" />
                          <span>{r.memories_count}</span>
                        </Button>
                      </TableCell>

                      {/* Date & Time */}
                      <TableCell className="text-xs text-muted-foreground font-mono">
                        {new Date(r.created_at).toLocaleString([], {
                          month: "short",
                          day: "numeric",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </TableCell>

                      {/* Actions */}
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleOpenReview(r.id, "findings")}
                            className="h-7 text-xs gap-1 px-2"
                          >
                            <Eye className="h-3 w-3" />
                            View
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleOpenReview(r.id, "memories")}
                            className="h-7 text-xs text-purple-400 hover:text-purple-300 gap-1 px-2"
                            title="View Hindsight Memories"
                          >
                            <BrainCircuit className="h-3 w-3" />
                            Trace
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-4 py-3 border-t border-border/40 text-xs">
              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">Rows per page:</span>
                <select
                  value={pageSize}
                  onChange={(e) => {
                    setPageSize(Number(e.target.value));
                    setPage(1);
                  }}
                  className="h-7 rounded-md border border-input bg-background px-2 text-xs focus:outline-hidden"
                >
                  <option value={10}>10</option>
                  <option value={25}>25</option>
                  <option value={50}>50</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <span className="text-muted-foreground">
                  Page {page} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-7 w-7"
                  disabled={page <= 1}
                  onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  className="h-7 w-7"
                  disabled={page >= totalPages}
                  onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                >
                  <ChevronRight className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Full Review Modal */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] flex flex-col p-0 overflow-hidden">
          <DialogHeader className="p-4 border-b border-border/60">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <DialogTitle className="text-base font-semibold flex items-center gap-2">
                  <History className="h-4 w-4 text-primary" />
                  Review Details & Findings
                </DialogTitle>
                <DialogDescription className="text-xs font-mono mt-0.5">
                  ID: {selectedReviewId}
                </DialogDescription>
              </div>

              {reviewDetail && (
                <div className="flex items-center gap-2">
                  <Badge variant="outline" className="text-[10px]">
                    {reviewDetail.source}
                  </Badge>
                  <Badge variant="secondary" className="text-[10px] font-mono">
                    {reviewDetail.model_used}
                  </Badge>
                </div>
              )}
            </div>

            {/* Modal Tabs */}
            <div className="flex items-center gap-2 pt-3 border-t border-border/40 text-xs">
              <button
                type="button"
                onClick={() => setActiveTab("findings")}
                className={`px-3 py-1.5 rounded-md font-medium text-xs transition-colors ${
                  activeTab === "findings"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
              >
                Findings ({reviewDetail?.findings?.length || 0})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("report")}
                className={`px-3 py-1.5 rounded-md font-medium text-xs transition-colors ${
                  activeTab === "report"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
              >
                AI Review Report
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("diff")}
                className={`px-3 py-1.5 rounded-md font-medium text-xs transition-colors ${
                  activeTab === "diff"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
              >
                Code Diff
              </button>
              <button
                type="button"
                onClick={() => setActiveTab("memories")}
                className={`px-3 py-1.5 rounded-md font-medium text-xs flex items-center gap-1.5 transition-colors ${
                  activeTab === "memories"
                    ? "bg-purple-600 text-white"
                    : "text-purple-400 hover:bg-purple-950/30"
                }`}
              >
                <Brain className="h-3 w-3" />
                Injected Memories ({reviewDetail?.memories?.length || 0})
              </button>
            </div>
          </DialogHeader>

          {/* Modal Body */}
          <div className="flex-1 overflow-y-auto p-4">
            {detailLoading ? (
              <div className="flex flex-col items-center justify-center py-16 gap-2">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
                <p className="text-xs text-muted-foreground">Loading review session from Neon...</p>
              </div>
            ) : !reviewDetail ? (
              <p className="text-xs text-muted-foreground text-center py-8">Review data could not be loaded.</p>
            ) : (
              <div>
                {/* Findings Tab */}
                {activeTab === "findings" && (
                  <div className="space-y-3">
                    {reviewDetail.findings.length === 0 ? (
                      <div className="text-center py-12 text-muted-foreground space-y-2">
                        <CheckCircle className="h-8 w-8 text-emerald-400 mx-auto" />
                        <p className="text-sm font-medium text-foreground">Zero Critical Issues Found</p>
                        <p className="text-xs">The model validated this code change cleanly without findings.</p>
                      </div>
                    ) : (
                      reviewDetail.findings.map((f, idx) => (
                        <div
                          key={f.id || idx}
                          className="rounded-lg border border-border/70 bg-card p-3.5 space-y-2 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <Badge
                                className={
                                  f.severity === "critical"
                                    ? "bg-red-500/20 text-red-400 border border-red-500/40 text-[10px]"
                                    : f.severity === "high"
                                    ? "bg-orange-500/20 text-orange-400 border border-orange-500/40 text-[10px]"
                                    : f.severity === "medium"
                                    ? "bg-amber-500/20 text-amber-400 border border-amber-500/40 text-[10px]"
                                    : "bg-blue-500/20 text-blue-400 border border-blue-500/40 text-[10px]"
                                }
                              >
                                {f.severity.toUpperCase()}
                              </Badge>
                              <h4 className="font-semibold text-foreground text-sm">{f.title}</h4>
                            </div>

                            {f.file_path && (
                              <span className="font-mono text-[11px] text-muted-foreground bg-muted/50 px-2 py-0.5 rounded">
                                {f.file_path} {f.line_number ? `:${f.line_number}` : ""}
                              </span>
                            )}
                          </div>

                          <p className="text-muted-foreground leading-relaxed">{f.description}</p>

                          {f.recommendation && (
                            <div className="rounded border border-emerald-500/20 bg-emerald-950/20 p-2 text-emerald-300 font-mono text-[11px]">
                              <span className="font-bold text-emerald-400">Fix Recommendation: </span>
                              {f.recommendation}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                )}

                {/* AI Review Report Tab */}
                {activeTab === "report" && (
                  <div className="rounded-lg border border-border/60 bg-muted/20 p-4 font-mono text-xs whitespace-pre-wrap leading-relaxed text-foreground">
                    {reviewDetail.review}
                  </div>
                )}

                {/* Code Diff Tab */}
                {activeTab === "diff" && (
                  <div className="rounded-lg border border-border/60 bg-black/80 text-foreground p-3 font-mono text-xs overflow-x-auto whitespace-pre leading-relaxed">
                    {reviewDetail.code_diff}
                  </div>
                )}

                {/* Injected Memories Tab */}
                {activeTab === "memories" && (
                  <div className="space-y-3">
                    <div className="rounded-md border border-purple-500/30 bg-purple-950/20 p-3 text-xs text-purple-300 space-y-1">
                      <p className="font-semibold flex items-center gap-1.5">
                        <BrainCircuit className="h-4 w-4" />
                        Memory Provenance Ledger
                      </p>
                      <p className="text-[11px] text-purple-300/80">
                        These guidelines, rules, and facts were actively recalled from Hindsight Cloud memory banks and injected into Groq to steer this review.
                      </p>
                    </div>

                    {reviewDetail.memories.length === 0 ? (
                      <p className="text-xs text-muted-foreground text-center py-8">
                        No prior memories were injected into this review session.
                      </p>
                    ) : (
                      reviewDetail.memories.map((m, idx) => (
                        <div
                          key={m.id || idx}
                          className="rounded-lg border border-border/60 bg-card p-3 space-y-2 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <Badge
                              variant="outline"
                              className="text-[10px] text-purple-400 border-purple-500/30"
                            >
                              {m.relevance_metadata?.source || "hindsight_recall"}
                            </Badge>
                            {m.hindsight_memory_id && (
                              <span className="text-[10px] font-mono text-muted-foreground">
                                Hindsight ID: {m.hindsight_memory_id.substring(0, 10)}...
                              </span>
                            )}
                          </div>
                          <p className="text-foreground font-medium leading-relaxed">
                            {m.memory_text}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

