import httpx

from server import build_server, env_set

FAKE_SPEC = {
    "openapi": "3.0.1",
    "info": {"title": "Teamscale REST API", "version": "test"},
    "paths": {
        "/api/findings": {
            "get": {
                "operationId": "getFindings",
                "tags": ["Findings"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
        "/api/backups": {
            "get": {
                "operationId": "getBackups",
                "tags": ["Backup"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
    },
}


MULTI_TAG_SPEC = {
    "openapi": "3.0.1",
    "info": {"title": "Teamscale REST API", "version": "test"},
    "paths": {
        "/api/findings": {
            "get": {
                "operationId": "getFindings",
                "tags": ["Findings"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
        "/api/backups": {
            "get": {
                "operationId": "getBackups",
                "tags": ["Backup"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
        "/api/metrics": {
            "get": {
                "operationId": "getMetrics",
                "tags": ["Metrics"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
    },
}

DUAL_TAG_SPEC = {
    "openapi": "3.0.1",
    "info": {"title": "Teamscale REST API", "version": "test"},
    "paths": {
        "/api/findings-backup": {
            "get": {
                "operationId": "getFindingsBackup",
                "tags": ["Findings", "Backup"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
        "/api/findings": {
            "get": {
                "operationId": "getFindings",
                "tags": ["Findings"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
        "/api/metrics": {
            "get": {
                "operationId": "getMetrics",
                "tags": ["Metrics"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
    },
}


# GET + DELETE + PUT across two tags, for method- and name-based filtering.
METHOD_SPEC = {
    "openapi": "3.0.1",
    "info": {"title": "Teamscale REST API", "version": "test"},
    "paths": {
        "/api/findings": {
            "get": {
                "operationId": "getFindings",
                "tags": ["Findings"],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            }
        },
        "/api/projects/{project}": {
            "delete": {
                "operationId": "deleteProject",
                "tags": ["Projects"],
                "parameters": [
                    {
                        "name": "project",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {"204": {"description": "deleted"}},
            },
            "put": {
                "operationId": "editProject",
                "tags": ["Projects"],
                "parameters": [
                    {
                        "name": "project",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    }
                ],
                "requestBody": {
                    "content": {"application/json": {"schema": {"type": "object"}}}
                },
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    }
                },
            },
        },
    },
}


def _client():
    return httpx.AsyncClient(
        base_url="http://teamscale:8080",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})),
    )


async def _tool_names(mcp):
    tools = await mcp.list_tools()
    return {t.name for t in tools}


def test_env_set_parses_comma_list(monkeypatch):
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_TAGS", " Backup , System ,")
    assert env_set("TEAMSCALE_EXCLUDE_TAGS") == {"Backup", "System"}
    monkeypatch.delenv("TEAMSCALE_EXCLUDE_TAGS")
    assert env_set("TEAMSCALE_EXCLUDE_TAGS") == set()


async def test_generates_a_tool_per_operation():
    mcp = build_server(client=_client(), spec=FAKE_SPEC)
    tools = await _tool_names(mcp)
    assert "getFindings" in tools
    assert "getBackups" in tools


async def test_exclude_tags_drops_matching_tools(monkeypatch):
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_TAGS", "Backup")
    mcp = build_server(client=_client(), spec=FAKE_SPEC)
    tools = await _tool_names(mcp)
    assert "getFindings" in tools
    assert "getBackups" not in tools


async def test_include_tags_allowlist_drops_everything_else(monkeypatch):
    monkeypatch.setenv("TEAMSCALE_INCLUDE_TAGS", "Findings")
    mcp = build_server(client=_client(), spec=FAKE_SPEC)
    tools = await _tool_names(mcp)
    assert "getFindings" in tools
    assert "getBackups" not in tools


async def test_multiple_exclude_tags_drop_each_independently(monkeypatch):
    # RouteMap.tags is a subset/AND match, so a single RouteMap built from the
    # whole {"Findings", "Backup"} set would require both tags on one route
    # and would drop neither of these single-tagged ops. Each listed tag must
    # get its own RouteMap for the comma-separated env var to behave as OR.
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_TAGS", "Findings,Backup")
    mcp = build_server(client=_client(), spec=MULTI_TAG_SPEC)
    tools = await _tool_names(mcp)
    assert "getFindings" not in tools
    assert "getBackups" not in tools
    assert "getMetrics" in tools


async def test_exclude_wins_over_include_for_dual_tagged_op(monkeypatch):
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_TAGS", "Backup")
    monkeypatch.setenv("TEAMSCALE_INCLUDE_TAGS", "Findings")
    mcp = build_server(client=_client(), spec=DUAL_TAG_SPEC)
    tools = await _tool_names(mcp)
    assert "getFindingsBackup" not in tools  # excluded despite also being Findings
    assert "getFindings" in tools  # Findings-only op is kept
    assert "getMetrics" not in tools  # not in the allowlist, dropped by catch-all


async def test_exclude_methods_drops_matching_verb(monkeypatch):
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_METHODS", "DELETE")
    mcp = build_server(client=_client(), spec=METHOD_SPEC)
    tools = await _tool_names(mcp)
    assert "deleteProject" not in tools
    assert "getFindings" in tools
    assert "editProject" in tools


async def test_exclude_methods_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_METHODS", "delete")
    mcp = build_server(client=_client(), spec=METHOD_SPEC)
    tools = await _tool_names(mcp)
    assert "deleteProject" not in tools
    assert "getFindings" in tools


async def test_exclude_methods_drops_each_listed_method(monkeypatch):
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_METHODS", "DELETE,PUT")
    mcp = build_server(client=_client(), spec=METHOD_SPEC)
    tools = await _tool_names(mcp)
    assert "deleteProject" not in tools
    assert "editProject" not in tools
    assert "getFindings" in tools


async def test_include_names_rescues_excluded_method(monkeypatch):
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_METHODS", "DELETE")
    monkeypatch.setenv("TEAMSCALE_INCLUDE_NAMES", "deleteProject")
    mcp = build_server(client=_client(), spec=METHOD_SPEC)
    tools = await _tool_names(mcp)
    assert "deleteProject" in tools  # rescued despite the DELETE exclusion
    assert "getFindings" in tools


async def test_include_names_overrides_tag_allowlist(monkeypatch):
    # The INCLUDE_TAGS allowlist would drop deleteProject (its Projects tag is
    # not allowed), but INCLUDE_NAMES forces it back in over the catch-all.
    monkeypatch.setenv("TEAMSCALE_INCLUDE_TAGS", "Findings")
    monkeypatch.setenv("TEAMSCALE_INCLUDE_NAMES", "deleteProject")
    mcp = build_server(client=_client(), spec=METHOD_SPEC)
    tools = await _tool_names(mcp)
    assert "getFindings" in tools      # allowed tag
    assert "deleteProject" in tools    # rescued by name
    assert "editProject" not in tools  # dropped by the allowlist catch-all


async def test_exclude_names_drops_specific_operation(monkeypatch):
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_NAMES", "getFindings")
    mcp = build_server(client=_client(), spec=METHOD_SPEC)
    tools = await _tool_names(mcp)
    assert "getFindings" not in tools
    assert "editProject" in tools


async def test_exclude_names_overrides_tag_allowlist(monkeypatch):
    # INCLUDE_TAGS makes getFindings a tool (positive route-maps decision), but
    # EXCLUDE_NAMES runs after and drops it -- the name layer overrides an
    # allowlist keep, not just the default all-tools state.
    monkeypatch.setenv("TEAMSCALE_INCLUDE_TAGS", "Findings")
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_NAMES", "getFindings")
    mcp = build_server(client=_client(), spec=METHOD_SPEC)
    tools = await _tool_names(mcp)
    assert "getFindings" not in tools  # dropped by name despite the allowlist
    assert "editProject" not in tools  # dropped by the allowlist catch-all


async def test_include_names_wins_over_exclude_names(monkeypatch):
    monkeypatch.setenv("TEAMSCALE_INCLUDE_NAMES", "getFindings")
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_NAMES", "getFindings")
    mcp = build_server(client=_client(), spec=METHOD_SPEC)
    tools = await _tool_names(mcp)
    assert "getFindings" in tools


async def test_exclude_names_is_case_sensitive(monkeypatch):
    # operationIds are exact identifiers; a wrong-case name matches nothing.
    monkeypatch.setenv("TEAMSCALE_EXCLUDE_NAMES", "getfindings")
    mcp = build_server(client=_client(), spec=METHOD_SPEC)
    tools = await _tool_names(mcp)
    assert "getFindings" in tools  # not dropped -- case mismatch
