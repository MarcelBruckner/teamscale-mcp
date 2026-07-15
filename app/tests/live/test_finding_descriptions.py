"""Live tests for finding descriptions.

Two levels of "description": the per-finding ``message`` (the concrete instance
description) and the finding *type* descriptor (getFindingTypeDescriptions),
which carries the reusable name + rationale for a finding type.
"""

from ._client import PROJECT, result_list


async def test_finding_message_is_a_description(client):
    findings = result_list(
        await client.call_tool("getFindings", {"project": PROJECT, "max": 1})
    )
    assert findings
    message = findings[0].get("message")
    assert isinstance(message, str) and message.strip()


async def test_finding_type_description(client):
    findings = result_list(
        await client.call_tool("getFindings", {"project": PROJECT, "max": 1})
    )
    assert findings
    type_id = findings[0]["typeId"]

    # The body is a free-form map of code scope -> finding type IDs; Teamscale
    # echoes the scope back, nesting the descriptors as scope -> typeId ->
    # descriptor. (Using the project id as the scope label.)
    data = (
        await client.call_tool(
            "getFindingTypeDescriptions",
            {"project": PROJECT, "body": {PROJECT: [type_id]}},
        )
    ).data
    assert PROJECT in data
    entries = data[PROJECT]
    assert type_id in entries

    descriptor = entries[type_id]
    assert descriptor.get("name", "").strip()
    assert descriptor.get("description", "").strip()
