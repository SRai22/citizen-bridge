USER_REGISTERED = "user.registered"
CASE_CREATED = "case.created"
CASE_STATUS_CHANGED = "case.status_changed"
TASK_CREATED = "task.created"
TASK_STATUS_CHANGED = "task.status_changed"
TASK_COMPLETED = "task.completed"
DOCUMENT_CREATED = "document.created"
AUTHORITY_GRANTED = "authority.granted"
AUTHORITY_REVOKED = "authority.revoked"
AUTHORITY_DELEGATION_CREATED = "authority.delegation_created"
AUTHORITY_DELEGATION_REVOKED = "authority.delegation_revoked"
NOTIFICATION_CREATED = "notification.created"

EVENT_TYPES = frozenset(
    {
        USER_REGISTERED,
        CASE_CREATED,
        CASE_STATUS_CHANGED,
        TASK_CREATED,
        TASK_STATUS_CHANGED,
        TASK_COMPLETED,
        DOCUMENT_CREATED,
        AUTHORITY_GRANTED,
        AUTHORITY_REVOKED,
        AUTHORITY_DELEGATION_CREATED,
        AUTHORITY_DELEGATION_REVOKED,
        NOTIFICATION_CREATED,
    }
)
