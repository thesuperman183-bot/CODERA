"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import { useAuth } from "@/lib/auth-context";
import { Button } from "@/components/ui/button";
import {
  BookOpen,
  Bot,
  BrainCircuit,
  ChevronDown,
  Code2,
  FileCode,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  Scale,
  Settings,
  Shield,
  Users,
  X,
} from "lucide-react";

interface NavItem {
  title: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  badge?: string;
}

const NAV_ITEMS: NavItem[] = [
  {
    title: "Overview",
    href: "/",
    icon: LayoutDashboard,
  },
  {
    title: "Code Review",
    href: "/review",
    icon: Code2,
  },
  {
    title: "Hindsight Inspector",
    href: "/inspector",
    icon: BrainCircuit,
  },
  {
    title: "Review History",
    href: "/history",
    icon: History,
  },
  {
    title: "Team Rules",
    href: "/rules",
    icon: Scale,
  },
  {
    title: "Team Settings",
    href: "/settings",
    icon: Settings,
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { user, login, logout, activeTeamId, setActiveTeamId } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const activeTeam = user?.teams.find((t) => t.team_id === activeTeamId);

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {/* Desktop Sidebar */}
      <aside className="hidden md:flex w-64 flex-col border-r border-border bg-card/60 backdrop-blur-md">
        {/* Brand header */}
        <div className="flex h-16 items-center gap-3 border-b border-border px-6">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
            <Bot className="h-5 w-5" />
          </div>
          <div className="flex flex-col">
            <span className="font-brand font-bold text-lg tracking-tight leading-tight text-foreground">
              CODERA
            </span>
            <span className="text-[11px] text-muted-foreground font-sans">
              Neon + Hindsight AI
            </span>
          </div>
        </div>

        {/* Team Selector Widget */}
        <div className="border-b border-border p-4">
          <div className="flex items-center justify-between rounded-lg border border-border bg-accent/40 p-2.5 text-xs">
            <div className="flex items-center gap-2 overflow-hidden">
              <Users className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="truncate">
                <p className="font-medium truncate">
                  {activeTeam?.team_name || "Personal Workspace"}
                </p>
                <p className="text-[10px] text-muted-foreground capitalize">
                  {activeTeam?.role || "Owner"}
                </p>
              </div>
            </div>
            {user?.teams && user.teams.length > 1 && (
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            )}
          </div>
        </div>

        {/* Navigation list */}
        <nav className="flex-1 space-y-1.5 p-4">
          {NAV_ITEMS.map((item) => {
            const isActive =
              item.href === "/"
                ? pathname === "/"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-xs"
                    : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                )}
              >
                <Icon className={cn("h-4 w-4 shrink-0", isActive ? "text-primary-foreground" : "")} />
                <span>{item.title}</span>
                {item.badge && (
                  <span className="ml-auto rounded-full bg-secondary px-2 py-0.5 text-[10px] font-semibold text-secondary-foreground">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* User profile / logout footer */}
        <div className="border-t border-border p-4">
          {user ? (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5 overflow-hidden">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-xs font-medium text-primary">
                  {user.name ? user.name[0].toUpperCase() : "U"}
                </div>
                <div className="truncate">
                  <p className="text-xs font-semibold truncate leading-tight">
                    {user.name}
                  </p>
                  <p className="text-[11px] text-muted-foreground truncate leading-tight">
                    {user.email}
                  </p>
                </div>
              </div>
              <button
                onClick={logout}
                title="Log out"
                className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Guest Session</span>
              <button
                onClick={() => login("developer@example.com")}
                className="text-xs text-primary hover:underline font-medium"
              >
                Sign In
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main Content Viewport */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile Navbar Header */}
        <header className="flex h-16 items-center justify-between border-b border-border px-4 md:hidden bg-card">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <Bot className="h-4 w-4" />
            </div>
            <span className="font-brand font-bold text-lg text-foreground">CODERA</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </header>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 top-16 z-50 bg-background/95 backdrop-blur-md md:hidden p-6 flex flex-col justify-between">
            <nav className="space-y-2">
              {NAV_ITEMS.map((item) => {
                const isActive =
                  item.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileMenuOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-4 py-3 text-base font-medium transition-colors",
                      isActive
                        ? "bg-primary text-primary-foreground"
                        : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                    )}
                  >
                    <Icon className="h-5 w-5" />
                    <span>{item.title}</span>
                  </Link>
                );
              })}
            </nav>
            {user && (
              <div className="border-t border-border pt-4 flex items-center justify-between">
                <div>
                  <p className="font-medium text-sm">{user.name}</p>
                  <p className="text-xs text-muted-foreground">{user.email}</p>
                </div>
                <Button variant="outline" size="sm" onClick={logout}>
                  Log out
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Main Content Area */}
        <main className="flex-1 overflow-y-auto p-4 md:p-8">
          <div className="mx-auto max-w-7xl">{children}</div>
        </main>
      </div>
    </div>
  );
}

