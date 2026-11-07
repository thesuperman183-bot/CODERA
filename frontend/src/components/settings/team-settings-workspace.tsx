"use client";

import React, { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { apiClient } from "@/lib/api";
import { useAuth } from "@/lib/auth-context";
import { useNotification } from "@/components/ui/notifications";
import {
  AlertCircle,
  Bot,
  Brain,
  BrainCircuit,
  Check,
  CheckCircle,
  Clock,
  Copy,
  Cpu,
  Crown,
  Key,
  Layers,
  Loader2,
  Mail,
  Plus,
  RefreshCw,
  Scale,
  Settings,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserCheck,
  UserPlus,
  Users,
  X,
} from "lucide-react";

interface TeamItem {
  id: string;
  name: string;
  role: string;
  member_count: number;
  created_at: string;
}

interface TeamMember {
  user_id: string;
  email: string;
  name?: string;
  role: string;
  joined_at?: string;
}

interface TeamRule {
  id: string;
  rule_text: string;
  hindsight_memory_id?: string;
  created_by?: string;
  creator_name?: string;
  created_at: string;
}

interface ActiveBank {
  bank_id: string;
  bank_type: string;
  status: string;
  is_active: boolean;
}

interface ModelConfig {
  model: string;
  provider: string;
  temperature: number;
  max_tokens: number;
}

interface TeamSettingsData {
  team_id: string;
  team_name: string;
  current_user_role: string;
  can_manage: boolean;
  members: TeamMember[];
  rules: TeamRule[];
  active_hindsight_bank: ActiveBank;
  ai_model_config?: ModelConfig;
  model_config?: ModelConfig;
  cli_instructions: Record<string, string>;
}

export function TeamSettingsWorkspace() {
  const { user, activeTeamId, setActiveTeamId } = useAuth();
  const { success, error } = useNotification();

  // Teams list
  const [teams, setTeams] = useState<TeamItem[]>([]);
  const [selectedTeamId, setSelectedTeamId] = useState<string>(activeTeamId || "");
  const [loadingTeams, setLoadingTeams] = useState(true);

  // Active team settings
  const [settings, setSettings] = useState<TeamSettingsData | null>(null);
  const [loadingSettings, setLoadingSettings] = useState(false);

  // Form states for Team Settings edit
  const [teamNameInput, setTeamNameInput] = useState("");
  const [bankIdInput, setBankIdInput] = useState("");
  const [savingSettings, setSavingSettings] = useState(false);

  // Invite member dialog
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState("member");
  const [inviting, setInviting] = useState(false);

  // Add rule dialog
  const [addRuleOpen, setAddRuleOpen] = useState(false);
  const [newRuleText, setNewRuleText] = useState("");
  const [addingRule, setAddingRule] = useState(false);

  // Copied state tracker for CLI snippets
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Fetch teams list
  const fetchTeams = async () => {
    setLoadingTeams(true);
    try {
      const data = await apiClient.teams.list();
      setTeams(data || []);
      if (data && data.length > 0 && !selectedTeamId) {
        setSelectedTeamId(data[0].id);
        if (!activeTeamId) setActiveTeamId(data[0].id);
      }
    } catch {
      // Fallback team
      setTeams([
        {
          id: "team-default-01",
          name: "Engineering Core",
          role: "owner",
          member_count: 3,
          created_at: new Date().toISOString(),
        },
      ]);
      if (!selectedTeamId) setSelectedTeamId("team-default-01");
    } finally {
      setLoadingTeams(false);
    }
  };

  // Fetch settings for selected team
  const fetchTeamSettings = async (teamId: string) => {
    if (!teamId) return;
    setLoadingSettings(true);
    try {
      const data = await apiClient.teams.settings(teamId);
      setSettings(data);
      setTeamNameInput(data.team_name || "");
      setBankIdInput(data.active_hindsight_bank?.bank_id || "");
    } catch (err: any) {
      error("Failed to fetch team settings", err.message || "Failed to load team workspace");
    } finally {
      setLoadingSettings(false);
    }
  };

  useEffect(() => {
    fetchTeams();
  }, []);

  useEffect(() => {
    if (selectedTeamId) {
      fetchTeamSettings(selectedTeamId);
    }
  }, [selectedTeamId]);

  const handleUpdateSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings?.can_manage) {
      error("Access Denied", "Requires Owner or Admin role to modify team settings");
      return;
    }

    setSavingSettings(true);
    try {
      await apiClient.teams.updateSettings(selectedTeamId, {
        name: teamNameInput.trim(),
        hindsight_bank_id: bankIdInput.trim(),
      });
      success("Settings Saved", "Team configuration updated in Neon");
      fetchTeamSettings(selectedTeamId);
      fetchTeams();
    } catch (err: any) {
      error("Update Failed", err.message || "FastAPI rejected the update request");
    } finally {
      setSavingSettings(false);
    }
  };

  const handleInviteMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;

    setInviting(true);
    try {
      await apiClient.teams.inviteMember(selectedTeamId, {
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      success("Member Added", `Successfully invited ${inviteEmail} as ${inviteRole}`);
      setInviteOpen(false);
      setInviteEmail("");
      setInviteRole("member");
      fetchTeamSettings(selectedTeamId);
    } catch (err: any) {
      error("Invite Failed", err.message || "Could not add team member");
    } finally {
      setInviting(false);
    }
  };

  const handleRoleChange = async (userId: string, newRole: string) => {
    try {
      await apiClient.teams.updateMemberRole(selectedTeamId, userId, newRole);
      success("Role Updated", `Member role updated to ${newRole}`);
      fetchTeamSettings(selectedTeamId);
    } catch (err: any) {
      error("Failed to Update Role", err.message || "Action unauthorized or invalid");
    }
  };

  const handleRemoveMember = async (userId: string, memberEmail: string) => {
    if (!confirm(`Are you sure you want to remove ${memberEmail} from this team?`)) return;

    try {
      await apiClient.teams.removeMember(selectedTeamId, userId);
      success("Member Removed", `${memberEmail} has been removed from the team`);
      fetchTeamSettings(selectedTeamId);
    } catch (err: any) {
      error("Removal Failed", err.message || "Could not remove member");
    }
  };

  const handleAddRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRuleText.trim()) return;

    setAddingRule(true);
    try {
      await apiClient.teamRules.create(newRuleText.trim(), selectedTeamId);
      success("Rule Added", "Rule saved in Neon and retained in Hindsight Cloud");
      setAddRuleOpen(false);
      setNewRuleText("");
      fetchTeamSettings(selectedTeamId);
    } catch (err: any) {
      error("Failed to Add Rule", err.message || "Action unauthorized or invalid");
    } finally {
      setAddingRule(false);
    }
  };

  const handleDeleteRule = async (ruleId: string) => {
    if (!confirm("Are you sure you want to delete this team rule?")) return;

    try {
      await apiClient.teams.deleteRule(selectedTeamId, ruleId);
      success("Rule Deleted", "Rule permanently removed from Neon");
      fetchTeamSettings(selectedTeamId);
    } catch (err: any) {
      error("Failed to Delete Rule", err.message || "Action unauthorized");
    }
  };

  const copySnippet = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    success("Copied to Clipboard", text);
    setTimeout(() => setCopiedKey(null), 2500);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-border/40 pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight">Team Settings</h1>
            <Badge variant="outline" className="gap-1 text-primary border-primary/30 text-[11px]">
              <ShieldCheck className="h-3 w-3" />
              Role-Based Authorization
            </Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">
            Configure collaborative team workspaces, member roles, coding rules, memory banks, and terminal CLI integration.
          </p>
        </div>

        {/* Team Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground font-medium">Active Team:</span>
          <select
            value={selectedTeamId}
            onChange={(e) => {
              setSelectedTeamId(e.target.value);
              setActiveTeamId(e.target.value);
            }}
            disabled={loadingTeams || teams.length === 0}
            className="h-8 rounded-md border border-input bg-background px-3 text-xs font-semibold focus:outline-hidden"
          >
            {teams.map((t) => (
              <option key={t.id} value={t.id}>
                {t.name} ({t.role})
              </option>
            ))}
          </select>

          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              fetchTeams();
              if (selectedTeamId) fetchTeamSettings(selectedTeamId);
            }}
            className="h-8 w-8 p-0"
            title="Refresh settings"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loadingSettings ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Role Banner if Member */}
      {settings && !settings.can_manage && (
        <div className="flex items-center gap-2.5 rounded-lg border border-amber-500/30 bg-amber-950/20 px-3.5 py-2.5 text-xs text-amber-300">
          <AlertCircle className="h-4 w-4 shrink-0 text-amber-400" />
          <span>
            You are signed in with <strong>Member</strong> privileges for <strong>{settings.team_name}</strong>. Only Team Owners and Admins have permission to invite members, change roles, or configure team settings.
          </span>
        </div>
      )}

      {loadingSettings && !settings ? (
        <div className="flex flex-col items-center justify-center py-20 gap-2">
          <Loader2 className="h-7 w-7 animate-spin text-primary" />
          <p className="text-xs text-muted-foreground">Loading workspace settings from Neon...</p>
        </div>
      ) : settings ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Card 1: Workspace Settings */}
          <Card className="border border-border/80 shadow-xs">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <Settings className="h-4 w-4 text-primary" />
                  Workspace Configuration
                </CardTitle>
                <Badge
                  className={
                    settings.current_user_role === "owner"
                      ? "bg-purple-500/20 text-purple-400 border border-purple-500/40"
                      : settings.current_user_role === "admin"
                      ? "bg-blue-500/20 text-blue-400 border border-blue-500/40"
                      : "bg-slate-500/20 text-slate-300 border border-slate-500/40"
                  }
                >
                  {settings.current_user_role.toUpperCase()}
                </Badge>
              </div>
              <CardDescription className="text-xs">
                Manage team identification and active Hindsight vector memory bank.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleUpdateSettings} className="space-y-4">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-foreground">Team Workspace Name</label>
                  <Input
                    value={teamNameInput}
                    onChange={(e) => setTeamNameInput(e.target.value)}
                    disabled={!settings.can_manage || savingSettings}
                    placeholder="Engineering Core Team"
                    className="h-8 text-xs"
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-foreground flex items-center gap-1.5">
                      <Brain className="h-3.5 w-3.5 text-purple-400" />
                      Active Hindsight Memory Bank ID
                    </label>
                    <span className="text-[10px] text-muted-foreground">
                      Status: {settings.active_hindsight_bank.status}
                    </span>
                  </div>
                  <Input
                    value={bankIdInput}
                    onChange={(e) => setBankIdInput(e.target.value)}
                    disabled={!settings.can_manage || savingSettings}
                    placeholder="team-bank-id"
                    className="h-8 text-xs font-mono"
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Reviews submitted by members of this team will automatically recall and retain guidelines from this bank.
                  </p>
                </div>

                {settings.can_manage && (
                  <Button type="submit" size="sm" disabled={savingSettings} className="text-xs h-8">
                    {savingSettings ? "Saving Changes..." : "Save Workspace Settings"}
                  </Button>
                )}
              </form>
            </CardContent>
          </Card>

          {/* Card 2: Model Configuration */}
          <Card className="border border-border/80 shadow-xs">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Cpu className="h-4 w-4 text-primary" />
                Model & Inference Configuration
              </CardTitle>
              <CardDescription className="text-xs">
                AI model parameters utilized across CLI and Web review pipelines.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3.5">
              {(() => {
                const mc = settings.ai_model_config || settings.model_config || {
                  provider: "Groq",
                  model: "llama-3.3-70b-versatile",
                  temperature: 0.1,
                  max_tokens: 4096,
                };
                return (
                  <div className="rounded-lg border border-border/60 bg-muted/30 p-3 space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Provider:</span>
                      <Badge variant="outline" className="font-semibold text-[11px]">
                        {mc.provider} Cloud
                      </Badge>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Review Model:</span>
                      <span className="font-mono text-emerald-400 font-medium">
                        {mc.model}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Inference Temperature:</span>
                      <span className="font-mono">{mc.temperature} (Deterministic)</span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Max Output Tokens:</span>
                      <span className="font-mono">{mc.max_tokens} tokens</span>
                    </div>
                  </div>
                );
              })()}

              <div className="rounded-md border border-emerald-500/20 bg-emerald-950/20 p-2.5 text-xs text-emerald-300 flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-emerald-400 shrink-0" />
                <span>High-throughput LPUs with sub-second time-to-first-token enabled.</span>
              </div>
            </CardContent>
          </Card>

          {/* Card 3: Team Members & RBAC */}
          <Card className="border border-border/80 shadow-xs lg:col-span-2">
            <CardHeader className="pb-3">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Users className="h-4 w-4 text-primary" />
                    Team Members ({settings.members.length})
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Assign role-based access control (Owner, Admin, Member) to control who can manage rules and workspace settings.
                  </CardDescription>
                </div>

                {settings.can_manage && (
                  <Button
                    size="sm"
                    onClick={() => setInviteOpen(true)}
                    className="gap-1.5 text-xs h-8"
                  >
                    <UserPlus className="h-3.5 w-3.5" />
                    Invite Member
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow className="hover:bg-transparent">
                      <TableHead>Member</TableHead>
                      <TableHead>Email</TableHead>
                      <TableHead className="w-[140px]">Role</TableHead>
                      <TableHead className="w-[160px]">Joined</TableHead>
                      {settings.can_manage && (
                        <TableHead className="text-right w-[140px]">Actions</TableHead>
                      )}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {settings.members.map((m) => (
                      <TableRow key={m.user_id} className="hover:bg-muted/40">
                        <TableCell>
                          <div className="flex items-center gap-2.5">
                            <div className="h-7 w-7 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs uppercase">
                              {(m.name || m.email)[0]}
                            </div>
                            <span className="font-medium text-xs text-foreground">
                              {m.name || m.email.split("@")[0]}
                            </span>
                            {m.user_id === user?.id && (
                              <Badge variant="outline" className="text-[10px] py-0 px-1 text-muted-foreground">
                                You
                              </Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {m.email}
                        </TableCell>
                        <TableCell>
                          {settings.can_manage && m.role !== "owner" && settings.current_user_role === "owner" ? (
                            <select
                              value={m.role}
                              onChange={(e) => handleRoleChange(m.user_id, e.target.value)}
                              className="h-6 rounded border border-input bg-background px-1.5 text-[11px] font-medium"
                            >
                              <option value="admin">Admin</option>
                              <option value="member">Member</option>
                            </select>
                          ) : (
                            <Badge
                              className={`capitalize text-[10px] ${
                                m.role === "owner"
                                  ? "bg-purple-500/20 text-purple-400 border border-purple-500/30"
                                  : m.role === "admin"
                                  ? "bg-blue-500/20 text-blue-400 border border-blue-500/30"
                                  : "bg-slate-500/20 text-slate-300 border border-slate-500/30"
                              }`}
                            >
                              {m.role === "owner" && <Crown className="h-2.5 w-2.5 mr-1 inline" />}
                              {m.role}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground font-mono">
                          {m.joined_at ? new Date(m.joined_at).toLocaleDateString() : "Active"}
                        </TableCell>
                        {settings.can_manage && (
                          <TableCell className="text-right">
                            {m.role !== "owner" && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleRemoveMember(m.user_id, m.email)}
                                className="h-7 text-xs text-red-400 hover:text-red-300 hover:bg-red-950/20 gap-1 px-2"
                              >
                                <Trash2 className="h-3 w-3" />
                                Remove
                              </Button>
                            )}
                          </TableCell>
                        )}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {/* Card 4: Team Rules Management */}
          <Card className="border border-border/80 shadow-xs lg:col-span-2">
            <CardHeader className="pb-3">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                  <CardTitle className="text-base font-semibold flex items-center gap-2">
                    <Scale className="h-4 w-4 text-primary" />
                    Team Coding Rules ({settings.rules.length})
                  </CardTitle>
                  <CardDescription className="text-xs">
                    Persistent organizational rules stored in Neon and retained in Hindsight for automated enforcement.
                  </CardDescription>
                </div>

                {settings.can_manage && (
                  <Button
                    size="sm"
                    onClick={() => setAddRuleOpen(true)}
                    className="gap-1.5 text-xs h-8"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Add Team Rule
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {settings.rules.length === 0 ? (
                <div className="text-center py-12 px-4 text-xs text-muted-foreground space-y-1.5">
                  <p className="font-medium text-foreground">No team rules configured yet</p>
                  <p>Add coding rules like architectural patterns, security requirements, and style guides.</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow className="hover:bg-transparent">
                        <TableHead>Rule Guideline</TableHead>
                        <TableHead className="w-[160px]">Created By</TableHead>
                        <TableHead className="w-[140px]">Date</TableHead>
                        {settings.can_manage && (
                          <TableHead className="text-right w-[100px]">Actions</TableHead>
                        )}
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {settings.rules.map((r) => (
                        <TableRow key={r.id} className="hover:bg-muted/40">
                          <TableCell className="text-xs font-medium leading-relaxed">
                            {r.rule_text}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground">
                            {r.creator_name || "System"}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground font-mono">
                            {new Date(r.created_at).toLocaleDateString()}
                          </TableCell>
                          {settings.can_manage && (
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeleteRule(r.id)}
                                className="h-7 text-xs text-red-400 hover:text-red-300 hover:bg-red-950/20 px-2"
                                title="Delete Rule"
                              >
                                <Trash2 className="h-3 w-3" />
                              </Button>
                            </TableCell>
                          )}
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Card 5: CLI Connection Instructions */}
          <Card className="border border-border/80 shadow-xs lg:col-span-2">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Key className="h-4 w-4 text-primary" />
                CLI Connection & Terminal Authentication Instructions
              </CardTitle>
              <CardDescription className="text-xs">
                How team members connect the Python CLI to this team workspace and active Hindsight bank.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Step 1: Login */}
                <div className="rounded-lg border border-border/60 bg-muted/20 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground">1. Authenticate CLI</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() =>
                        copySnippet(settings.cli_instructions.login || `review-agent login --email ${user?.email}`, "login")
                      }
                    >
                      {copiedKey === "login" ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                    </Button>
                  </div>
                  <div className="rounded bg-black/80 text-emerald-400 p-2 font-mono text-[11px] overflow-x-auto">
                    {settings.cli_instructions.login || `review-agent login --email ${user?.email}`}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Stores Personal Access Token securely in macOS Keychain, Linux Secret Service, or Windows Vault.
                  </p>
                </div>

                {/* Step 2: Verify identity & team */}
                <div className="rounded-lg border border-border/60 bg-muted/20 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground">2. Verify Workspace</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() => copySnippet(settings.cli_instructions.whoami || "review-agent whoami", "whoami")}
                    >
                      {copiedKey === "whoami" ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                    </Button>
                  </div>
                  <div className="rounded bg-black/80 text-emerald-400 p-2 font-mono text-[11px] overflow-x-auto">
                    {settings.cli_instructions.whoami || "review-agent whoami"}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Prints current user email, roles, and verified team associations.
                  </p>
                </div>

                {/* Step 3: Check diff */}
                <div className="rounded-lg border border-border/60 bg-muted/20 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground">3. Submit Diff for Review</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() => copySnippet(settings.cli_instructions.check || "review-agent check feature.diff", "check")}
                    >
                      {copiedKey === "check" ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                    </Button>
                  </div>
                  <div className="rounded bg-black/80 text-emerald-400 p-2 font-mono text-[11px] overflow-x-auto">
                    {settings.cli_instructions.check || "review-agent check feature.diff"}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Automatically persists review in Neon and links it to this team.
                  </p>
                </div>

                {/* Step 4: Teach rule */}
                <div className="rounded-lg border border-border/60 bg-muted/20 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-foreground">4. Retain Guidelines (CLI)</span>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-6 w-6"
                      onClick={() =>
                        copySnippet(
                          settings.cli_instructions.learn || 'review-agent learn "All API endpoints must validate input schemas."',
                          "learn"
                        )
                      }
                    >
                      {copiedKey === "learn" ? <Check className="h-3 w-3 text-emerald-400" /> : <Copy className="h-3 w-3" />}
                    </Button>
                  </div>
                  <div className="rounded bg-black/80 text-emerald-400 p-2 font-mono text-[11px] overflow-x-auto">
                    {settings.cli_instructions.learn || 'review-agent learn "All API endpoints must validate input schemas."'}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    Authorized owners and admins can push rules directly from terminal workflows.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* Invite Member Dialog */}
      <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold flex items-center gap-2">
              <UserPlus className="h-4 w-4 text-primary" />
              Invite Team Member
            </DialogTitle>
            <DialogDescription className="text-xs">
              Add a teammate to <strong>{settings?.team_name}</strong> by email address and assign an initial role.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleInviteMember} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground">Teammate Email Address</label>
              <Input
                type="email"
                required
                placeholder="colleague@company.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                className="h-8 text-xs"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground">Team Role</label>
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="w-full h-8 rounded-md border border-input bg-background px-3 text-xs focus:outline-hidden"
              >
                <option value="member">Member (Can review code and view rules)</option>
                <option value="admin">Admin (Can manage rules, invite members, configure settings)</option>
              </select>
            </div>

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setInviteOpen(false)} className="text-xs">
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={inviting} className="text-xs">
                {inviting ? "Inviting..." : "Send Invitation"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Add Team Rule Dialog */}
      <Dialog open={addRuleOpen} onOpenChange={setAddRuleOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="text-base font-semibold flex items-center gap-2">
              <Scale className="h-4 w-4 text-primary" />
              Add Team Rule
            </DialogTitle>
            <DialogDescription className="text-xs">
              Save a new coding guideline to Neon and retain it in Hindsight Cloud memory.
            </DialogDescription>
          </DialogHeader>

          <form onSubmit={handleAddRule} className="space-y-4 pt-2">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground">Guideline or Rule Statement</label>
              <textarea
                required
                rows={3}
                placeholder="e.g. Always sanitize HTML inputs before rendering to prevent XSS vulnerabilities."
                value={newRuleText}
                onChange={(e) => setNewRuleText(e.target.value)}
                className="w-full rounded-md border border-input bg-background p-2 text-xs focus:outline-hidden leading-relaxed"
              />
            </div>

            <DialogFooter className="pt-2">
              <Button type="button" variant="outline" size="sm" onClick={() => setAddRuleOpen(false)} className="text-xs">
                Cancel
              </Button>
              <Button type="submit" size="sm" disabled={addingRule} className="text-xs">
                {addingRule ? "Saving..." : "Add Rule"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
