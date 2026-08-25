import json

import pytest
from contracts.generated import catalog_pb2

from app.grpc import CatalogServicer
from app.main import catalog


@pytest.mark.asyncio
async def test_catalog_http_api(client) -> None:
    categories = await client.get("/api/catalog/categories")
    assert categories.status_code == 200
    assert {item["id"] for item in categories.json()["categories"]} == {
        "bereavement",
        "new_baby",
        "address_change",
        "retirement",
    }

    bereavement = await client.get("/api/catalog/categories/bereavement")
    assert bereavement.status_code == 200
    assert len(bereavement.json()["services"]) == 5

    filtered = await client.get(
        "/api/catalog/services", params={"category": "certificates", "search": "death"}
    )
    assert {item["id"] for item in filtered.json()["services"]} == {
        "death_certificate",
        "birth_certificate",
    }

    searched = await client.get("/api/catalog/search", params={"q": "electricity"})
    assert len(searched.json()["services"]) == 2

    service = await client.get("/api/catalog/services/death_certificate")
    assert service.json()["typical_wait_days"] == [3, 7]
    assert len(service.json()["stages"]) == 4

    workflow = await client.get("/api/catalog/workflows/death_certificate")
    assert workflow.json()["tasks"][0]["id"] == "death_registration"
    stages = await client.get("/api/catalog/workflows/death_certificate/stages")
    assert stages.json()["stages"][0] == {"id": "submitted", "name": "Submitted", "order": 1}

    assert (await client.get("/api/catalog/services/missing")).status_code == 404
    assert (await client.get("/health")).status_code == 200


@pytest.mark.asyncio
async def test_catalog_grpc_api() -> None:
    servicer = CatalogServicer(catalog)
    workflow = await servicer.GetWorkflowDefinition(
        catalog_pb2.WorkflowRequest(workflow_id="death_certificate"), None
    )
    assert json.loads(workflow.definition_json)["id"] == "death_certificate"

    profile = {
        "deceased": {
            "is_deceased": True,
            "pension_status": "active",
            "was_electricity_account_holder": True,
            "was_head_of_household": True,
        },
        "surviving_spouse": {"exists": True},
        "location": {"state": "Karnataka"},
        "assets": {"bescom": True, "ration_card": True},
    }
    result = await servicer.ListApplicableWorkflows(
        catalog_pb2.ProfileContext(profile_json=json.dumps(profile)), None
    )
    assert {json.loads(item.definition_json)["id"] for item in result.workflows} == {
        "death_certificate",
        "family_pension",
        "bescom_transfer",
        "ration_card",
    }
