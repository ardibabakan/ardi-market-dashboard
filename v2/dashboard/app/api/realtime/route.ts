import { NextResponse } from "next/server";
import type { RealtimePrice } from "@/app/types";

const FINNHUB_KEY = process.env.FINNHUB_API_KEY;
const TICKERS = [
  "LMT",
  "RTX",
  "LNG",
  "GLD",
  "ITA",
  "XOM",
  "CEG",
  "BAESY",
  "SPY",
  "DAL",
  "RCL",
];

export async function GET() {
  if (!FINNHUB_KEY) {
    return NextResponse.json({ error: "No API key" }, { status: 500 });
  }

  try {
    const prices: Record<string, RealtimePrice> = {};

    for (const ticker of TICKERS) {
      try {
        const res = await fetch(
          `https://finnhub.io/api/v1/quote?symbol=${ticker}&token=${FINNHUB_KEY}`
        );
        if (res.ok) {
          const d = await res.json();
          if (d.c && d.c > 0) {
            prices[ticker] = {
              price: d.c,
              change: d.d,
              changePct: d.dp,
              high: d.h,
              low: d.l,
              prevClose: d.pc,
            };
          }
        }
      } catch {
        // skip individual ticker failures
      }
      // Finnhub free tier: 60 calls/min
      await new Promise((r) => setTimeout(r, 1100));
    }

    return NextResponse.json({ prices, timestamp: new Date().toISOString() });
  } catch {
    return NextResponse.json({ error: "Fetch failed" }, { status: 500 });
  }
}

export const revalidate = 300;
