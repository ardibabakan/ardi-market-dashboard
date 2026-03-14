"use client";

import {
  BarChart3,
  AlertTriangle,
  Search,
  Activity,
  Bitcoin,
  Globe,
  ShieldAlert,
  Settings,
} from "lucide-react";
import type { TabId } from "@/app/types";
import clsx from "clsx";

interface TabNavProps {
  activeTab: TabId;
  onTabChange: (tab: TabId) => void;
}

const TABS: { id: TabId; label: string; icon: React.ElementType }[] = [
  { id: "stocks", label: "My Stocks", icon: BarChart3 },
  { id: "signals", label: "War Signals", icon: AlertTriangle },
  { id: "opportunities", label: "Opportunities", icon: Search },
  { id: "technical", label: "Technical", icon: Activity },
  { id: "crypto", label: "My Crypto", icon: Bitcoin },
  { id: "events", label: "World Events", icon: Globe },
  { id: "risk", label: "Risk", icon: ShieldAlert },
  { id: "system", label: "System", icon: Settings },
];

export default function TabNav({ activeTab, onTabChange }: TabNavProps) {
  return (
    <nav className="sticky top-[49px] z-40 bg-bg/90 backdrop-blur border-b border-bg-elevated">
      <div className="max-w-7xl mx-auto overflow-x-auto scrollbar-hide">
        <div className="flex gap-1 px-3 py-1.5 min-w-max">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              onClick={() => onTabChange(id)}
              className={clsx(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap",
                activeTab === id
                  ? "bg-bg-elevated text-txt"
                  : "text-txt-muted hover:text-txt-secondary hover:bg-bg-surface"
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>
    </nav>
  );
}
