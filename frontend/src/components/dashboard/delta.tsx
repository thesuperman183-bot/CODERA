"use client";

import React, { createContext, useContext } from "react";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { ArrowDown, ArrowUp, Minus, TrendingDown, TrendingUp } from "lucide-react";

type DeltaVariant = "default" | "badge";
type DeltaIconVariant = "default" | "trend" | "arrow";

interface DeltaContextType {
  value: number;
  variant: DeltaVariant;
}

const DeltaContext = createContext<DeltaContextType>({
  value: 0,
  variant: "default",
});

export function Delta({
  value,
  variant = "default",
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & {
  value: number;
  variant?: DeltaVariant;
}) {
  return (
    <DeltaContext.Provider value={{ value, variant }}>
      {variant === "badge" ? (
        <Badge
          variant="secondary"
          className={cn(
            "gap-1 font-medium",
            value >= 0
              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
              : "bg-red-500/10 text-red-600 dark:text-red-400",
            className
          )}
        >
          {children}
        </Badge>
      ) : (
        <div
          className={cn(
            "inline-flex items-center gap-1 font-medium text-xs",
            value > 0 ? "text-emerald-600 dark:text-emerald-400" : "",
            value < 0 ? "text-red-600 dark:text-red-400" : "text-muted-foreground",
            className
          )}
          {...props}
        >
          {children}
        </div>
      )}
    </DeltaContext.Provider>
  );
}

export function DeltaIcon({
  variant = "default",
  className,
}: {
  variant?: DeltaIconVariant;
  className?: string;
}) {
  const { value } = useContext(DeltaContext);
  const size = "h-3.5 w-3.5 shrink-0";

  if (value === 0) {
    return <Minus className={cn(size, className)} />;
  }

  if (value > 0) {
    if (variant === "trend") return <TrendingUp className={cn(size, className)} />;
    if (variant === "arrow") return <ArrowUp className={cn(size, className)} />;
    return <ArrowUp className={cn(size, className)} />;
  }

  if (variant === "trend") return <TrendingDown className={cn(size, className)} />;
  if (variant === "arrow") return <ArrowDown className={cn(size, className)} />;
  return <ArrowDown className={cn(size, className)} />;
}

export function DeltaValue({
  precision = 1,
  suffix = "%",
  className,
}: {
  precision?: number;
  suffix?: string;
  className?: string;
}) {
  const { value } = useContext(DeltaContext);
  const formatted = Math.abs(value).toFixed(precision);
  return (
    <span className={cn("tabular-nums", className)}>
      {value > 0 ? `+${formatted}` : value < 0 ? `-${formatted}` : formatted}
      {suffix}
    </span>
  );
}

