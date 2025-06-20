import os
import sys
import pytest
from self_evolution_experiment import FrameworkLogger

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configure environment variables for tests
@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test_key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "http://test.url")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")

@pytest.fixture
def logger():
    return FrameworkLogger() 