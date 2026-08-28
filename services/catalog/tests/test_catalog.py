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
        "marriage",
        "property",
        "education",
        "senior_services",
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
    assert all("required_profile_fields" in item for item in filtered.json()["services"])

    searched = await client.get("/api/catalog/search", params={"q": "electricity"})
    assert len(searched.json()["services"]) == 2

    service = await client.get("/api/catalog/services/death_certificate")
    assert service.json()["typical_wait_days"] == [3, 7]
    assert len(service.json()["stages"]) == 4

    workflow = await client.get("/api/catalog/workflows/death_certificate")
    assert workflow.json()["tasks"][0]["id"] == "death_registration"
    stages = await client.get("/api/catalog/workflows/death_certificate/stages")
    assert stages.json()["stages"][0] == {"id": "submitted", "name": "Submitted", "order": 1}

    benefits = await client.get("/api/catalog/benefits")
    assert {item["id"] for item in benefits.json()["benefits"]} == {
        "widow_pension",
        "sc_st_scholarship",
        "senior_pension",
    }
    assert (await client.get("/api/catalog/benefits/widow_pension")).json()["workflow_id"] == (
        "widow_pension_application"
    )

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
        "category_id": "bereavement",
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

    for profile, expected in (
        (
            {
                "category_id": "new_baby",
                "baby": {"name": "Anaya Rao", "dob": "2026-08-20"},
                "hospital_record_uploaded": True,
            },
            {
                "birth_certificate",
                "aadhaar_enrollment",
                "child_passport",
                "vaccination_registration",
            },
        ),
        (
            {
                "category_id": "marriage",
                "marriage": {
                    "spouse1": "Meera Rao",
                    "change_address": True,
                    "change_name": False,
                    "add_to_ration_card": True,
                },
            },
            {
                "marriage_certificate",
                "post_marriage_address_update",
                "ration_card_spouse_addition",
            },
        ),
    ):
        result = await servicer.ListApplicableWorkflows(
            catalog_pb2.ProfileContext(profile_json=json.dumps(profile)), None
        )
        assert {json.loads(item.definition_json)["id"] for item in result.workflows} == expected


@pytest.mark.parametrize(
    ("category_id", "expected"),
    [
        (
            "new_baby",
            {
                "birth_certificate",
                "aadhaar_enrollment",
                "child_passport",
                "vaccination_registration",
            },
        ),
        (
            "marriage",
            {
                "marriage_certificate",
                "post_marriage_address_update",
                "ration_card_spouse_addition",
            },
        ),
        ("bereavement", {"death_certificate", "family_pension", "bescom_transfer", "ration_card"}),
    ],
)
def test_workflow_matching_does_not_cross_categories(category_id, expected) -> None:
    mixed_profile = {
        "category_id": category_id,
        "baby": {"name": "Anaya Rao", "dob": "2026-08-20"},
        "hospital_record_uploaded": True,
        "marriage": {
            "spouse1": "Meera Rao",
            "change_address": True,
            "change_name": False,
            "add_to_ration_card": True,
        },
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

    assert {workflow.id for workflow in catalog.applicable_workflows(mixed_profile)} == expected


def test_family_workflow_dependencies_follow_the_real_sequence() -> None:
    assert "hospital_birth_record" not in catalog.workflows
    assert catalog.workflows["birth_certificate"].inter_workflow_dependencies == []
    assert catalog.workflows["aadhaar_enrollment"].inter_workflow_dependencies == [
        "birth_certificate"
    ]
    assert catalog.workflows["child_passport"].inter_workflow_dependencies == [
        "birth_certificate"
    ]
    assert catalog.workflows["vaccination_registration"].inter_workflow_dependencies == []
    for workflow_id in (
        "post_marriage_address_update",
        "post_marriage_name_update",
        "ration_card_spouse_addition",
    ):
        assert catalog.workflows[workflow_id].inter_workflow_dependencies == [
            "marriage_certificate"
        ]
