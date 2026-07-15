"""Live tests for findings-list filtering and pagination (getFindings, getFindingsWithCount)."""

from ._client import PROJECT, result_list


async def test_max_limits_page_size(client):
    one = result_list(await client.call_tool("getFindings", {"project": PROJECT, "max": 1}))
    three = result_list(await client.call_tool("getFindings", {"project": PROJECT, "max": 3}))
    assert len(one) == 1
    assert len(three) <= 3
    # The seeded project has many findings, so a larger page returns more.
    assert len(three) > len(one)


async def test_uniform_path_filter_narrows_to_that_path(client):
    sample = result_list(await client.call_tool("getFindings", {"project": PROJECT, "max": 1}))
    assert sample
    path = sample[0]["location"]["uniformPath"]

    filtered = result_list(
        await client.call_tool(
            "getFindings", {"project": PROJECT, "uniform-path": path, "max": 100}
        )
    )
    assert filtered
    assert all(f["location"]["uniformPath"].startswith(path) for f in filtered)


async def test_count_total_exceeds_returned_page(client):
    data = (
        await client.call_tool("getFindingsWithCount", {"project": PROJECT, "max": 1})
    ).data
    assert len(data["findings"]) == 1
    # resultSize is the total for the whole project, far larger than a one-item page.
    assert data["resultSize"] > 1
