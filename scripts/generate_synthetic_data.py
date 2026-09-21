import os
import sys
import time
import random
from datetime import datetime, timedelta

# Add parent dir to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models.user import db, User
from models.proctor import ExamSession, BrowserEvent, FaceAbsenceInterval, SuspiciousReport
from services.integrity_scoring import IntegrityScorer

def create_synthetic_data():
    with app.app_context():
        print("Cleaning up old data...")
        db.session.query(SuspiciousReport).delete()
        db.session.query(BrowserEvent).delete()
        db.session.query(FaceAbsenceInterval).delete()
        db.session.query(ExamSession).delete()
        
        # Ensure a dummy user exists
        user = User.query.first()
        if not user:
            user = User(name="Test Student", email="test@example.com")
            user.set_password("password123")
            db.session.add(user)
            db.session.commit()
            
        profiles = [
            {'name': 'Low Risk', 'count': 10, 'events': 2, 'absences': 0},
            {'name': 'Medium Risk', 'count': 5, 'events': 5, 'absences': 1},
            {'name': 'High Risk', 'count': 3, 'events': 12, 'absences': 3}
        ]
        
        print("Generating synthetic sessions...")
        for profile in profiles:
            for i in range(profile['count']):
                start_time = datetime.utcnow() - timedelta(days=random.randint(0, 10), hours=random.randint(0, 5))
                end_time = start_time + timedelta(minutes=60)
                
                session = ExamSession(  # type: ignore
                    user_id=user.id,
                    email=user.email,
                    student_name=f"Student {profile['name']} {i+1}",
                    course_id="CS101",
                    status="submitted",
                    start_time=start_time,
                    end_time=end_time,
                    score=random.randint(60, 100)
                )
                db.session.add(session)
                db.session.commit()
                
                # Generate events
                events = []
                event_types = ['tab_hidden', 'window_blur', 'mouse_leave', 'context_menu', 'copy_paste', 'shortcut_key', 'fullscreen_exit']
                
                for j in range(profile['events']):
                    evt_type = random.choice(event_types) if profile['name'] == 'High Risk' else random.choice(event_types[:3])
                    evt_time = start_time + timedelta(minutes=random.randint(1, 55))
                    
                    be = BrowserEvent(  # type: ignore
                        session_id=session.id,
                        email=user.email,
                        course_id="CS101",
                        timestamp=evt_time.timestamp() * 1000, # ms
                        event_type=evt_type,
                        severity='WARNING' if profile['name'] == 'High Risk' else 'INFO'
                    )
                    db.session.add(be)
                    events.append(be.to_dict())
                
                # Generate face absences
                intervals = []
                for k in range(profile['absences']):
                    abs_start = start_time + timedelta(minutes=random.randint(1, 50))
                    duration = random.randint(10, 60) if profile['name'] != 'High Risk' else random.randint(60, 300)
                    abs_end = abs_start + timedelta(seconds=duration)
                    
                    fai = FaceAbsenceInterval(  # type: ignore
                        session_id=session.id,
                        email=user.email,
                        course_id="CS101",
                        start_timestamp=abs_start.timestamp(),
                        end_timestamp=abs_end.timestamp(),
                        duration_seconds=duration,
                        reason='face_absent'
                    )
                    db.session.add(fai)
                    intervals.append(fai.to_dict())
                    
                db.session.commit()
                
                # Generate Score using Pandas Scorer
                scorer = IntegrityScorer(
                    session_id=session.id,
                    start_time=start_time.timestamp(),
                    end_time=end_time.timestamp(),
                    browser_events=events,
                    face_intervals=intervals
                )
                
                score_result = scorer.calculate_score()
                
                report = SuspiciousReport(
                    session_id=session.id,
                    email=user.email,
                    course_id="CS101",
                    suspicion_score=score_result['suspicion_score'],
                    suspicion_level=score_result['suspicion_level'],
                    is_suspicious=score_result['is_suspicious'],
                    summary=score_result['summary'],
                    flags_triggered=[e['event_type'] for e in events] # Simplified flag list for testing
                )
                
                if score_result['is_suspicious']:
                    session.status = 'flagged'
                    
                db.session.add(report)
                db.session.commit()
                
        print("Done generating synthetic data!")

if __name__ == '__main__':
    create_synthetic_data()
