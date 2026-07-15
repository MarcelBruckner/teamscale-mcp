"""Live tests for the findings-list tools (getFindings, getFindingsWithCount, getFinding)."""

from ._client import PROJECT, result_list


async def test_findings_list_non_empty(client):
    findings = result_list(
        await client.call_tool("getFindings", {"project": PROJECT, "max": 5})
    )
    assert isinstance(findings, list) and findings
    for finding in findings:
        assert finding.get("id")
        assert finding.get("message")
        assert finding.get("categoryName")


async def test_findings_with_count_reports_summary(client):
    data = (
        await client.call_tool("getFindingsWithCount", {"project": PROJECT, "max": 1})
    ).data
    assert isinstance(data.get("findings"), list)
    # resultSize is the total available; it is at least the size of the returned page.
    assert data.get("resultSize", 0) >= len(data["findings"])


async def test_get_single_finding_matches_list(client):
    listing = result_list(
        await client.call_tool("getFindings", {"project": PROJECT, "max": 1})
    )
    assert listing, "seeded project should have at least one finding"
    finding_id = listing[0]["id"]

    finding = (
        await client.call_tool("getFinding", {"project": PROJECT, "id": finding_id})
    ).data
    assert finding.get("id") == finding_id
    assert finding.get("message")
