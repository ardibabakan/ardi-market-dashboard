"use client";

import { useState, useEffect, useCallback } from "react";
import type {
  DashboardSnapshot,
  SignalRow,
  EventRow,
  FallenAngelRow,
  RealtimeResponse,
  TabId,
} from "@/app/types";
import {
  getDashboardState,
  getSignals,
  getEvents,
  getFallenAngels,
  getAgentRuns,
} from "@/app/lib/supabase";

import LoginGate from "@/app/components/LoginGate";
import Header from "@/app/components/Header";
import ActionBanner from "@/app/components/ActionBanner";
import TabNav from "@/app/components/TabNav";
import MyStocksTab from "@/app/components/MyStocksTab";
import WarSignalsTab from "@/app/components/WarSignalsTab";
import OpportunitiesTab from "@/app/components/OpportunitiesTab";
import TechnicalTab from "@/app/components/TechnicalTab";
import CryptoTab from "@/app/components/CryptoTab";
import EventsTab from "@/app/components/EventsTab";
import RiskTab from "@/app/components/RiskTab";
import SystemTab from "@/app/components/SystemTab";

const REFRESH_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes

export default function Home() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [signals, setSignals] = useState<SignalRow[]>([]);
  const [events, setEvents] = useState<EventRow[]>([]);
  const [fallenAngels, setFallenAngels] = useState<FallenAngelRow[]>([]);
  const [agentRuns, setAgentRuns] = useState<unknown[]>([]);
  const [realtimePrices, setRealtimePrices] =
    useState<RealtimeResponse | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("stocks");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  // ── Auth check ──
  useEffect(() => {
    fetch("/api/auth/check")
      .then((r) => r.json())
      .then((d) => setAuthenticated(d.authenticated))
      .catch(() => setAuthenticated(false));
  }, []);

  // ── Data fetching ──
  const fetchAllData = useCallback(async () => {
    try {
      setError(null);
      const [dashState, sigs, evts, angels, runs] = await Promise.all([
        getDashboardState().catch(() => null),
        getSignals().catch(() => []),
        getEvents().catch(() => []),
        getFallenAngels().catch(() => []),
        getAgentRuns().catch(() => []),
      ]);

      if (dashState?.data) {
        setSnapshot(dashState.data as DashboardSnapshot);
      }
      setSignals(sigs as SignalRow[]);
      setEvents(evts as EventRow[]);
      setFallenAngels(angels as FallenAngelRow[]);
      setAgentRuns(runs);
      setLastRefresh(new Date());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to fetch dashboard data"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchRealtimePrices = useCallback(async () => {
    try {
      const res = await fetch("/api/realtime");
      if (res.ok) {
        const data: RealtimeResponse = await res.json();
        setRealtimePrices(data);
      }
    } catch {
      // non-critical; ignore
    }
  }, []);

  useEffect(() => {
    if (authenticated !== true) return;

    fetchAllData();
    fetchRealtimePrices();

    const dataInterval = setInterval(fetchAllData, REFRESH_INTERVAL_MS);
    const priceInterval = setInterval(fetchRealtimePrices, REFRESH_INTERVAL_MS);

    return () => {
      clearInterval(dataInterval);
      clearInterval(priceInterval);
    };
  }, [authenticated, fetchAllData, fetchRealtimePrices]);

  // ── Auth gate ──
  if (authenticated === null) {
    return <LoadingSkeleton />;
  }

  if (!authenticated) {
    return <LoginGate onSuccess={() => setAuthenticated(true)} />;
  }

  // ── Loading state ──
  if (loading) {
    return <LoadingSkeleton />;
  }

  // ── Error state ──
  if (error && !snapshot) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="card max-w-md w-full text-center">
          <p className="text-loss text-lg font-semibold mb-2">
            Connection Error
          </p>
          <p className="text-txt-secondary text-sm mb-4">{error}</p>
          <button
            onClick={() => {
              setLoading(true);
              fetchAllData();
            }}
            className="px-4 py-2 bg-info rounded-lg text-sm font-medium hover:opacity-90 transition-opacity"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  // ── Render active tab ──
  const renderTab = () => {
    switch (activeTab) {
      case "stocks":
        return (
          <MyStocksTab
            snapshot={snapshot}
            realtimePrices={realtimePrices}
          />
        );
      case "signals":
        return <WarSignalsTab snapshot={snapshot} signals={signals} />;
      case "opportunities":
        return <OpportunitiesTab fallenAngels={fallenAngels} />;
      case "technical":
        return <TechnicalTab snapshot={snapshot} />;
      case "crypto":
        return <CryptoTab data={snapshot} />;
      case "events":
        return <EventsTab events={events} />;
      case "risk":
        return <RiskTab data={snapshot} />;
      case "system":
        return <SystemTab agentRuns={agentRuns} />;
      default:
        return null;
    }
  };

  return (
    <div className="min-h-screen bg-bg">
      <Header
        snapshot={snapshot}
        lastRefresh={lastRefresh}
        onRefresh={() => {
          fetchAllData();
          fetchRealtimePrices();
        }}
      />

      {snapshot?.action && <ActionBanner action={snapshot.action} />}

      <TabNav activeTab={activeTab} onTabChange={setActiveTab} />

      <main className="max-w-7xl mx-auto px-3 pb-24 pt-2">
        {error && (
          <div className="mb-3 px-3 py-2 bg-loss/10 border border-loss/30 rounded-lg text-loss text-xs">
            {error} — showing cached data
          </div>
        )}
        {renderTab()}
      </main>
    </div>
  );
}

// ── Skeleton loader ──
function LoadingSkeleton() {
  return (
    <div className="min-h-screen bg-bg flex flex-col items-center justify-center gap-4">
      <div className="w-10 h-10 border-2 border-info border-t-transparent rounded-full animate-spin" />
      <p className="text-txt-secondary text-sm">Loading Command Center...</p>
    </div>
  );
}
