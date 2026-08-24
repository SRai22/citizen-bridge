import { randomUUID } from "node:crypto";

import { NextRequest, NextResponse } from "next/server";

import { proxyBackendRequest } from "../../_proxy";

interface RouteContext {
  params: Promise<{ path: string[] }>;
}

interface Session {
  answers: string[];
  profile?: IntakeProfile;
}

interface IntakeProfile {
  deceased: {
    name: string;
    relationship: string;
    occupation: string;
    pension_status: "active";
  };
  surviving_members: Array<{
    name: string;
    relationship: string;
    occupation: string;
    pension_status: "none";
  }>;
  location: { city: string; state: string };
  assets: { bescom: boolean; ration_card: boolean; property: boolean };
}

const sessions = new Map<string, Session>();
const questions = [
  "What was your father's name?",
  "Is there a surviving spouse who may receive the family pension?",
  "Which city and state did your father live in?",
];

export async function POST(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  if (path.length === 1 && path[0] === "start") {
    const sessionId = randomUUID();
    sessions.set(sessionId, { answers: [] });
    return NextResponse.json({
      session_id: sessionId,
      status: "in_progress",
      message: "I'm sorry you're going through this. What happened?",
      profile: null,
    });
  }

  const [sessionId, action] = path;
  const session = sessions.get(sessionId);
  if (!session) return NextResponse.json({ detail: "Intake session not found" }, { status: 404 });

  if (action === "message") {
    const { message } = (await request.json()) as { message?: unknown };
    if (typeof message !== "string" || !message.trim()) {
      return NextResponse.json({ detail: "A message is required" }, { status: 422 });
    }
    session.answers.push(message.trim());
    if (session.answers.length < 4) {
      return NextResponse.json({
        session_id: sessionId,
        status: "in_progress",
        message: questions[session.answers.length - 1],
        profile: null,
      });
    }
    session.profile = buildProfile(session.answers);
    return NextResponse.json({
      session_id: sessionId,
      status: "complete",
      message: "I have enough information to prepare your plan.",
      profile: session.profile,
    });
  }

  if (action === "confirm" && session.profile) {
    const profile = session.profile;
    // ponytail: in-memory deterministic intake is the Phase-0 seam; Step 7 replaces it with AI persistence.
    return proxyBackendRequest(
      request,
      "/api/cases",
      JSON.stringify({
        life_event: {
          type: "father_death",
          context: {
            deceased: {
              is_deceased: true,
              pension_status: profile.deceased.pension_status,
              was_electricity_account_holder: profile.assets.bescom,
              was_head_of_household: true,
            },
            surviving_spouse: { exists: profile.surviving_members.length > 0 },
            location: { state: profile.location.state },
            assets: profile.assets,
          },
        },
        household_profile: {
          location_city: profile.location.city,
          location_state: profile.location.state,
          people: [
            { name: profile.deceased.name, relationship: "father", is_deceased: true },
          ],
        },
      }),
    );
  }

  return NextResponse.json({ detail: "Intake is not ready to confirm" }, { status: 409 });
}

function buildProfile(answers: string[]): IntakeProfile {
  const name = answers[1]?.replace(/^(his name (was|is)|it was)\s+/i, "").trim() || "Father";
  return {
    deceased: {
      name,
      relationship: "father",
      occupation: "retired government employee",
      pension_status: "active",
    },
    surviving_members: [
      { name: "Surviving spouse", relationship: "spouse", occupation: "", pension_status: "none" },
    ],
    location: { city: "Bengaluru", state: "Karnataka" },
    assets: { bescom: true, ration_card: true, property: false },
  };
}
