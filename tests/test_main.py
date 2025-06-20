import os
from unittest.mock import patch, MagicMock
from self_evolution_experiment.main import chat

@patch('self_evolution_experiment.main.OpenAI')
def test_chat_success(mock_openai):
    """Test basic successful API call"""
    # Setup mock response
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_completion = MagicMock()
    mock_completion.choices[0].message.content = "Test response"
    mock_client.chat.completions.create.return_value = mock_completion

    # Set test environment
    os.environ["DEEPSEEK_API_KEY"] = "test_key"
    os.environ["DEEPSEEK_BASE_URL"] = "http://test.url"
    
    # Remove MODEL environment variable to test default behavior
    if "DEEPSEEK_MODEL" in os.environ:
        del os.environ["DEEPSEEK_MODEL"]

    # Call function
    messages = [{"role": "user", "content": "Hello"}]
    response = chat(messages)

    # Verify
    assert response == "Test response"
    mock_openai.assert_called_once()
    
    # Use actual default value in assertion
    mock_client.chat.completions.create.assert_called_once_with(
        model="deepseek-chat",  # Default value from implementation
        messages=messages,
        temperature=0.7
    )

@patch('self_evolution_experiment.main.OpenAI')
def test_chat_failure(mock_openai):
    """Test API failure handling"""
    # Setup mock to raise exception
    mock_client = MagicMock()
    mock_openai.return_value = mock_client
    mock_client.chat.completions.create.side_effect = Exception("API error")

    # Call function and verify exception is raised
    try:
        chat([])
        assert False, "Should have raised exception"
    except Exception as e:
        assert str(e) == "API error" 