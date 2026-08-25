import json

import grpc
from contracts.generated import catalog_pb2, catalog_pb2_grpc
from grpc import aio

from app.catalog import Catalog


class CatalogServicer(catalog_pb2_grpc.CatalogServiceServicer):
    def __init__(self, catalog: Catalog) -> None:
        self.catalog = catalog

    async def GetWorkflowDefinition(self, request, context):  # noqa: N802
        workflow = self.catalog.workflows.get(request.workflow_id)
        if workflow is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "Workflow not found")
        return catalog_pb2.WorkflowDefinition(definition_json=workflow.model_dump_json())

    async def GetServiceDefinition(self, request, context):  # noqa: N802
        service = self.catalog.services.get(request.service_id)
        if service is None:
            await context.abort(grpc.StatusCode.NOT_FOUND, "Service not found")
        return catalog_pb2.ServiceDefinition(definition_json=service.model_dump_json())

    async def ListApplicableWorkflows(self, request, context):  # noqa: N802
        try:
            profile = json.loads(request.profile_json)
            if not isinstance(profile, dict):
                raise ValueError("Profile context must be a JSON object")
            workflows = self.catalog.applicable_workflows(profile)
        except (json.JSONDecodeError, ValueError) as exc:
            await context.abort(grpc.StatusCode.INVALID_ARGUMENT, str(exc))
        return catalog_pb2.WorkflowList(
            workflows=[
                catalog_pb2.WorkflowDefinition(definition_json=workflow.model_dump_json())
                for workflow in workflows
            ]
        )


def create_server(port: int, catalog: Catalog) -> aio.Server:
    server = aio.server()
    catalog_pb2_grpc.add_CatalogServiceServicer_to_server(CatalogServicer(catalog), server)
    server.add_insecure_port(f"[::]:{port}")
    return server
