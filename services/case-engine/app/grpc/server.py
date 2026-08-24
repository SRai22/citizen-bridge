from uuid import UUID

import grpc
from contracts.generated import cases_pb2, cases_pb2_grpc
from grpc import aio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.service import get_case, list_cases


class CaseServicer(cases_pb2_grpc.CaseServiceServicer):
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def GetCase(self, request, context):  # noqa: N802
        try:
            case_id = UUID(request.case_id)
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid case ID")
        async with self.sessions() as session:
            case = await get_case(session, case_id)
        if case is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "Case not found")
        return _response(case)

    async def ListCases(self, request, context):  # noqa: N802
        try:
            case_ids = [UUID(value) for value in request.case_ids]
        except ValueError:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, "Invalid case ID")
        async with self.sessions() as session:
            cases = await list_cases(session, case_ids)
        return cases_pb2.CaseList(cases=[_response(case) for case in cases])


def _response(case):
    return cases_pb2.CaseResponse(
        case_id=str(case.id),
        status=case.status.value,
        life_event_type=case.life_event_type,
    )


def create_server(port: int, sessions: async_sessionmaker[AsyncSession]) -> aio.Server:
    server = aio.server()
    cases_pb2_grpc.add_CaseServiceServicer_to_server(CaseServicer(sessions), server)
    server.add_insecure_port(f"[::]:{port}")
    return server
