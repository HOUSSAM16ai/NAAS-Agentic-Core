from unittest.mock import AsyncMock, patch

import pytest

from app.services.chat.tools.content import _normalize_branch, search_content


@pytest.mark.asyncio
async def test_normalize_branch():
    assert _normalize_branch("experimental_sciences") == "علوم تجريبية"
    assert _normalize_branch("Math Tech") == "تقني رياضي"
    assert _normalize_branch("لغات") == "لغات أجنبية"
    assert _normalize_branch("unknown") == "unknown"


@pytest.mark.asyncio
async def test_search_content_with_branch_generates_correct_query():
    # Mock ResearchClient
    mock_client = AsyncMock()
    mock_client.deep_research.return_value = "Mock Report Content"

    # Patch the research_client in the content tool module
    with patch("app.services.chat.tools.content.research_client", mock_client):
        await search_content(
            q="Probability",
            year=2024,
            set_name="subject_1",
            branch="experimental_sciences",
        )

        # Verify calls
        mock_client.deep_research.assert_called_once()
        call_args = mock_client.deep_research.call_args[0][0]

        # Verify query construction contains key elements
        assert "Probability" in call_args
        assert "Branch: علوم تجريبية" in call_args
        assert "Year: 2024" in call_args


@pytest.mark.asyncio
async def test_search_content_without_branch():
    # Mock ResearchClient
    mock_client = AsyncMock()
    mock_client.deep_research.return_value = "Mock Report Content"

    with patch("app.services.chat.tools.content.research_client", mock_client):
        await search_content(q="Test Query")

        # Verify calls
        mock_client.deep_research.assert_called_once()
        call_args = mock_client.deep_research.call_args[0][0]

        assert "Test Query" in call_args
        assert "Branch:" not in call_args
