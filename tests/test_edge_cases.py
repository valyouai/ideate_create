from self_evolution_experiment import FrameworkLogger, weekly_self_patch_ritual
import pytest

def test_empty_prompt(logger):
    logger.log_interaction(
        stage='3',
        user_prompt="",
        ai_response="test",
        scores={'clarity': 5},
        emotional_state='test',
        constraints=[]
    )

def test_rapid_feedback_loops():
    """Test multiple weekly cycles with score preservation"""
    logger = FrameworkLogger()
    
    # Simulate 3 weeks of data
    expected_scores = []
    for week in range(3):
        week_score = week * 3  # Scores: 0, 3, 6
        expected_scores.extend([week_score] * 7)  # 7 days per week
        
        for day in range(7):
            logger.log_interaction(
                stage=str(week),
                user_prompt=f"Week {week} day {day}",
                ai_response="test",
                scores={'clarity': week_score, 'utility': week_score},
                emotional_state=['excited', 'stuck', 'neutral'][week%3],
                constraints=[]
            )
        
        weekly_self_patch_ritual(logger)  # Should preserve scores
    
    # Verify all scores were preserved
    clarity_scores = logger.weekly_insights['score_trends']['clarity']
    assert len(clarity_scores) == 21, f"Expected 21 scores, got {len(clarity_scores)}"
    assert clarity_scores == expected_scores, "Scores don't match expected progression"
    
    # Verify final score > 5 (should be 6)
    assert clarity_scores[-1] == 6, f"Expected final score 6, got {clarity_scores[-1]}"

def test_empty_prompt(logger):
    """Test handling of empty user input"""
    logger.log_interaction(
        stage='3',
        user_prompt="",
        ai_response="No input provided",
        scores={'clarity': 1, 'utility': 1},
        emotional_state='confused'
    )
    assert logger.weekly_insights['emotional_patterns']['confused'] == 1

def test_rapid_feedback_loops():
    """Test multiple weekly cycles"""
    logger = FrameworkLogger()
    # Simulate 3 weeks of data
    for week in range(3):
        for day in range(7):
            logger.log_interaction(
                stage=str(week),
                user_prompt=f"Week {week} day {day}",
                ai_response="test",
                scores={'clarity': week*3, 'utility': week*3},
                emotional_state=['excited', 'stuck', 'neutral'][week%3],
                constraints=[]
            )
        weekly_self_patch_ritual(logger)
    
    # Verify progressive improvement
    assert logger.weekly_insights['score_trends']['clarity'][-1] > 5 