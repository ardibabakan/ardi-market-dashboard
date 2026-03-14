"use client";

import { AlertTriangle, CheckCircle, Info } from "lucide-react";

interface ActionBannerProps {
  action: string;
}

export default function ActionBanner({ action }: ActionBannerProps) {
  const isBuy = action.toUpperCase().includes("BUY");
  const isSell = action.toUpperCase().includes("SELL");

  const bgColor = isBuy
    ? "bg-profit/10 border-profit/30"
    : isSell
      ? "bg-loss/10 border-loss/30"
      : "bg-info/10 border-info/30";

  const Icon = isBuy ? CheckCircle : isSell ? AlertTriangle : Info;
  const iconColor = isBuy ? "text-profit" : isSell ? "text-loss" : "text-info";

  return (
    <div
      className={`max-w-7xl mx-auto mx-3 mt-2 px-3 py-2 border rounded-lg ${bgColor}`}
    >
      <div className="flex items-start gap-2">
        <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${iconColor}`} />
        <p className="text-sm font-medium leading-snug">{action}</p>
      </div>
    </div>
  );
}
