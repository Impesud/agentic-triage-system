"""Test guardrail API key per demo L17."""

from unittest.mock import patch

from orchestration.api_guard import (
    has_openai_api_key,
    require_api_key_for_scenario,
    skip_llm_block,
)


@patch("orchestration.api_guard._openai_api_key_from_dotenv", return_value="")
def test_require_api_key_l15_always_ok(_mock_key):
    assert require_api_key_for_scenario("l15") is True


@patch("orchestration.api_guard._openai_api_key_from_dotenv", return_value="")
def test_require_api_key_l16a_skips_without_key(_mock_key):
    assert require_api_key_for_scenario("l16a") is False
    assert has_openai_api_key() is False


@patch("orchestration.api_guard._openai_api_key_from_dotenv", return_value="sk-test")
def test_require_api_key_l16a_ok_with_key(_mock_key):
    assert require_api_key_for_scenario("l16a") is True


@patch("orchestration.api_guard._openai_api_key_from_dotenv", return_value="")
def test_skip_llm_block_without_key(_mock_key):
    assert skip_llm_block("L16a CrewAI") is True


@patch("orchestration.api_guard._openai_api_key_from_dotenv", return_value="sk-test")
def test_skip_llm_block_with_key(_mock_key):
    assert skip_llm_block("L16a CrewAI") is False
