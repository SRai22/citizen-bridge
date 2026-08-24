# Citizen-Bridge: API Contracts

**Status:** Authoritative contract — frontend and backend develop against this  
**Updated:** 2026-08-24  
**Rule:** Any endpoint change requires updating this document FIRST

---

## Auth Service (`/api/auth`)

### `POST /api/auth/register`

Register a new user account.

**Request:**
```json
{
  "username": "string (3-50 chars, alphanumeric + underscore)",
  "password": "string (min 8 chars)",
  "name": "string (1-200 chars)",
  "date_of_birth": "string (YYYY-MM-DD)",
  "city": "string (1-100 chars)",
  "state": "string | null"
}
```

**Response `201`:**
```json
{
  "user_id": "uuid",
  "username": "string",
  "access_token": "string (JWT)",
  "refresh_token": "string",
  "expires_in": 900
}
```

**Errors:** `409` username taken, `422` validation error

---

### `POST /api/auth/login`

**Request:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response `200`:**
```json
{
  "user_id": "uuid",
  "access_token": "string (JWT)",
  "refresh_token": "string",
  "expires_in": 900
}
```

**Errors:** `401` invalid credentials

---

### `POST /api/auth/refresh`

**Request:**
```json
{
  "refresh_token": "string"
}
```

**Response `200`:**
```json
{
  "access_token": "string (JWT)",
  "refresh_token": "string (rotated)",
  "expires_in": 900
}
```

**Errors:** `401` expired or revoked

---

### `POST /api/auth/logout`

**Headers:** `Authorization: Bearer <access_token>`

**Response `204`:** No content

---

### `GET /api/auth/me`

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`:**
```json
{
  "user_id": "uuid",
  "username": "string",
  "name": "string",
  "date_of_birth": "YYYY-MM-DD",
  "city": "string",
  "state": "string | null",
  "phone": "string | null",
  "aadhaar_linked": false,
  "created_at": "ISO8601"
}
```

---

### `PATCH /api/auth/me`

**Headers:** `Authorization: Bearer <access_token>`

**Request (partial update):**
```json
{
  "name": "string | undefined",
  "city": "string | undefined",
  "state": "string | undefined",
  "phone": "string | undefined"
}
```

**Response `200`:** Updated user object (same shape as `GET /api/auth/me`)

---

### `GET /api/auth/me/profile`

Extended profile with completeness and provenance.

**Response `200`:**
```json
{
  "profile": {
    "name": "string",
    "date_of_birth": "YYYY-MM-DD",
    "city": "string",
    "state": "string | null",
    "gender": "string | null",
    "caste_category": "string | null",
    "annual_income": "number | null",
    "occupation": "string | null",
    "education_level": "string | null",
    "marital_status": "string | null"
  },
  "completeness_percent": 65,
  "missing_fields": ["annual_income", "caste_category"],
  "enrichment_suggestions": [
    {
      "field": "annual_income",
      "reason": "Required for 3 benefit schemes",
      "action": "Upload income certificate"
    }
  ]
}
```

---

### `GET /api/auth/me/family`

**Response `200`:**
```json
{
  "family_members": [
    {
      "person_id": "uuid",
      "name": "string",
      "relationship": "parent | spouse | sibling | child",
      "is_deceased": false,
      "on_platform": false,
      "user_id": "uuid | null",
      "active_cases_count": 1
    }
  ]
}
```

---

## Catalog Service (`/api/catalog`)

### `GET /api/catalog/categories`

**Response `200`:**
```json
{
  "categories": [
    {
      "id": "bereavement",
      "title": "Someone Passed Away",
      "subtitle": "Death certificate, pension, utilities, ration card",
      "icon": "dove",
      "description": "Handle administrative formalities after a family member's death",
      "service_count": 5
    }
  ]
}
```

---

### `GET /api/catalog/categories/{category_id}`

**Response `200`:**
```json
{
  "id": "bereavement",
  "title": "Someone Passed Away",
  "subtitle": "...",
  "icon": "dove",
  "description": "...",
  "services": [
    {
      "id": "death_certificate",
      "name": "Death Certificate",
      "authority": "BBMP / Municipal Corporation",
      "typical_wait_days": [3, 7]
    }
  ]
}
```

---

### `GET /api/catalog/services?category=certificates&search=death`

**Response `200`:**
```json
{
  "services": [
    {
      "id": "death_certificate",
      "name": "Death Certificate",
      "authority": "BBMP / Municipal Corporation",
      "category": "certificates",
      "typical_wait_days": [3, 7],
      "stages_known": true
    }
  ]
}
```

---

### `GET /api/catalog/services/{service_id}`

**Response `200`:**
```json
{
  "id": "death_certificate",
  "name": "Death Certificate",
  "authority": "BBMP / Municipal Corporation",
  "category": "certificates",
  "description": "...",
  "typical_wait_days": [3, 7],
  "stages_known": true,
  "stages": [
    { "id": "submitted", "label": "Submitted", "order": 1 },
    { "id": "under_review", "label": "Under Review", "order": 2 },
    { "id": "approved", "label": "Approved", "order": 3 },
    { "id": "issued", "label": "Issued", "order": 4 }
  ],
  "required_profile_fields": ["name", "dob", "city"],
  "workflow_id": "death_certificate"
}
```

---

## Case Engine (`/api/cases`)

### `GET /api/cases`

List cases the authenticated user has access to.

**Headers:** `Authorization: Bearer <access_token>`  
**Query:** `?status=active&life_event_type=bereavement`

**Response `200`:**
```json
{
  "cases": [
    {
      "case_id": "uuid",
      "title": "Father's Death — Administrative Formalities",
      "status": "active",
      "life_event_type": "bereavement",
      "my_role": "owner",
      "progress": { "completed": 2, "total": 5 },
      "created_at": "ISO8601",
      "updated_at": "ISO8601"
    }
  ]
}
```

---

### `GET /api/cases/{case_id}`

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`:**
```json
{
  "case_id": "uuid",
  "title": "Father's Death — Administrative Formalities",
  "status": "active",
  "life_event_type": "bereavement",
  "my_role": "owner",
  "my_permissions": ["view", "submit", "approve", "manage"],
  "subject": {
    "person_id": "uuid | null",
    "name": "Rajesh Kumar",
    "relationship": "father"
  },
  "progress": { "completed": 2, "total": 5 },
  "tasks_by_group": {
    "ready": [
      {
        "task_id": "uuid",
        "title": "Legal Heir Certificate",
        "task_type": "legal_heir_cert_application",
        "status": "ready",
        "description": "Apply at Tahsildar office",
        "workflow_id": "legal_heir_certificate"
      }
    ],
    "waiting": [
      {
        "task_id": "uuid",
        "title": "Family Pension Transfer",
        "status": "submitted",
        "wait_state": {
          "stages_known": false,
          "status_label": "Processing",
          "submitted_at": "ISO8601",
          "estimated_wait": { "min_days": 5, "max_days": 7 },
          "last_update": "ISO8601",
          "is_overdue": false,
          "message": "We'll notify you when there's an update."
        }
      }
    ],
    "blocked": [
      {
        "task_id": "uuid",
        "title": "BESCOM Name Transfer",
        "status": "blocked",
        "blocked_reason": "Waiting for: Legal Heir Certificate",
        "blocked_by_task_ids": ["uuid"]
      }
    ],
    "completed": [
      {
        "task_id": "uuid",
        "title": "Death Certificate",
        "status": "completed",
        "completed_at": "ISO8601",
        "reference_number": "BBMP/DC/2026/148392"
      }
    ]
  },
  "life_event": { "event_type": "father_death", "occurred_at": "ISO8601" },
  "created_at": "ISO8601"
}
```

---

### `GET /api/cases/{case_id}/tasks/{task_id}`

**Response `200`:**
```json
{
  "task_id": "uuid",
  "case_id": "uuid",
  "title": "Obtain Death Certificate",
  "task_type": "death_cert_application",
  "status": "ready",
  "description": "Apply for a death certificate at the municipal corporation",
  "workflow_id": "death_certificate",
  "required_documents": [
    {
      "type": "aadhaar",
      "owner": "deceased",
      "description": "Aadhaar card of the deceased",
      "status": "satisfied",
      "satisfied_by_document_id": "uuid"
    },
    {
      "type": "address_proof",
      "owner": "applicant",
      "description": "Address proof of applicant",
      "status": "missing"
    }
  ],
  "produced_documents": [],
  "dependencies": [
    { "task_id": "uuid", "title": "Some other task", "status": "completed" }
  ],
  "input_data": {},
  "wait_state": null
}
```

---

### `POST /api/cases/{case_id}/tasks/{task_id}/prepare`

Prepare and validate a submission.

**Request:**
```json
{
  "input_data": {
    "deceased_name": "Rajesh Kumar",
    "date_of_death": "2026-08-10",
    "place_of_death": "Bengaluru"
  }
}
```

**Response `200`:**
```json
{
  "approval_required": true,
  "approval_id": "uuid",
  "preview": {
    "action_title": "Submit Death Certificate Application",
    "authority": "BBMP (Bruhat Bengaluru Mahanagara Palike)",
    "fields": [
      { "label": "Deceased", "value": "Rajesh Kumar", "provenance": "From intake on 15 Aug 2026" },
      { "label": "Date of Death", "value": "10 Aug 2026", "provenance": "You provided" },
      { "label": "Applicant", "value": "Priya Kumar (Daughter)", "provenance": "Your profile" }
    ],
    "attached_documents": [
      { "type": "aadhaar", "title": "Aadhaar (Rajesh Kumar)", "provenance": "From DigiLocker" }
    ],
    "warning": "This action cannot be undone once submitted to BBMP.",
    "requires_step_up_auth": false
  }
}
```

---

### `POST /api/approvals/{approval_id}/approve`

**Response `200`:**
```json
{
  "task_id": "uuid",
  "status": "submitted",
  "receipt": {
    "reference_number": "BBMP/DC/2026/148392",
    "submitted_at": "ISO8601",
    "next_steps": [
      "BBMP will process within 3-7 working days",
      "We'll notify you when the certificate is ready",
      "Your death certificate will appear in 'My Documents' once issued"
    ]
  },
  "unlocked_tasks": [
    { "task_id": "uuid", "title": "Family Pension Transfer", "new_status": "ready" }
  ]
}
```

---

## AI Service (`/api/ai`)

### `POST /api/ai/intake/start`

**Headers:** `Authorization: Bearer <access_token>`

**Request:**
```json
{
  "category_id": "bereavement"
}
```

**Response `201`:**
```json
{
  "conversation_id": "uuid",
  "message": "I'm sorry for your loss. Could you tell me who passed away and your relationship to them?",
  "status": "in_progress"
}
```

---

### `POST /api/ai/intake/{conversation_id}/message`

**Request:**
```json
{
  "message": "My father passed away last week. He was 68."
}
```

**Response `200`:**
```json
{
  "message": "I understand. Could you share your father's full name and where he was living?",
  "status": "in_progress | complete",
  "profile": null
}
```

When `status: "complete"`:
```json
{
  "message": "I have all the information I need. Please review the summary below.",
  "status": "complete",
  "profile": {
    "deceased": { "name": "Rajesh Kumar", "age": 68, "relationship": "father" },
    "surviving_members": [
      { "name": "Priya Kumar", "relationship": "daughter", "role": "applicant" },
      { "name": "Kamala Devi", "relationship": "spouse", "role": "surviving_spouse" }
    ],
    "location": { "city": "Bengaluru", "state": "Karnataka" },
    "applicable_workflows": ["death_certificate", "family_pension", "bescom_transfer", "ration_card_update"]
  }
}
```

---

### `POST /api/ai/intake/{conversation_id}/confirm`

**Request:**
```json
{
  "profile_confirmed": true
}
```

**Response `200`:**
```json
{
  "case_id": "uuid"
}
```

---

### `POST /api/ai/interpret-rejection`

**Request:**
```json
{
  "rejection_text": "Legal Heir Certificate required for name transfer",
  "task_type": "bescom_name_transfer",
  "context": { "case_id": "uuid", "task_id": "uuid" }
}
```

**Response `200`:**
```json
{
  "interpretation": "BESCOM requires proof of legal succession rights. A death certificate alone is not sufficient for property-linked services.",
  "remediation_actions": [
    {
      "workflow_id": "legal_heir_certificate",
      "description": "Obtain Legal Heir Certificate from Tahsildar office",
      "estimated_duration": "7-15 days",
      "dependency_target": "bescom_name_transfer"
    }
  ]
}
```

---

## Document Service (`/api/docs`)

### `GET /api/docs`

**Headers:** `Authorization: Bearer <access_token>`  
**Query:** `?category=certificates&status=verified`

**Response `200`:**
```json
{
  "documents_by_category": {
    "identity": [
      {
        "document_id": "uuid",
        "document_type": "aadhaar",
        "title": "Aadhaar Card",
        "issuer": "UIDAI",
        "issued_at": "ISO8601 | null",
        "valid_until": "null",
        "verification_status": "verified",
        "provenance_type": "digilocker",
        "provenance_source": "DigiLocker",
        "used_in": ["Death Certificate application", "Pension Transfer"]
      }
    ],
    "certificates": [],
    "address": [],
    "income": [],
    "family": []
  }
}
```

---

### `GET /api/docs/{document_id}`

**Response `200`:**
```json
{
  "document_id": "uuid",
  "document_type": "death_certificate",
  "proof_category": "certificates",
  "title": "Death Certificate — Rajesh Kumar",
  "issuer": "BBMP",
  "issued_at": "ISO8601",
  "valid_until": null,
  "verification_status": "verified",
  "provenance_type": "platform_issued",
  "provenance_source": "Issued via task: Death Certificate (18 Aug 2026)",
  "source_case_id": "uuid",
  "source_task_id": "uuid",
  "extracted_fields": { "deceased_name": "Rajesh Kumar", "date_of_death": "2026-08-10" },
  "created_at": "ISO8601"
}
```

---

### `GET /api/docs/{document_id}/access-log`

**Response `200`:**
```json
{
  "accesses": [
    {
      "action": "shared",
      "purpose": "Pension Transfer application",
      "recipient": "Treasury Department",
      "case_id": "uuid",
      "accessed_at": "ISO8601"
    }
  ]
}
```

---

## Notification Service (`/api/notifications`)

### `GET /api/notifications`

**Headers:** `Authorization: Bearer <access_token>`  
**Query:** `?unread_only=true&type=urgent&limit=50&offset=0`

**Response `200`:**
```json
{
  "notifications": [
    {
      "id": "uuid",
      "notification_type": "task_status",
      "priority": "normal",
      "title": "Death Certificate Submitted",
      "body": "Your death certificate application has been submitted to BBMP",
      "data": {
        "case_id": "uuid",
        "task_id": "uuid",
        "entity_type": "task",
        "event": "status_changed",
        "new_status": "submitted"
      },
      "read": false,
      "created_at": "ISO8601"
    }
  ],
  "unread_count": 3,
  "total": 15
}
```

---

### `PATCH /api/notifications/{id}/read`

**Response `204`:** No content

---

### `GET /api/notifications/digest?week=2026-W34`

**Response `200`:**
```json
{
  "week": "2026-W34",
  "ready_actions": [
    {
      "task_id": "uuid",
      "case_id": "uuid",
      "title": "Legal Heir Certificate",
      "context": "You can start this now"
    }
  ],
  "new_opportunities": [
    {
      "benefit_id": "free_bus_pass",
      "name": "Free Bus Pass",
      "readiness_percent": 100
    }
  ],
  "status_updates": [
    {
      "task_id": "uuid",
      "title": "Pension Transfer",
      "update": "Still under review"
    }
  ],
  "completions": []
}
```

---

### WebSocket: `ws://host/ws?token=<jwt>`

**Server → Client message:**
```json
{
  "type": "notification",
  "notification_id": "uuid",
  "notification_type": "task_status",
  "priority": "normal",
  "title": "Death Certificate Submitted",
  "body": "...",
  "data": { "case_id": "uuid", "task_id": "uuid", "event": "status_changed" },
  "timestamp": "ISO8601"
}
```

**Client → Server (ack):**
```json
{
  "type": "ack",
  "notification_id": "uuid"
}
```

**Reconnect:** `ws://host/ws?token=<jwt>&last_event_id=<uuid>`

---

## Authority Service (`/api/authority`)

### `GET /api/authority/check?user_id=X&resource_type=case&resource_id=Y&action=submit`

**Response `200`:**
```json
{
  "allowed": true,
  "role": "owner",
  "permissions": ["view", "submit", "approve", "manage", "delegate"],
  "limitations": []
}
```

---

### `GET /api/authority/cases`

**Headers:** `Authorization: Bearer <access_token>`

**Response `200`:**
```json
{
  "cases": [
    { "case_id": "uuid", "role": "owner", "granted_at": "ISO8601" },
    { "case_id": "uuid", "role": "coordinator", "granted_at": "ISO8601" }
  ]
}
```

---

### `POST /api/authority/grants`

**Request:**
```json
{
  "grantee_id": "uuid",
  "resource_type": "case",
  "resource_id": "uuid",
  "role": "coordinator",
  "expires_at": "ISO8601 | null"
}
```

**Response `201`:**
```json
{
  "grant_id": "uuid",
  "role": "coordinator",
  "granted_at": "ISO8601"
}
```

---

## Benefits (`/api/cases/benefits`)

### `GET /api/cases/benefits/active`

**Response `200`:**
```json
{
  "active_benefits": [
    {
      "benefit_id": "widow_pension",
      "name": "Widow Pension",
      "amount": "₹2,000/month",
      "status": "active",
      "since": "ISO8601",
      "next_payment_at": "ISO8601"
    }
  ]
}
```

---

### `GET /api/cases/benefits/eligible`

**Response `200`:**
```json
{
  "eligible": [
    {
      "benefit_id": "free_bus_pass",
      "name": "Free Bus Pass (Senior Citizen)",
      "amount": "Free BMTC travel",
      "authority": "BMTC",
      "readiness_percent": 100,
      "satisfied_requirements": [
        { "type": "aadhaar", "document_id": "uuid" },
        { "type": "age_verification", "source": "profile (DOB)" }
      ],
      "missing_requirements": []
    }
  ],
  "partially_eligible": [
    {
      "benefit_id": "sc_st_scholarship",
      "name": "SC/ST Scholarship",
      "readiness_percent": 40,
      "missing_requirements": [
        { "type": "caste_certificate", "action": "Upload or apply for caste certificate" }
      ],
      "missing_profile_fields": ["caste_category"]
    }
  ]
}
```

---

## Data Controls (`/api/auth/me`)

### `POST /api/auth/me/export`

**Response `202`:**
```json
{
  "export_id": "uuid",
  "status": "processing",
  "estimated_ready": "ISO8601"
}
```

### `POST /api/auth/me/delete`

**Request:**
```json
{ "confirmation": "DELETE MY ACCOUNT" }
```

**Response `200`:**
```json
{
  "deletion_id": "uuid",
  "status": "cooling_off",
  "cooling_off_until": "ISO8601",
  "what_will_be_deleted": ["Profile", "Documents metadata", "Cases", "Activity"],
  "what_cannot_be_recalled": ["Government submissions already made"]
}
```

---

## Common Patterns

### Authentication

All endpoints except `/api/auth/register`, `/api/auth/login`, `/api/auth/refresh`, `/api/catalog/*`, and `/health` require:
```
Authorization: Bearer <access_token>
```

### Error Response Shape

All errors follow:
```json
{
  "detail": "Human-readable error message",
  "error_code": "MACHINE_READABLE_CODE",
  "field_errors": [
    { "field": "username", "message": "Already taken" }
  ]
}
```

### Pagination

List endpoints support:
```
?limit=50&offset=0
```

Response includes:
```json
{
  "items": [...],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```
