import json
from datetime import datetime
from models.user import db


class ExamSession(db.Model):
    __tablename__ = 'exam_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    student_name = db.Column(db.String(120), nullable=True)
    course_id = db.Column(db.String(50), nullable=False, index=True)
    status = db.Column(db.String(20), default='in_progress')  # in_progress, submitted, flagged
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    score = db.Column(db.Float, nullable=True)
    answers_json = db.Column(db.Text, nullable=True)

    # Relationships
    face_intervals = db.relationship('FaceAbsenceInterval', backref='session', lazy=True, cascade='all, delete-orphan')
    browser_events = db.relationship('BrowserEvent', backref='session', lazy=True, cascade='all, delete-orphan')
    suspicious_reports = db.relationship('SuspiciousReport', backref='session', lazy=True, cascade='all, delete-orphan')
    evidence = db.relationship('IncidentEvidence', backref='session', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'student_name': self.student_name,
            'course_id': self.course_id,
            'status': self.status,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'score': self.score,
        }


class FaceAbsenceInterval(db.Model):
    __tablename__ = 'face_absence_intervals'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    course_id = db.Column(db.String(50), nullable=False)
    start_timestamp = db.Column(db.Float, nullable=False)
    end_timestamp = db.Column(db.Float, nullable=True)
    duration_seconds = db.Column(db.Float, default=0.0)
    reason = db.Column(db.String(50), default='face_absent')  # face_absent, multiple_faces

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'email': self.email,
            'course_id': self.course_id,
            'start_timestamp': self.start_timestamp,
            'end_timestamp': self.end_timestamp,
            'duration_seconds': self.duration_seconds,
            'reason': self.reason,
            'start_iso': datetime.fromtimestamp(self.start_timestamp).isoformat() if self.start_timestamp else None,
            'end_iso': datetime.fromtimestamp(self.end_timestamp).isoformat() if self.end_timestamp else None,
        }


class BrowserEvent(db.Model):
    __tablename__ = 'browser_events'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=True, index=True)
    email = db.Column(db.String(120), nullable=False, index=True)
    course_id = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.Float, nullable=False)
    event_type = db.Column(db.String(50), nullable=False, index=True)  # tab_switch, window_blur, mouse_leave, etc.
    severity = db.Column(db.String(20), default='WARNING')  # INFO, WARNING, CRITICAL
    details = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'email': self.email,
            'course_id': self.course_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'severity': self.severity,
            'details': self.details,
            'time_iso': datetime.fromtimestamp(self.timestamp / 1000.0 if self.timestamp > 1e11 else self.timestamp).isoformat() if self.timestamp else None,
        }


class SuspiciousReport(db.Model):
    __tablename__ = 'suspicious_reports'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=False)
    course_id = db.Column(db.String(50), nullable=False)
    suspicion_score = db.Column(db.Float, nullable=False, default=0.0)  # 0.0 to 100.0
    suspicion_level = db.Column(db.String(20), nullable=False, default='LOW')  # LOW, MEDIUM, HIGH, CRITICAL
    is_suspicious = db.Column(db.Boolean, default=False)
    flags_triggered_json = db.Column(db.Text, default='[]')
    summary_json = db.Column(db.Text, default='{}')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def flags_triggered(self):
        try:
            return json.loads(self.flags_triggered_json or '[]')
        except Exception:
            return []

    @flags_triggered.setter
    def flags_triggered(self, val):
        self.flags_triggered_json = json.dumps(val)

    @property
    def summary(self):
        try:
            return json.loads(self.summary_json or '{}')
        except Exception:
            return {}

    @summary.setter
    def summary(self, val):
        self.summary_json = json.dumps(val)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'email': self.email,
            'course_id': self.course_id,
            'suspicion_score': round(self.suspicion_score, 1),
            'suspicion_level': self.suspicion_level,
            'is_suspicious': self.is_suspicious,
            'flags_triggered': self.flags_triggered,
            'summary': self.summary,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class IncidentEvidence(db.Model):
    __tablename__ = 'incident_evidence'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('exam_sessions.id'), nullable=False, index=True)
    evidence_type = db.Column(db.String(50), nullable=False, default='screenshot')
    file_path = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'evidence_type': self.evidence_type,
            'file_path': self.file_path,
            'description': self.description,
            'timestamp': self.timestamp,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
