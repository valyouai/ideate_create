from collections import defaultdict

class FrameworkLogger:
    """Enhanced interaction logger with patch note generation"""
    def __init__(self):
        self.session_log = []
        self.weekly_insights = {
            'emotional_patterns': defaultdict(int),
            'stage_completion_rates': defaultdict(float),
            'common_stuck_points': defaultdict(int),
            'score_trends': defaultdict(list)
        }

    def log_interaction(self, stage, user_prompt, ai_response, scores, emotional_state, constraints=None):
        """Log an interaction with metadata"""
        entry = {
            'stage': stage,
            'user_prompt': user_prompt,
            'ai_response': ai_response,
            'scores': scores,
            'emotional_state': emotional_state,
            'constraints': constraints or []
        }
        self.session_log.append(entry)
        self._update_weekly_insights(entry)

    def _update_weekly_insights(self, entry):
        """Update weekly insights based on logged interaction"""
        self.weekly_insights['emotional_patterns'][entry['emotional_state']] += 1
        self.weekly_insights['stage_completion_rates'][entry['stage']] += 1
        
        # Update score trends for each metric
        for metric, score in entry['scores'].items():
            if metric not in self.weekly_insights['score_trends']:
                self.weekly_insights['score_trends'][metric] = []
            self.weekly_insights['score_trends'][metric].append(score)
        
        # Track stuck points if utility score is low
        if entry['scores'].get('utility', 0) < 5:
            self.weekly_insights['common_stuck_points'][entry['stage']] += 1

    def _detect_constraints(self, prompt):
        """Detect constraints in a user prompt."""
        constraint_phrases = [
            "do not offer",
            "no actionable steps",
            "no advice",
            "only confirm",
            "nothing more than",
            "exactly 3 things"
        ]
        return [phrase for phrase in constraint_phrases if phrase in prompt.lower()]

    def weekly_self_patch_ritual(self):
        """Generate a weekly report and reset insights."""
        report = {
            'emotional_patterns': dict(self.weekly_insights['emotional_patterns']),
            'stage_completion_rates': dict(self.weekly_insights['stage_completion_rates']),
            'common_stuck_points': dict(self.weekly_insights['common_stuck_points']),
            'score_trends': {k: sum(v)/len(v) for k, v in self.weekly_insights['score_trends'].items()}
        }
        # Reset weekly insights
        for key in self.weekly_insights:
            self.weekly_insights[key].clear()
        return report

    def generate_insight_report(self, insights):
        """Generate a human-readable report from insights."""
        report = []
        if insights['emotional_patterns']:
            report.append("### Emotional Patterns")
            for emotion, count in insights['emotional_patterns'].items():
                report.append(f"- {emotion}: {count} occurrences")
        
        if insights['stage_completion_rates']:
            report.append("\n### Stage Completion Rates")
            for stage, rate in insights['stage_completion_rates'].items():
                report.append(f"- Stage {stage}: {rate} completions")
        
        if insights['common_stuck_points']:
            report.append("\n### Common Stuck Points")
            for stage, count in insights['common_stuck_points'].items():
                report.append(f"- Stage {stage}: {count} occurrences")
        
        if insights['score_trends']:
            report.append("\n### Average Scores")
            for metric, scores in insights['score_trends'].items():
                avg = sum(scores) / len(scores) if scores else 0
                report.append(f"- {metric}: {avg:.2f}")
        
        return "\n".join(report)

def weekly_self_patch_ritual(logger):
    """Generate weekly report and reset insights while preserving score history"""
    report = {
        'emotional_patterns': dict(logger.weekly_insights['emotional_patterns']),
        'stage_completion_rates': dict(logger.weekly_insights['stage_completion_rates']),
        'common_stuck_points': dict(logger.weekly_insights['common_stuck_points']),
        'score_trends': dict(logger.weekly_insights['score_trends'])  # Preserve full history
    }
    
    # Reset only the weekly counters, not score trends
    logger.weekly_insights['emotional_patterns'].clear()
    logger.weekly_insights['stage_completion_rates'].clear() 
    logger.weekly_insights['common_stuck_points'].clear()
    
    return report

def generate_insight_report(insights):
    """Generate human-readable report"""
    report = []
    if insights['emotional_patterns']:
        report.append("### Emotional Patterns")
        for emotion, count in insights['emotional_patterns'].items():
            report.append(f"- {emotion}: {count} occurrences")
    # ... (rest of the report generation logic)
    return "\n".join(report)
