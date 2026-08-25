from contracts.lib.events import DomainEvent


def test_domain_event_envelope() -> None:
    event = DomainEvent.create(
        "auth",
        {
            "event_type": "user.registered",
            "user_id": "8b7d907a-82fb-4cca-97e9-f9f02b9aee4e",
            "name": "Asha Rao",
        },
    )

    assert event.schema_version == "1.0"
    assert event.aggregate_id == "8b7d907a-82fb-4cca-97e9-f9f02b9aee4e"
    assert event.aggregate_type == "user"
    assert event.payload == {
        "user_id": "8b7d907a-82fb-4cca-97e9-f9f02b9aee4e",
        "name": "Asha Rao",
    }
