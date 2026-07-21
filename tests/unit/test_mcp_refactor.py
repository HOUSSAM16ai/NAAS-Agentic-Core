from unittest.mock import MagicMock, patch

import pytest

from app.core.integration_kernel import (
    AgentAction,
    PromptProgram,
    RetrievalQuery,
    ScoringSpec,
    WorkflowPlan,
)
from app.services.mcp.integrations import MCPIntegrations


@pytest.fixture
def mcp():
    with (
        patch("app.integration.gateways.planning.LocalPlanningGateway"),
        patch("app.integration.gateways.research.LocalResearchGateway"),
        patch("app.drivers.LangGraphDriver"),
        patch("app.drivers.LlamaIndexDriver"),
        patch("app.drivers.DSPyDriver"),
        patch("app.drivers.RerankerDriver"),
    ):
        return MCPIntegrations()


@pytest.mark.asyncio
async def test_run_langgraph_workflow_delegates_to_kernel(mcp):
    mcp.kernel.run_workflow = MagicMock()
    mcp.kernel.run_workflow.return_value = {"success": True}

    await mcp.run_langgraph_workflow(goal="test")

    mcp.kernel.run_workflow.assert_called_once()
    args, kwargs = mcp.kernel.run_workflow.call_args
    assert isinstance(args[0], WorkflowPlan)
    assert args[0].goal == "test"
    assert kwargs["engine"] == "langgraph"


@pytest.mark.asyncio
async def test_semantic_search_delegates_to_kernel(mcp):
    mcp.kernel.search = MagicMock()
    mcp.kernel.search.return_value = {"success": True}

    await mcp.semantic_search(query="test")

    mcp.kernel.search.assert_called_once()
    args, kwargs = mcp.kernel.search.call_args
    assert isinstance(args[0], RetrievalQuery)
    assert args[0].query == "test"
    assert kwargs["engine"] == "llamaindex"


@pytest.mark.asyncio
async def test_refine_query_delegates_to_kernel(mcp):
    mcp.kernel.optimize = MagicMock()
    mcp.kernel.optimize.return_value = {"success": True}

    await mcp.refine_query(query="test")

    mcp.kernel.optimize.assert_called_once()
    args, kwargs = mcp.kernel.optimize.call_args
    assert isinstance(args[0], PromptProgram)
    assert args[0].input_text == "test"
    assert kwargs["engine"] == "dspy"


@pytest.mark.asyncio
async def test_rerank_results_delegates_to_kernel(mcp):
    mcp.kernel.rank = MagicMock()
    mcp.kernel.rank.return_value = {"success": True}

    await mcp.rerank_results(query="test", documents=["doc1"])

    mcp.kernel.rank.assert_called_once()
    args, kwargs = mcp.kernel.rank.call_args
    assert isinstance(args[0], ScoringSpec)
    assert args[0].query == "test"
    assert kwargs["engine"] == "reranker"


@pytest.mark.asyncio
async def test_execute_action_delegates_to_kernel(mcp):
    mcp.kernel.act = MagicMock()
    mcp.kernel.act.return_value = {"success": True}

    await mcp.execute_action(action="act", capability="cap")

    mcp.kernel.act.assert_called_once()
    args, kwargs = mcp.kernel.act.call_args
    assert isinstance(args[0], AgentAction)
    assert args[0].action_name == "act"
    assert kwargs["engine"] == "kagent"
