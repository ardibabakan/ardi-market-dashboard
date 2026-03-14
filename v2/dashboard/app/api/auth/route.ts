import { NextResponse } from "next/server";

export async function POST(request: Request) {
  const { password } = await request.json();

  if (password === (process.env.DASHBOARD_PASSWORD || "ardi2026")) {
    const response = NextResponse.json({ success: true });
    response.cookies.set("ardi_auth", "authenticated", {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      maxAge: 60 * 60 * 24 * 30,
    });
    return response;
  }

  return NextResponse.json({ success: false }, { status: 401 });
}
