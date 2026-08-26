import asyncio
import hmac
import json
import secrets
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from contracts.lib.observability import reset_user_id, set_user_id
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.clients import CatalogClient, DataServicesClient
from app.config import settings
from app.db import get_session
from app.kafka import EventPublisher
from app.models import (
    AccountDeletion,
    DataExport,
    FamilyMember,
    ProfileFieldProvenance,
    RefreshToken,
    User,
)
from app.profile import completeness, enrich_profile, missing_fields, profile_payload, suggestions
from app.schemas import (
    AccessTokenResponse,
    DeletionRequest,
    EnrichmentField,
    EnrichmentRequest,
    FamilyMemberCreate,
    FamilyMemberResponse,
    FamilyMemberUpdate,
    LoginRequest,
    PhoneOtpRequest,
    PhoneOtpResponse,
    PhoneOtpVerify,
    PhoneTokenResponse,
    ProfileFieldUpdate,
    ProvenanceDecision,
    ProvenanceResponse,
    RefreshRequest,
    RegistrationRequest,
    TokenResponse,
    UserResponse,
    UserUpdate,
)
from app.security import (
    InvalidTokenError,
    LoginRateLimiter,
    TokenManager,
    hash_password,
    token_digest,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer = HTTPBearer(auto_error=False)
tokens = TokenManager(
    settings.jwt_secret.get_secret_value(),
    settings.access_token_minutes,
    settings.refresh_token_days,
)
login_limiter = LoginRateLimiter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CredentialsDep = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def get_publisher(request: Request) -> EventPublisher:
    return request.app.state.publisher


PublisherDep = Annotated[EventPublisher, Depends(get_publisher)]


def get_catalog(request: Request) -> CatalogClient:
    return request.app.state.catalog_client


CatalogDep = Annotated[CatalogClient, Depends(get_catalog)]


def get_data_services(request: Request) -> DataServicesClient:
    return request.app.state.data_services


DataServicesDep = Annotated[DataServicesClient, Depends(get_data_services)]


async def current_user(session: SessionDep, credentials: CredentialsDep) -> AsyncIterator[User]:
    if credentials is None:
        raise _unauthorized("Missing bearer token")
    try:
        claims = tokens.decode(credentials.credentials, "access")
        user_id = UUID(claims["sub"])
    except (InvalidTokenError, ValueError) as exc:
        raise _unauthorized("Invalid or expired token") from exc
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Invalid or expired token")
    context_token = set_user_id(str(user.id))
    try:
        yield user
    finally:
        reset_user_id(context_token)


CurrentUserDep = Annotated[User, Depends(current_user)]


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegistrationRequest,
    request: Request,
    session: SessionDep,
    publisher: PublisherDep,
) -> TokenResponse:
    existing = await session.scalar(select(User.id).where(User.username == payload.username))
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already registered")

    user = User(
        username=payload.username,
        password_hash=await asyncio.to_thread(hash_password, payload.password),
        name=payload.name,
        date_of_birth=payload.date_of_birth,
        city=payload.city,
        state=payload.state,
        phone=payload.phone,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already registered") from exc

    provided = payload.model_dump(
        include={"name", "date_of_birth", "city", "state"}, exclude_none=True
    )
    if provided:
        await enrich_profile(
            session,
            user,
            [
                EnrichmentField(name=name, value=value, source_type="user_input")
                for name, value in provided.items()
            ],
        )

    access, refresh, expires_at = tokens.issue_pair(user.id, user.username)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest(refresh),
            expires_at=expires_at,
            device_info=_device_info(request),
        )
    )
    await publisher.publish(
        _event(
            "user.registered",
            user,
            username=user.username,
            name=user.name,
            city=user.city,
        )
    )
    await session.commit()
    return TokenResponse(user_id=user.id, access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: SessionDep,
    publisher: PublisherDep,
) -> TokenResponse:
    key = payload.username.casefold()
    if await login_limiter.is_limited(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts")

    user = await session.scalar(select(User).where(User.username == payload.username))
    valid = (
        user is not None
        and user.is_active
        and await asyncio.to_thread(verify_password, payload.password, user.password_hash)
    )
    if not valid:
        await login_limiter.record_failure(key)
        raise _unauthorized("Invalid credentials")
    await login_limiter.clear(key)

    access, refresh, expires_at = tokens.issue_pair(user.id, user.username)
    device_info = _device_info(request)
    known_device = await session.scalar(
        select(RefreshToken.id).where(
            RefreshToken.user_id == user.id,
            RefreshToken.device_info == device_info,
        )
    )
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest(refresh),
            expires_at=expires_at,
            device_info=device_info,
        )
    )
    await publisher.publish(
        _event(
            "user.logged_in",
            user,
            device_info=device_info,
            new_device=known_device is None,
        )
    )
    await session.commit()
    return TokenResponse(user_id=user.id, access_token=access, refresh_token=refresh)


@router.post("/phone/request", response_model=PhoneOtpResponse)
def request_phone_otp(payload: PhoneOtpRequest) -> PhoneOtpResponse:
    demo_code = settings.otp_demo_code
    if demo_code is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "OTP delivery is not configured")
    return PhoneOtpResponse(demo_code=demo_code.get_secret_value())


@router.post("/phone/verify", response_model=PhoneTokenResponse)
async def verify_phone_otp(
    payload: PhoneOtpVerify,
    request: Request,
    session: SessionDep,
    publisher: PublisherDep,
) -> PhoneTokenResponse:
    key = f"otp:{payload.phone}"
    if await login_limiter.is_limited(key):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many verification attempts")
    configured = settings.otp_demo_code
    if configured is None or not hmac.compare_digest(payload.code, configured.get_secret_value()):
        await login_limiter.record_failure(key)
        raise _unauthorized("The verification code is incorrect or expired")
    await login_limiter.clear(key)

    user = await session.scalar(select(User).where(User.phone == payload.phone))
    if payload.intent == "login" and user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account uses this phone number")
    if payload.intent == "register" and user is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account already uses this phone number")

    is_new_user = user is None
    if user is None:
        digits = payload.phone.removeprefix("+91")
        user = User(
            username=f"phone_{digits}",
            phone=payload.phone,
            password_hash=await asyncio.to_thread(hash_password, secrets.token_urlsafe(32)),
        )
        session.add(user)
        await session.flush()
    if not user.is_active:
        raise _unauthorized("This account is not active")

    access, refresh_token, expires_at = tokens.issue_pair(user.id, user.username)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest(refresh_token),
            expires_at=expires_at,
            device_info=_device_info(request),
        )
    )
    await publisher.publish(_event("user.registered" if is_new_user else "user.logged_in", user))
    await session.commit()
    return PhoneTokenResponse(
        user_id=user.id,
        access_token=access,
        refresh_token=refresh_token,
        is_new_user=is_new_user,
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(payload: RefreshRequest, session: SessionDep) -> AccessTokenResponse:
    try:
        claims = tokens.decode(payload.refresh_token, "refresh")
        user_id = UUID(claims["sub"])
    except (InvalidTokenError, ValueError) as exc:
        raise _unauthorized("Token expired or revoked") from exc

    stored = await session.scalar(
        select(RefreshToken)
        .where(
            RefreshToken.token_hash == token_digest(payload.refresh_token),
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > datetime.now(UTC),
        )
        .with_for_update()
    )
    user = await session.get(User, user_id)
    if stored is None or user is None or not user.is_active:
        raise _unauthorized("Token expired or revoked")

    stored.revoked_at = datetime.now(UTC)
    access, rotated, expires_at = tokens.issue_pair(user.id, user.username)
    session.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_digest(rotated),
            expires_at=expires_at,
            device_info=stored.device_info,
        )
    )
    await session.commit()
    return AccessTokenResponse(access_token=access, refresh_token=rotated)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(user: CurrentUserDep, session: SessionDep) -> Response:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUserDep) -> User:
    return user


@router.post("/me/export", status_code=status.HTTP_202_ACCEPTED)
async def request_export(
    background: BackgroundTasks,
    request: Request,
    user: CurrentUserDep,
    session: SessionDep,
    services: DataServicesDep,
) -> dict[str, Any]:
    export = DataExport(user_id=user.id)
    session.add(export)
    await session.commit()
    background.add_task(generate_export, export.id, services, request.app.state.session_factory)
    return {
        "export_id": export.id,
        "status": export.status,
        "estimated_ready": datetime.now(UTC) + timedelta(minutes=1),
    }


@router.get("/me/export/{export_id}")
async def export_status(
    export_id: UUID, user: CurrentUserDep, session: SessionDep
) -> dict[str, Any]:
    export = await _owned_export(session, export_id, user.id)
    response: dict[str, Any] = {"status": export.status}
    if export.status == "ready":
        response["download_url"] = f"/api/auth/me/export/{export.id}/download"
    if export.status == "failed":
        response["detail"] = export.error
    return response


@router.get("/me/export/{export_id}/download")
async def download_export(export_id: UUID, user: CurrentUserDep, session: SessionDep) -> Response:
    export = await _owned_export(session, export_id, user.id)
    if export.status != "ready" or export.payload is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Export is not ready")
    return Response(
        json.dumps(export.payload, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="citizen-bridge-export-{export.id}.json"'
        },
    )


@router.post("/me/delete")
async def request_deletion(
    payload: DeletionRequest,
    user: CurrentUserDep,
    session: SessionDep,
    publisher: PublisherDep,
) -> dict[str, Any]:
    if not await asyncio.to_thread(verify_password, payload.password, user.password_hash):
        raise _unauthorized("Password verification failed")
    existing = await session.scalar(
        select(AccountDeletion).where(
            AccountDeletion.user_id == user.id,
            AccountDeletion.status == "cooling_off",
        )
    )
    if existing is None:
        existing = AccountDeletion(
            user_id=user.id,
            cooling_off_until=datetime.now(UTC)
            + timedelta(days=settings.deletion_cooling_off_days),
        )
        session.add(existing)
        await session.flush()
        await publisher.publish(
            _event(
                "user.deletion_scheduled",
                user,
                deletion_id=str(existing.id),
                delete_at=existing.cooling_off_until.isoformat(),
            )
        )
        await session.commit()
    return _deletion_payload(existing)


@router.post("/me/delete/cancel")
async def cancel_deletion(user: CurrentUserDep, session: SessionDep) -> dict[str, bool]:
    deletion = await session.scalar(
        select(AccountDeletion).where(
            AccountDeletion.user_id == user.id,
            AccountDeletion.status == "cooling_off",
        )
    )
    if deletion is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending account deletion")
    deletion.status = "cancelled"
    deletion.cancelled_at = datetime.now(UTC)
    await session.commit()
    return {"cancelled": True, "account_active": True}


@router.get("/me/delete/status")
async def deletion_status(user: CurrentUserDep, session: SessionDep) -> dict[str, Any]:
    deletion = await session.scalar(
        select(AccountDeletion)
        .where(AccountDeletion.user_id == user.id, AccountDeletion.status == "cooling_off")
        .order_by(AccountDeletion.created_at.desc())
    )
    return (
        {"status": "none"}
        if deletion is None
        else {"status": "cooling_off", "cooling_off_until": deletion.cooling_off_until}
    )


@router.get("/me/family", response_model=list[FamilyMemberResponse])
async def family(user: CurrentUserDep, session: SessionDep) -> list[FamilyMember]:
    return list(
        await session.scalars(
            select(FamilyMember)
            .where(FamilyMember.user_id == user.id)
            .order_by(FamilyMember.created_at)
        )
    )


@router.post("/me/family", response_model=FamilyMemberResponse, status_code=status.HTTP_201_CREATED)
async def add_family_member(
    payload: FamilyMemberCreate, user: CurrentUserDep, session: SessionDep
) -> FamilyMember:
    member = await session.scalar(
        select(FamilyMember).where(
            FamilyMember.user_id == user.id,
            FamilyMember.name == payload.name,
            FamilyMember.relationship == payload.relationship,
        )
    )
    if member is None:
        member = FamilyMember(
            user_id=user.id,
            **payload.model_dump(exclude_none=True),
        )
        session.add(member)
    else:
        for name, value in payload.model_dump(exclude={"id"}, exclude_none=True).items():
            setattr(member, name, value)
    await session.commit()
    await session.refresh(member)
    return member


@router.patch("/me/family/{member_id}", response_model=FamilyMemberResponse)
async def update_family_member(
    member_id: UUID,
    payload: FamilyMemberUpdate,
    user: CurrentUserDep,
    session: SessionDep,
) -> FamilyMember:
    member = await session.scalar(
        select(FamilyMember).where(FamilyMember.id == member_id, FamilyMember.user_id == user.id)
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Family member not found")
    for name, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, name, value)
    await session.commit()
    await session.refresh(member)
    return member


@router.delete("/me/family/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_family_member(
    member_id: UUID, user: CurrentUserDep, session: SessionDep
) -> Response:
    member = await session.scalar(
        select(FamilyMember).where(FamilyMember.id == member_id, FamilyMember.user_id == user.id)
    )
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Family member not found")
    await session.delete(member)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    user: CurrentUserDep,
    session: SessionDep,
    publisher: PublisherDep,
) -> User:
    changes = payload.model_dump(exclude_unset=True)
    profile_changes = {key: value for key, value in changes.items() if key != "phone"}
    if profile_changes:
        await enrich_profile(
            session,
            user,
            [
                EnrichmentField(name=name, value=value, source_type="user_input")
                for name, value in profile_changes.items()
            ],
        )
    if "phone" in changes:
        user.phone = changes["phone"]
    if changes:
        await publisher.publish(
            _event("user.profile_updated", user, changed_fields=sorted(changes))
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, "Phone already registered") from exc
        await session.refresh(user)
    return user


@router.get("/me/profile")
async def get_profile(
    user: CurrentUserDep, catalog: CatalogDep, session: SessionDep
) -> dict[str, Any]:
    missing = missing_fields(user)
    requirements = await catalog.benefit_requirements()
    provenance_rows = (
        await session.scalars(
            select(ProfileFieldProvenance)
            .where(ProfileFieldProvenance.user_id == user.id)
            .order_by(ProfileFieldProvenance.created_at.desc())
        )
    ).all()
    provenance: dict[str, dict[str, Any]] = {}
    for row in provenance_rows:
        provenance.setdefault(
            row.field_name,
            {
                "type": row.source_type,
                "reference": row.source_reference,
                "verified": row.verified,
            },
        )
    return {
        "profile": profile_payload(user),
        "provenance": provenance,
        "completeness_percent": completeness(user),
        "missing_fields": missing,
        "enrichment_suggestions": suggestions(missing, requirements),
    }


@router.patch("/me/profile")
async def patch_profile(
    payload: ProfileFieldUpdate,
    user: CurrentUserDep,
    session: SessionDep,
    publisher: PublisherDep,
) -> dict[str, Any]:
    try:
        changed = await enrich_profile(
            session,
            user,
            [
                EnrichmentField(
                    name=payload.field_name,
                    value=payload.value,
                    source_type=payload.source,
                )
            ],
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await publisher.publish(_event("user.profile_updated", user, changed_fields=changed))
    await session.commit()
    await session.refresh(user)
    return {"profile": profile_payload(user), "completeness_percent": completeness(user)}


@router.get("/me/profile/{field_name}/provenance")
async def provenance_history(
    field_name: str, user: CurrentUserDep, session: SessionDep
) -> dict[str, Any]:
    rows = (
        await session.scalars(
            select(ProfileFieldProvenance)
            .where(
                ProfileFieldProvenance.user_id == user.id,
                ProfileFieldProvenance.field_name == field_name,
            )
            .order_by(ProfileFieldProvenance.created_at.desc())
        )
    ).all()
    return {"history": [ProvenanceResponse.model_validate(row).model_dump() for row in rows]}


@router.patch("/me/profile/{field_name}/provenance/{provenance_id}")
async def decide_provenance(
    field_name: str,
    provenance_id: UUID,
    payload: ProvenanceDecision,
    user: CurrentUserDep,
    session: SessionDep,
) -> ProvenanceResponse:
    record = await session.scalar(
        select(ProfileFieldProvenance).where(
            ProfileFieldProvenance.id == provenance_id,
            ProfileFieldProvenance.user_id == user.id,
            ProfileFieldProvenance.field_name == field_name,
        )
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Profile provenance not found")
    now = datetime.now(UTC)
    record.confirmed_by_user = payload.confirmed
    record.confirmed_at = now if payload.confirmed else None
    record.disputed_at = None if payload.confirmed else now
    await session.commit()
    await session.refresh(record)
    return ProvenanceResponse.model_validate(record)


@router.post("/users/{user_id}/enrich")
async def internal_enrich(
    user_id: UUID,
    payload: EnrichmentRequest,
    session: SessionDep,
    publisher: PublisherDep,
    internal_token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> dict[str, Any]:
    _require_internal(internal_token)
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    try:
        changed = await enrich_profile(session, user, payload.fields)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
    await publisher.publish(_event("user.profile_updated", user, changed_fields=changed))
    await session.commit()
    return {"profile": profile_payload(user), "completeness_percent": completeness(user)}


@router.get("/users/{user_id}/profile")
async def internal_profile(
    user_id: UUID,
    session: SessionDep,
    internal_token: Annotated[str | None, Header(alias="X-Internal-Service-Token")] = None,
) -> dict[str, Any]:
    _require_internal(internal_token)
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return {"profile": profile_payload(user)}


def _require_internal(internal_token: str | None) -> None:
    expected = settings.internal_service_token.get_secret_value()
    if not expected or not internal_token or not hmac.compare_digest(internal_token, expected):
        raise _unauthorized("Invalid internal service token")


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _device_info(request: Request) -> str | None:
    value = request.headers.get("User-Agent")
    return value[:512] if value else None


def _event(event_type: str, user: User, **fields: Any) -> dict[str, Any]:
    return {
        "event_type": event_type,
        "user_id": str(user.id),
        "timestamp": datetime.now(UTC).isoformat(),
        **fields,
    }


async def _owned_export(session: AsyncSession, export_id: UUID, user_id: UUID) -> DataExport:
    export = await session.scalar(
        select(DataExport).where(DataExport.id == export_id, DataExport.user_id == user_id)
    )
    if export is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export not found")
    return export


async def generate_export(
    export_id: UUID,
    services: DataServicesClient,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as session:
        export = await session.get(DataExport, export_id)
        if export is None:
            return
        user = await session.get(User, export.user_id)
        if user is None:
            return
        try:
            family = (
                await session.scalars(select(FamilyMember).where(FamilyMember.user_id == user.id))
            ).all()
            provenance = (
                await session.scalars(
                    select(ProfileFieldProvenance).where(ProfileFieldProvenance.user_id == user.id)
                )
            ).all()
            remote = await services.export(str(user.id))
            export.payload = jsonable_encoder(
                {
                    "exported_at": datetime.now(UTC),
                    "profile": {
                        **profile_payload(user),
                        "user_id": user.id,
                        "username": user.username,
                        "phone": user.phone,
                        "aadhaar_linked": user.aadhaar_linked,
                        "is_active": user.is_active,
                        "created_at": user.created_at,
                        "updated_at": user.updated_at,
                    },
                    "profile_provenance": [
                        ProvenanceResponse.model_validate(row) for row in provenance
                    ],
                    "family_members": [FamilyMemberResponse.model_validate(row) for row in family],
                    **remote,
                }
            )
            export.status = "ready"
            export.completed_at = datetime.now(UTC)
        except Exception as exc:
            export.status = "failed"
            export.error = str(exc)[:500]
        await session.commit()


def _deletion_payload(deletion: AccountDeletion) -> dict[str, Any]:
    return {
        "deletion_id": deletion.id,
        "status": deletion.status,
        "cooling_off_until": deletion.cooling_off_until,
        "what_will_be_deleted": [
            "Profile and personal data",
            "Documents metadata",
            "Case history",
            "Activity log",
            "Notification history",
        ],
        "what_cannot_be_recalled": [
            "Government submissions already made",
            "Certificates already issued",
            "Data already shared with government bodies",
        ],
    }
