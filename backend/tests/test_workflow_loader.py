from pathlib import Path

import pytest

from app.core import WorkflowDefinition, WorkflowDefinitionError, WorkflowLoader


def test_loads_and_validates_bundled_workflow_definitions() -> None:
    definitions = WorkflowLoader().load_all()
    definitions_by_id = {definition.id: definition for definition in definitions}

    assert set(definitions_by_id) == {
        "death_certificate",
        "family_pension",
        "bescom_transfer",
        "legal_heir_certificate",
        "ration_card",
    }
    assert all(isinstance(definition, WorkflowDefinition) for definition in definitions)
    assert all(
        any(task.required_documents and task.produces_documents for task in definition.tasks)
        for definition in definitions
    )
    assert definitions_by_id["death_certificate"].inter_workflow_dependencies == []
    assert definitions_by_id["legal_heir_certificate"].dynamic is True
    for workflow_id in {"family_pension", "bescom_transfer", "ration_card"}:
        assert definitions_by_id[workflow_id].inter_workflow_dependencies == ["death_certificate"]
        assert "death_certificate" in definitions_by_id[workflow_id].required_document_types


def test_applicability_rules_use_safe_dotted_path_equality() -> None:
    definitions = {definition.id: definition for definition in WorkflowLoader().load_all()}
    profile = {
        "deceased": {
            "is_deceased": True,
            "pension_status": "active",
            "was_electricity_account_holder": True,
            "was_head_of_household": True,
        },
        "location": {"state": "Karnataka"},
        "surviving_spouse": {"exists": True},
        "assets": {"bescom": True, "ration_card": True},
    }

    assert all(definition.is_applicable(profile) for definition in definitions.values())
    assert not definitions["bescom_transfer"].is_applicable(
        {**profile, "assets": {"bescom": 1, "ration_card": True}}
    )
    assert not definitions["family_pension"].is_applicable(
        {**profile, "deceased": {"is_deceased": True}}
    )


def test_invalid_yaml_has_a_clear_file_scoped_error(tmp_path: Path) -> None:
    invalid_file = tmp_path / "invalid.yaml"
    invalid_file.write_text("id: [unterminated", encoding="utf-8")

    with pytest.raises(WorkflowDefinitionError) as error:
        WorkflowLoader(tmp_path).load_all()

    assert "Could not parse workflow definition" in str(error.value)
    assert str(invalid_file) in str(error.value)


def test_invalid_definition_has_a_clear_validation_error(tmp_path: Path) -> None:
    invalid_file = tmp_path / "invalid_structure.yaml"
    invalid_file.write_text("id: death_certificate\nname: Incomplete\n", encoding="utf-8")

    with pytest.raises(WorkflowDefinitionError) as error:
        WorkflowLoader(tmp_path).load_all()

    assert "Invalid workflow definition" in str(error.value)
    assert "description" in str(error.value)


def test_duplicate_workflow_ids_are_rejected(tmp_path: Path) -> None:
    source = (
        Path(__file__).parents[1] / "app" / "workflows" / "definitions" / "death_certificate.yaml"
    )
    definition = source.read_text(encoding="utf-8")
    (tmp_path / "first.yaml").write_text(definition, encoding="utf-8")
    (tmp_path / "second.yaml").write_text(definition, encoding="utf-8")

    with pytest.raises(WorkflowDefinitionError, match="Duplicate workflow ID 'death_certificate'"):
        WorkflowLoader(tmp_path).load_all()


def workflow_yaml(
    workflow_id: str,
    dependency_id: str,
    required_document: str,
    produced_document: str,
) -> str:
    return f"""
id: {workflow_id}
name: {workflow_id}
description: Test workflow {workflow_id}.
authority: Test Authority
adapter_type: test_adapter
applicability_rules:
  - field: enabled
    equals: true
tasks:
  - id: submit
    name: Submit
    type: government_submission
    requires_approval: true
    required_documents:
      - type: {required_document}
        description: Required test document.
    produces_documents:
      - type: {produced_document}
        description: Produced test document.
    estimated_duration_days: 1
inter_workflow_dependencies:
  - {dependency_id}
"""


def test_circular_inter_workflow_dependencies_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "alpha.yaml").write_text(
        workflow_yaml("alpha", "beta", "document_beta", "document_alpha"),
        encoding="utf-8",
    )
    (tmp_path / "beta.yaml").write_text(
        workflow_yaml("beta", "alpha", "document_alpha", "document_beta"),
        encoding="utf-8",
    )

    with pytest.raises(WorkflowDefinitionError, match="Circular inter-workflow dependency"):
        WorkflowLoader(tmp_path).load_all()


def test_inconsistent_dependency_document_reference_is_rejected(tmp_path: Path) -> None:
    upstream = workflow_yaml(
        "upstream", "placeholder", "external_input", "upstream_output"
    ).replace("inter_workflow_dependencies:\n  - placeholder", "inter_workflow_dependencies: []")
    downstream = workflow_yaml("downstream", "upstream", "unrelated_document", "downstream_output")
    (tmp_path / "upstream.yaml").write_text(upstream, encoding="utf-8")
    (tmp_path / "downstream.yaml").write_text(downstream, encoding="utf-8")

    with pytest.raises(WorkflowDefinitionError, match="does not require any document"):
        WorkflowLoader(tmp_path).load_all()
