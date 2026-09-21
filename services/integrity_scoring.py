import pandas as pd
from typing import Dict, Any, List
import logging

class IntegrityScorer:
    """
    Pandas-based Integrity Scoring Module
    Calculates weighted event scoring, face presence ratio, and normalized risk labels.
    """
    def __init__(self, session_id: int, start_time: float, end_time: float, browser_events: List[Dict[str, Any]], face_intervals: List[Dict[str, Any]]):
        self.session_id = session_id
        self.start_time = start_time
        self.end_time = end_time
        self.browser_events = browser_events
        self.face_intervals = face_intervals
        self.total_duration = end_time - start_time if end_time and start_time else 0.0
        
        # Event weights
        self.weights = {
            'tab_hidden': 5.0,
            'window_blur': 5.0,
            'mouse_leave': 2.0,
            'context_menu': 10.0,
            'copy_paste': 15.0,
            'shortcut_key': 20.0,
            'fullscreen_exit': 25.0
        }

    def calculate_score(self) -> Dict[str, Any]:
        """Calculates final integrity score and risk label."""
        if self.total_duration <= 0:
            logging.warning("Session duration is 0 or negative. Cannot calculate accurate score.")
            self.total_duration = 3600.0 # Default 1 hour if unknown
            
        score = 0.0
        
        # 1. Weighted Event Scoring
        event_score = 0.0
        if self.browser_events:
            df_events = pd.DataFrame(self.browser_events)
            if 'event_type' in df_events.columns:
                # Map weights
                df_events['weight'] = df_events['event_type'].map(self.weights).fillna(0.0)
                event_score = df_events['weight'].sum()
        
        # 2. Face Presence Ratio Calculation
        face_absence_duration = 0.0
        if self.face_intervals:
            df_faces = pd.DataFrame(self.face_intervals)
            if 'duration_seconds' in df_faces.columns:
                face_absence_duration = df_faces['duration_seconds'].sum()
                
        # Calculate ratio of absence (0.0 to 1.0)
        face_absence_ratio = min(1.0, face_absence_duration / self.total_duration)
        
        # Penalty for face absence (e.g., 50 points max if absent whole time)
        face_score = face_absence_ratio * 50.0
        
        # 3. Combine scores
        total_score = event_score + face_score
        
        # Normalize score (0 to 100)
        normalized_score = min(100.0, round(total_score, 1))
        
        # 4. Normalized Risk Labelling
        if normalized_score >= 75.0:
            risk_label = 'CRITICAL'
        elif normalized_score >= 50.0:
            risk_label = 'HIGH'
        elif normalized_score >= 25.0:
            risk_label = 'MEDIUM'
        else:
            risk_label = 'LOW'
            
        is_suspicious = normalized_score >= 35.0 or risk_label in ['HIGH', 'CRITICAL']
        
        return {
            'suspicion_score': normalized_score,
            'suspicion_level': risk_label,
            'is_suspicious': is_suspicious,
            'summary': {
                'event_score': round(event_score, 1),
                'face_score': round(face_score, 1),
                'face_absence_ratio': round(face_absence_ratio, 2),
                'total_events': len(self.browser_events),
                'total_face_absences': len(self.face_intervals)
            }
        }
