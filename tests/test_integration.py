from self_evolution_experiment import FrameworkLogger, generate_insight_report

def test_full_workflow():
    """End-to-end test from logging to patching"""
    logger = FrameworkLogger()
    
    # Simulate real usage
    interactions = [
        (0, "Starting new project", {'clarity': 8, 'utility': 7}, "excited"),
        (3, "Feeling stuck", {'clarity': 3, 'utility': 2}, "stuck"),
        (3, "Still struggling", {'clarity': 4, 'utility': 3}, "stuck"),
        (4, "Breakthrough!", {'clarity': 9, 'utility': 9}, "excited")
    ]
    
    for stage, prompt, scores, emotion in interactions:
        logger.log_interaction(
            stage=str(stage),
            user_prompt=prompt,
            ai_response="test",
            scores=scores,
            emotional_state=emotion,
            constraints=[]
        )
    
    # Generate report
    report = generate_insight_report(logger.weekly_insights)
    
    # Verify recommendations
    assert "Emotional Patterns" in report
    assert "excited" in report
    assert "stuck" in report

    logger.log_interaction(
        stage='3',
        user_prompt="test",
        ai_response="test",
        scores={'clarity': 5},
        emotional_state='test',
        constraints=[]
    ) 