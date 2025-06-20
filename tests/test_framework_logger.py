import pytest
from datetime import datetime, timedelta
from self_evolution_experiment import FrameworkLogger

@pytest.fixture
def logger():
    return FrameworkLogger()

def test_log_interaction():
    logger = FrameworkLogger()
    logger.log_interaction(
        stage='3',
        user_prompt="test",
        ai_response="test",
        scores={'clarity': 5},
        emotional_state='test',
        constraints=[]
    )
    assert len(logger.session_log) == 1

def test_weekly_insight_generation(logger):
    """Test insight aggregation over multiple interactions"""
    # Simulate a week's worth of varied interactions
    test_data = [
        {'stage': '3', 'scores': {'clarity': 5, 'utility': 3}, 'emotional_state': 'stuck', 'constraints': []},
        {'stage': '2', 'scores': {'clarity': 8, 'utility': 7}, 'emotional_state': 'flow', 'constraints': []},
        {'stage': '3', 'scores': {'clarity': 4, 'utility': 2}, 'emotional_state': 'stuck', 'constraints': []},
        {'stage': '4', 'scores': {'clarity': 9, 'utility': 8}, 'emotional_state': 'excited', 'constraints': []}
    ]
    
    for data in test_data:
        logger.log_interaction(
            stage=data['stage'],
            user_prompt="test",
            ai_response="test",
            scores=data['scores'],
            emotional_state=data['emotional_state'],
            constraints=data['constraints']
        )
    
    # Verify insights
    assert logger.weekly_insights['emotional_patterns']['stuck'] == 2
    assert logger.weekly_insights['stage_completion_rates']['3'] == 2.0
    assert '3' in logger.weekly_insights['common_stuck_points']

def test_constraint_detection():
    logger = FrameworkLogger()
    constrained_prompt = "Do exactly 3 things and nothing more"
    constraints = logger._detect_constraints(constrained_prompt)
    assert "exactly 3 things" in constraints 