"use client";

import React, { createContext, useContext, useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { AlertCircle, CheckCircle2, Info, X, XCircle } from "lucide-react";

type NotificationType = "success" | "error" | "info" | "warning";

interface Notification {
  id: string;
  title: string;
  message?: string;
  type: NotificationType;
}

interface NotificationContextType {
  notify: (title: string, message?: string, type?: NotificationType) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
}

const NotificationContext = createContext<NotificationContextType>({
  notify: () => {},
  success: () => {},
  error: () => {},
});

export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const remove = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const notify = useCallback(
    (title: string, message?: string, type: NotificationType = "info") => {
      const id = Math.random().toString(36).substring(2, 9);
      setNotifications((prev) => [...prev, { id, title, message, type }]);
      setTimeout(() => {
        remove(id);
      }, 5000);
    },
    [remove]
  );

  const success = useCallback(
    (title: string, message?: string) => notify(title, message, "success"),
    [notify]
  );

  const error = useCallback(
    (title: string, message?: string) => notify(title, message, "error"),
    [notify]
  );

  return (
    <NotificationContext.Provider value={{ notify, success, error }}>
      {children}
      {/* Toast container */}
      <div className="fixed bottom-4 right-4 z-50 flex flex-col space-y-2 w-full max-w-sm pointer-events-none">
        {notifications.map((n) => (
          <div
            key={n.id}
            className={cn(
              "pointer-events-auto flex items-start gap-3 rounded-xl border p-4 shadow-lg backdrop-blur-md transition-all animate-in slide-in-from-bottom-5",
              n.type === "success" &&
                "bg-emerald-950/80 border-emerald-500/30 text-emerald-200",
              n.type === "error" &&
                "bg-red-950/80 border-red-500/30 text-red-200",
              n.type === "warning" &&
                "bg-amber-950/80 border-amber-500/30 text-amber-200",
              n.type === "info" &&
                "bg-card border-border text-card-foreground"
            )}
          >
            {n.type === "success" && (
              <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
            )}
            {n.type === "error" && (
              <XCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
            )}
            {n.type === "warning" && (
              <AlertCircle className="h-5 w-5 text-amber-400 shrink-0 mt-0.5" />
            )}
            {n.type === "info" && (
              <Info className="h-5 w-5 text-blue-400 shrink-0 mt-0.5" />
            )}
            <div className="flex-1 text-sm">
              <p className="font-semibold">{n.title}</p>
              {n.message && (
                <p className="mt-0.5 text-xs opacity-90">{n.message}</p>
              )}
            </div>
            <button
              onClick={() => remove(n.id)}
              className="opacity-70 hover:opacity-100 transition-opacity"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        ))}
      </div>
    </NotificationContext.Provider>
  );
}

export const useNotification = () => useContext(NotificationContext);

