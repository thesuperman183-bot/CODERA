import React from "react";
import type { Metadata } from "next";
import "./globals.css";
import { AuthProvider } from "@/lib/auth-context";
import { NotificationProvider } from "@/components/ui/notifications";
import { AppShell } from "@/components/layout/app-shell";

export const metadata: Metadata = {
  title: "CODERA - AI Code Review",
  description: "CODERA: AI-powered Code Review Agent with Neon PostgreSQL and Hindsight Memory Integration",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Fredoka:wght@600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="font-sans antialiased bg-background text-foreground">
        <AuthProvider>
          <NotificationProvider>
            <AppShell>{children}</AppShell>
          </NotificationProvider>
        </AuthProvider>
      </body>
    </html>
  );
}

