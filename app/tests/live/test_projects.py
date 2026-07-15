"""Live tests for the project tools (getAllProjects, getAllProjectIds, getProject)."""

from ._client import PROJECT, result_list


async def test_list_projects_includes_seeded_projects(client):
    projects = result_list(await client.call_tool("getAllProjects", {}))
    assert isinstance(projects, list) and projects

    public_ids = {pid for p in projects for pid in p.get("publicIds", [])}
    assert {"jabref", "junit-framework"} <= public_ids
    # Every project carries a human-readable name.
    assert all(p.get("name") for p in projects)


async def test_list_project_ids(client):
    ids = result_list(await client.call_tool("getAllProjectIds", {}))
    assert "jabref" in ids
    assert "junit-framework" in ids


async def test_get_single_project(client):
    project = (await client.call_tool("getProject", {"project": PROJECT})).data
    assert PROJECT in project.get("publicIds", [])
    assert project.get("name") == "JabRef"
    assert project.get("defaultBranch")
