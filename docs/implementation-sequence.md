# Citizen-Bridge: Implementation Sequence

**40 tickets. 3 phases. Incremental delivery.**

Each step produces a testable, working increment. No step is wasted infrastructure — every step either enables a user-visible capability or proves the architecture works.

---

## How to Read This

- **Steps** are sequential — complete one before starting the next
- **Parallel tracks** within a step can run simultaneously
- **Checkpoint** at the end of each step = something demonstrable works
- Ticket IDs link to `/tickets/TICKET-{id}.md`

---

## Phase 0 — Infrastructure & Walking Skeleton

> Goal: New architecture runs end-to-end. One user flow works through all services.

### Step 1: Foundation (Week 1)

```
BE-001  Monorepo Restructure & Shared Contracts
INT-006 Strangler Transition Plan (document only — no code)
```

**Do:**
- Restructure repo: `/services/`, `/contracts/`, `/infrastructure/`
- Create proto definitions, event schemas, shared constants
- Create service skeleton template (Dockerfile, config.py, health check)
- Write transition map (legacy → new endpoints)
- Keep `/backend/` intact (legacy)

**Checkpoint:** Repo has new structure. `contracts/` has proto files. Legacy still runs.

---

### Step 2: Infrastructure Containers (Week 1-2)

```
BE-002  Docker Compose Infrastructure (PG, Kafka, Nginx)
INT-005 Secrets & Configuration Management
INT-003 Observability Stack
```

**Do:**
- Docker compose with PostgreSQL 16, Kafka (KRaft), Nginx, Jaeger
- PostgreSQL init script creates 7 schemas with per-service roles
- Kafka topic creation script
- Nginx config with routes for all services (503 until services start)
- `.env.example` with all variables documented
- Shared observability library (structured logging, correlation IDs, tracing)

**Checkpoint:** `docker compose up` starts PG + Kafka + Nginx + Jaeger. Schemas exist. Topics created. Jaeger UI accessible at :16686.

---

### Step 3: Auth Service (Week 2)

```
BE-003  Auth Service
```

**Do:**
- User model, registration, login, JWT issuance/refresh
- gRPC ValidateToken (other services will call this)
- Password hashing (bcrypt)
- Publishes `user.registered` to Kafka
- Uses shared observability library

**Checkpoint:** Register via API → get JWT → `/api/auth/me` returns profile. Jaeger shows traces.

---

### Step 4: Authority + CI (Week 2-3)

Parallel tracks:

```
Track A: BE-004  Authority Service
Track B: INT-004 CI/CD for Multi-Service
         INT-002 Integration Test Framework (skeleton)
```

**Track A — Authority:**
- Grant model, case access, permission checking
- gRPC CheckAccess + RegisterCaseOwner
- Consumes `user.registered` → creates default self-grants
- REST endpoints for grant/revoke

**Track B — CI/CD:**
- GitHub Actions: change detection, per-service matrix, contract tests
- `docker-compose.test.yml` for integration tests
- First integration test: register user → verify authority default grants

**Checkpoint:** Auth + Authority communicate via Kafka. CI runs on PR. Integration test passes.

---

### Step 5: Case Engine Migration (Week 3-4)

```
BE-005  Case Engine Service (Migrate from Monolith)
```

**Do:**
- Move case/task/workflow logic to `services/case-engine/`
- Add JWT auth (validates via Auth gRPC)
- Add authority checks (validates via Authority gRPC)
- New `GET /api/cases` (list user's cases via Authority)
- Enhanced response shape (grouped tasks, wait state, progress)
- SQLite → PostgreSQL migration for existing models
- Publishes case/task events to Kafka

**Checkpoint:** Create case via API (authenticated) → tasks appear → case owned by user. Legacy still works at `/api/legacy/`.

---

### Step 6: Walking Skeleton (Week 4)

```
INT-001 Walking Skeleton — E2E Through New Architecture
```

**Do:**
- Wire everything together
- Frontend points to Nginx (auth header injection)
- Full flow: Register → Login → Intake → Case → View
- E2E test validates the flow programmatically

**Checkpoint (GATE):** The walking skeleton passes. Register → Login → Browse → Intake → Create case → View case — all through new services. Jaeger shows full cross-service trace. This gates all P1 work.

---

```
Phase 0 Summary
━━━━━━━━━━━━━━
Steps:     6
Tickets:   BE-001→005, INT-001→006
Services:  Auth, Authority, Case Engine (3 of 7)
Result:    Authenticated user can create and view cases through new architecture
Legacy:    Still running, frontend can use either
```

---

## Phase 1 — Full Service Ecosystem

> Goal: All 7 services running. Frontend transformed. Real-time updates. Complete demo through new stack.

### Step 7: Catalog + AI Services (Week 5)

Parallel tracks:

```
Track A: BE-006 Catalog Service
Track B: BE-008 AI Service
```

**Track A — Catalog:**
- YAML-based service registry and life event categories
- API: categories, services, workflow definitions, stages
- gRPC interface for Case Engine to fetch workflow definitions

**Track B — AI:**
- Extract intake + rejection interpretation from monolith
- Conversation persistence in DB (survives restart)
- Mock mode for development
- Token cost tracking

**Checkpoint:** `GET /api/catalog/categories` returns life event cards. Intake conversation works via AI Service.

---

### Step 8: Document + Notification Services (Week 5-6)

Parallel tracks:

```
Track A: BE-007  Document Service
Track B: BE-009  Notification Service
```

**Track A — Documents:**
- Document model with proof categories, provenance, access log
- Profile-centric grouping (identity, certificates, address, income, family)
- gRPC CheckRequirements (Case Engine calls this)
- Consumes `task.completed` → creates produced documents

**Track B — Notifications:**
- WebSocket connection manager (JWT auth)
- Notification persistence in DB
- Consumes ALL Kafka topics → routes to user notifications
- REST: list, mark read, preferences
- Digest generation (weekly summary)

**Checkpoint:** Documents appear with provenance after task completion. WebSocket sends real-time notification when task status changes.

---

### Step 9: Kafka Backbone + Waiting States + Delegation (Week 6-7)

```
BE-010 Kafka Event Backbone (full wiring)
BE-013 Waiting State & Timeline Metadata
BE-015 Acting On Behalf & Delegation Flow
```

**Do:**
- Wire all producers and consumers across all 7 services
- Idempotent consumers with processed_events tracking
- Dead letter queues for failed events
- Task wait state tracking (stages, ETAs, overdue detection)
- CaseCoordinator role, delegation requests, authority limitations
- "Who is this for?" API

**Checkpoint:** Full event chain works: task completes → document created → notification sent → WebSocket broadcast. Waiting tasks show timeline. User can coordinate a case for a family member.

---

### Step 10: Frontend Platform Shell (Week 6-7, parallel with Step 9)

```
UX-001 Platform Shell — Navigation & Layout
UX-002 Onboarding Flow
```

**Do:**
- New navigation: 7-section sidebar (desktop) + hamburger drawer (mobile)
- Responsive layout with breakpoint at 768px
- Onboarding: register → name/DOB/city → optional Aadhaar → home
- Auth state management (JWT storage, refresh, header injection)

**Checkpoint:** New app shell renders. User can register and land on home page. Navigation works on mobile and desktop.

---

### Step 11: Frontend Core Flows (Week 7-8)

```
UX-003 Services Catalog & Life Event Trigger
UX-004 Enhanced Case Progress View
UX-005 Approval Gate Ceremony
```

**Do:**
- Home: life event category cards from Catalog Service
- Category → chat handoff (connects to AI Service)
- Case view: grouped task list (ready / waiting / blocked / completed)
- Graph toggle (existing React Flow, enhanced)
- Full-screen approval ceremony (not modal) with preview, provenance, receipt

**Checkpoint:** Complete user journey in new UI: browse services → start life event → chat intake → view case with grouped tasks → submit task with approval ceremony → see receipt.

---

### Step 12: Frontend Supporting Sections (Week 8-9)

```
UX-006 My Documents (Profile-Centric)
UX-008 Waiting State UX
UX-009 Notification Digest Page
UX-011 Trust & Transparency Features
```

**Do:**
- Documents section: grouped by proof type, provenance tags, access log
- Waiting states: adaptive (timeline if stages known, status card if opaque)
- Notification digest page (push → digest with ready actions + opportunities)
- Activity log, data provenance display, data controls page

**Checkpoint:** All 7 nav sections populated (some with real data, some with empty states). Waiting tasks show appropriate timeline/status. Citizen can see who accessed their documents.

---

```
Phase 1 Summary
━━━━━━━━━━━━━━
Steps:     7→12
Tickets:   BE-006→010, BE-013, BE-015, UX-001→006, UX-008, UX-009, UX-011
Services:  All 7 running
Result:    Full platform experience through new architecture
           Real-time WebSocket updates
           Profile-centric documents with provenance
           Adaptive waiting states
           Trust & transparency features
Legacy:    Can be shut down after verifying all flows work
```

---

## Phase 2 — Full Platform Vision

> Goal: Benefits discovery, progressive enrichment, family management, polish. Platform feels complete.

### Step 13: User Profile Engine (Week 9-10)

```
BE-011 User Profile & Progressive Enrichment
BE-014 Activity Feed & Audit Projection
```

**Do:**
- Extended profile fields (gender, caste, income, occupation, education, marital status)
- Provenance per field (source, verification, confirmed_at)
- Completeness percentage calculation
- Enrichment suggestions ("complete income to unlock 3 benefits")
- Activity feed projection from Kafka events
- Citizen-friendly vs detailed audit views

**Checkpoint:** Profile shows completeness %. Fields enriched from document extraction. Activity feed shows chronological events.

---

### Step 14: Benefits & Opportunities (Week 10-11)

```
BE-012 Benefits & Opportunity Engine
UX-007 My Benefits (Active + Opportunities)
```

**Do:**
- Rule-based eligibility engine (YAML-defined, not LLM)
- Readiness calculation (% of requirements satisfied)
- Active benefits tracking
- Profile change → re-evaluate eligibility → notify if new benefit found
- Frontend: "Currently Receiving" + "You May Be Eligible For" with readiness bars
- "Apply now" creates case with benefit workflow

**Checkpoint:** User with profile data sees eligible benefits with readiness %. "Apply now" starts a workflow. Profile enrichment discovers new benefits.

---

### Step 15: Acting On Behalf & Family (Week 11-12)

```
UX-010 Acting On Behalf Of
UX-012 My Family (Contextual Management)
UX-013 My Applications (Flat View)
```

**Do:**
- "Who is this for?" flow (self / family member / someone else)
- Smart inference from chat context
- Persistent coordinator banner when acting for others
- Authority limitations display
- Family member list with relationship + active cases
- My Applications: flat cross-case view of all submissions

**Checkpoint:** User can coordinate a case for a family member. Banner shows who they're acting for. My Applications shows all tasks across all cases.

---

### Step 16: Data Controls (Week 12)

```
BE-016 Data Controls (Export, Deletion, Revocation)
UX-014 Recent Activity Feed
```

**Do:**
- Data export (async, JSON download)
- Document sharing revocation
- Application withdrawal
- Account deletion (7-day cooling-off, cross-service coordination)
- Recent activity nav section (citizen-friendly event feed)

**Checkpoint:** User can export their data, revoke document shares, withdraw applications, and request account deletion. Activity feed shows human-readable timeline.

---

### Step 17: Polish & Patterns (Week 12-13)

```
UX-015 Error & Edge Case Patterns
UX-016 Empty States & Onboarding Prompts
UX-017 Chat Personality & Adaptive Interaction
UX-018 Progress Celebration & Milestone Acknowledgment
```

**Do:**
- Standardized error components (rejection, network error, timeout, expired, authority)
- Empty state for every section with actionable CTA
- First-time hint on home page
- Adaptive mirror chat personality (prompt engineering)
- Subtle progress celebrations (checkmark animation, milestone summary, case completion)

**Checkpoint:** No section shows a blank page. Errors always show next action. Chat adapts to user's style. Completing a case shows warm summary.

---

```
Phase 2 Summary
━━━━━━━━━━━━━━
Steps:     13→17
Tickets:   BE-011, BE-012, BE-014, BE-016, UX-007, UX-010, UX-012→018
Result:    Complete platform vision
           Benefits discovery with readiness indicators
           Progressive profile enrichment
           Family management and delegation
           Full data controls
           Polished error states, empty states, celebrations
```

---

## Visual Timeline

```
Week  1 ──── 2 ──── 3 ──── 4 ──── 5 ──── 6 ──── 7 ──── 8 ──── 9 ──── 10 ─── 11 ─── 12 ─── 13
      │      │      │      │      │      │      │      │      │      │      │      │      │
P0    ├──────┤      │      │      │      │      │      │      │      │      │      │      │
      │ S1   │      │      │      │      │      │      │      │      │      │      │      │
      │ S2 ──┤      │      │      │      │      │      │      │      │      │      │      │
      │      ├── S3 ┤      │      │      │      │      │      │      │      │      │      │
      │      │   S4 ├──────┤      │      │      │      │      │      │      │      │      │
      │      │      │  S5 ─┤      │      │      │      │      │      │      │      │      │
      │      │      │      ├ S6 ──┤ GATE │      │      │      │      │      │      │      │
      │      │      │      │      │      │      │      │      │      │      │      │      │
P1    │      │      │      │      ├── S7 ┤      │      │      │      │      │      │      │
      │      │      │      │      ├── S8 ┼──────┤      │      │      │      │      │      │
      │      │      │      │      │      ├── S9 ┼──────┤      │      │      │      │      │
      │      │      │      │      │      ├ S10 ─┤      │      │      │      │      │      │
      │      │      │      │      │      │      ├ S11 ─┼──────┤      │      │      │      │
      │      │      │      │      │      │      │      ├ S12 ─┤      │      │      │      │
      │      │      │      │      │      │      │      │      │      │      │      │      │
P2    │      │      │      │      │      │      │      │      ├ S13 ─┼──────┤      │      │
      │      │      │      │      │      │      │      │      │      ├ S14 ─┼──────┤      │
      │      │      │      │      │      │      │      │      │      │      ├ S15 ─┤      │
      │      │      │      │      │      │      │      │      │      │      │  S16 ┤      │
      │      │      │      │      │      │      │      │      │      │      │      ├ S17 ─┤
```

---

## Dependency Graph (Simplified)

```
BE-001 ─→ BE-002 ─→ BE-003 ─→ BE-004 ─→ BE-005 ─→ INT-001 (GATE)
  │          │                              │            │
  │          ├→ INT-003 (observability)      │            ↓
  │          ├→ INT-005 (secrets)            │        ┌───────┐
  │          │                              │        │ P1    │
  ├→ INT-006 (transition plan)              │        │ START │
  ├→ INT-004 (CI/CD)                        │        └───┬───┘
  │                                         │            │
  │                               ┌─────────┤            │
  │                               ↓         ↓            ↓
  │                           BE-006    BE-008      UX-001 ─→ UX-002
  │                             │                     │
  │                             │                     ├→ UX-003
  │                             ↓                     ├→ UX-004 ─→ UX-005
  │                     BE-007  BE-009                │
  │                       │       │                   ↓
  │                       ↓       ↓              UX-006, UX-008
  │                    BE-010 (kafka wiring)     UX-009, UX-011
  │                       │
  │                    BE-013 (waiting)
  │                    BE-015 (delegation)
  │                       │
  │                       ↓
  │                    BE-011 (profile) ─→ BE-012 (benefits)
  │                       │                   │
  │                    BE-014 (activity)  UX-007 (benefits UI)
  │                       │
  │                    BE-016 (data controls)
  │                       │
  │                    UX-010, UX-012, UX-013
  │                    UX-014, UX-015, UX-016
  │                    UX-017, UX-018
```

---

## Rules

1. **No skipping steps.** Each step's checkpoint must pass before the next starts.
2. **Parallel tracks within a step are independent.** Start both simultaneously.
3. **The P0→P1 gate (INT-001) is hard.** No exceptions. If the walking skeleton doesn't work, fix it before doing anything else.
4. **Frontend can lead backend within a step** using mock data from the API contract (docs/api-contracts.md). But must integrate with real service before the step's checkpoint.
5. **Legacy monolith stays running** until all P1 checkpoints pass. Then evaluate shutdown per INT-006 criteria.
6. **Every step delivers something demonstrable.** If you can't demo the checkpoint, the step isn't done.
