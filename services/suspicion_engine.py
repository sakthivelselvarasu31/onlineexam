from typing import Dict, Any, List, Optional
from flask import current_app


class SuspicionEngine:
    """
    Rule-based Suspicious Event Detection Engine.
    Evaluates face presence intervals and browser event streams against configurable threshold parameters.
    """

    DEFAULT_RULES = {
        "focus_loss_max": 3,
        "tab_switch_max": 2,
        "face_absence_max_seconds": 10,
        "face_absence_single_max_seconds": 5,
        "multi_face_max": 1,
        "unauthorized_actions_max": 2,
    }

    def __init__(self, rules: Optional[Dict[str, Any]] = None):
        self.rules = self.DEFAULT_RULES.copy()
        if rules:
            self.rules.update(rules)

    @classmethod
    def from_config(cls) -> 'SuspicionEngine':
        rules = None
        if current_app and current_app.config.get('SUSPICION_RULES'):
            rules = current_app.config['SUSPICION_RULES']
        return cls(rules=rules)

    def evaluate(
        self,
        focus_loss_count: int = 0,
        tab_switch_count: int = 0,
        face_absence_total_seconds: float = 0.0,
        face_absence_count: int = 0,
        face_intervals: Optional[List[Any]] = None,
        browser_events: Optional[List[Any]] = None,
        multi_face_count: int = 0,
        unauthorized_actions_count: int = 0
    ) -> Dict[str, Any]:
        """
        Evaluates session monitoring metrics and returns a detailed suspicion assessment.
        """
        flags_triggered = []
        score_weight = 0.0

        # Rule 1: Focus Loss Count
        focus_max = self.rules.get('focus_loss_max', 3)
        if focus_loss_count >= focus_max:
            flags_triggered.append('EXCESSIVE_FOCUS_LOSS')
            score_weight += min(35.0, 20.0 + (focus_loss_count - focus_max) * 5.0)

        # Rule 2: Tab Switch Count
        tab_max = self.rules.get('tab_switch_max', 2)
        if tab_switch_count >= tab_max:
            flags_triggered.append('EXCESSIVE_TAB_SWITCH')
            score_weight += min(40.0, 25.0 + (tab_switch_count - tab_max) * 7.5)

        # Rule 3: Cumulative Face Absence Seconds
        absence_max_sec = self.rules.get('face_absence_max_seconds', 10)
        if face_absence_total_seconds >= absence_max_sec:
            flags_triggered.append('CUMULATIVE_FACE_ABSENCE_EXCEEDED')
            score_weight += min(45.0, 30.0 + (face_absence_total_seconds - absence_max_sec) * 2.0)

        # Rule 4: Max Single Face Absence Duration
        single_max_sec = self.rules.get('face_absence_single_max_seconds', 5)
        max_single_duration = 0.0
        if face_intervals:
            for interval in face_intervals:
                if isinstance(interval, dict):
                    dur = interval.get('duration_seconds', 0.0)
                else:
                    dur = getattr(interval, 'duration_seconds', 0.0) or 0.0
                if dur > max_single_duration:
                    max_single_duration = dur

        if max_single_duration >= single_max_sec:
            flags_triggered.append('LONG_SINGLE_FACE_ABSENCE')
            score_weight += min(30.0, 20.0 + (max_single_duration - single_max_sec) * 2.0)

        # Rule 5: Multiple Faces Detected
        multi_max = self.rules.get('multi_face_max', 1)
        if multi_face_count >= multi_max:
            flags_triggered.append('MULTIPLE_FACES_DETECTED')
            score_weight += 35.0

        # Rule 6: Unauthorized Client-side Actions (Copy/Paste, Context Menu, Shortcuts)
        unauth_max = self.rules.get('unauthorized_actions_max', 2)
        if unauthorized_actions_count >= unauth_max:
            flags_triggered.append('UNAUTHORIZED_KEYBOARD_OR_CLIPBOARD')
            score_weight += 25.0

        # Inspect browser_events list if passed directly
        if browser_events:
            for evt in browser_events:
                evt_type = evt.get('type') if isinstance(evt, dict) else getattr(evt, 'event_type', '')
                if evt_type in ['fullscreen_exit', 'shortcut_key']:
                    if 'FULLSCREEN_EXIT_OR_SHORTCUT' not in flags_triggered:
                        flags_triggered.append('FULLSCREEN_EXIT_OR_SHORTCUT')
                        score_weight += 20.0

        # Calculate final normalized suspicion score (capped at 100.0)
        suspicion_score = min(100.0, round(score_weight, 1))

        # Categorize suspicion level
        if suspicion_score >= 75.0 or len(flags_triggered) >= 3:
            suspicion_level = 'CRITICAL'
        elif suspicion_score >= 50.0 or len(flags_triggered) >= 2:
            suspicion_level = 'HIGH'
        elif suspicion_score >= 25.0 or len(flags_triggered) >= 1:
            suspicion_level = 'MEDIUM'
        else:
            suspicion_level = 'LOW'

        is_suspicious = suspicion_score >= 35.0 or suspicion_level in ['HIGH', 'CRITICAL']

        if face_intervals and face_absence_count == 0:
            face_absence_count = len(face_intervals)

        summary = {
            'focus_loss_count': focus_loss_count,
            'tab_switch_count': tab_switch_count,
            'face_absence_count': face_absence_count,
            'face_absence_total_seconds': round(face_absence_total_seconds, 1),
            'max_single_absence_seconds': round(max_single_duration, 1),
            'multi_face_count': multi_face_count,
            'unauthorized_actions_count': unauthorized_actions_count,
            'rules_applied': self.rules,
        }

        return {
            'suspicion_score': suspicion_score,
            'suspicion_level': suspicion_level,
            'is_suspicious': is_suspicious,
            'flags_triggered': flags_triggered,
            'summary': summary,
        }


# Singleton engine instance
suspicion_engine_instance = SuspicionEngine()
