import os
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from flask import current_app
from models.user import db
from models.proctor import ExamSession, FaceAbsenceInterval, BrowserEvent


class EventLogger:
    def __init__(self):
        # In-memory tracking of active face absence per (email, course_id) key
        # key -> {'start_time': timestamp, 'interval_id': db_id}
        self._absence_tracker: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def get_log_dir() -> str:
        if current_app:
            log_dir = current_app.config.get('MONITOR_LOG_DIR', 'monitor_logs')
        else:
            log_dir = 'monitor_logs'
        os.makedirs(log_dir, exist_ok=True)
        return log_dir

    def _write_audit_log(self, filename: str, line: str):
        try:
            log_dir = EventLogger.get_log_dir()
            filepath = os.path.join(log_dir, filename)
            with open(filepath, 'a', encoding='utf-8') as fh:
                fh.write(f"{datetime.utcnow().isoformat()},{line}\n")
        except Exception as e:
            print(f"Error writing audit log {filename}: {e}")

    def process_face_check(
        self,
        email: str,
        course_id: str,
        face_present: bool,
        face_count: int = 1,
        session_id: Optional[int] = None,
        timestamp: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        State machine processing face presence checks.
        Logs face-absent intervals with exact timestamps.
        """
        now = timestamp if timestamp is not None else time.time()
        key = f"{email}:{course_id}"
        tracker = self._absence_tracker.setdefault(key, {'absent_since': None, 'interval_id': None, 'reason': None})

        response_info = {
            'face_present': face_present,
            'face_count': face_count,
            'current_absence_duration': 0.0,
            'interval_closed': False,
            'interval_started': False,
        }

        if face_present and face_count == 1:
            # Face is normally present
            if tracker['absent_since'] is not None:
                # Face returned after absence -> Close interval
                start_ts = tracker['absent_since']
                duration = round(now - start_ts, 2)
                reason = tracker['reason'] or 'face_absent'

                interval = None
                if tracker['interval_id']:
                    interval = db.session.get(FaceAbsenceInterval, tracker['interval_id'])


                if interval:
                    interval.end_timestamp = now
                    interval.duration_seconds = duration
                else:
                    interval = FaceAbsenceInterval(
                        session_id=session_id,
                        email=email,
                        course_id=course_id,
                        start_timestamp=start_ts,
                        end_timestamp=now,
                        duration_seconds=duration,
                        reason=reason
                    )
                    db.session.add(interval)

                try:
                    db.session.commit()
                except Exception:
                    db.session.rollback()

                self._write_audit_log(
                    'face_absence_intervals.log',
                    f"{email},{course_id},{reason},end,{start_ts},{now},{duration}"
                )

                response_info['interval_closed'] = True
                response_info['last_absence_duration'] = duration
                tracker['absent_since'] = None
                tracker['interval_id'] = None
                tracker['reason'] = None
            else:
                self._write_audit_log('monitor_activity.log', f"{email},{course_id},face_present")

        else:
            # Face is either absent (face_count == 0) or multiple faces (face_count > 1)
            reason = 'multiple_faces' if face_count > 1 else 'face_absent'

            if tracker['absent_since'] is None:
                # Absence/Anomaly started -> Open interval
                tracker['absent_since'] = now
                tracker['reason'] = reason

                interval = FaceAbsenceInterval(
                    session_id=session_id,
                    email=email,
                    course_id=course_id,
                    start_timestamp=now,
                    end_timestamp=None,
                    duration_seconds=0.0,
                    reason=reason
                )
                db.session.add(interval)
                try:
                    db.session.commit()
                    tracker['interval_id'] = interval.id
                except Exception:
                    db.session.rollback()

                self._write_audit_log(
                    'face_absence_intervals.log',
                    f"{email},{course_id},{reason},start,{now}"
                )
                response_info['interval_started'] = True
                response_info['current_absence_duration'] = 0.0
            else:
                # Absence continues -> Update duration
                duration = round(now - tracker['absent_since'], 2)
                response_info['current_absence_duration'] = duration

                if tracker['interval_id']:
                    interval = db.session.get(FaceAbsenceInterval, tracker['interval_id'])
                    if interval:
                        interval.duration_seconds = duration
                        try:
                            db.session.commit()
                        except Exception:
                            db.session.rollback()

                self._write_audit_log(
                    'monitor_activity.log',
                    f"{email},{course_id},{reason}_continues,{duration}s"
                )

        return response_info

    def log_browser_events(
        self,
        email: str,
        course_id: str,
        events: List[Dict[str, Any]],
        session_id: Optional[int] = None
    ) -> List[BrowserEvent]:
        """
        Logs browser activity events to Database and File Audit Log.
        """
        created_events = []
        for evt in events:
            ts = evt.get('timestamp') or (time.time() * 1000.0)
            event_type = evt.get('type', 'unknown')
            details = str(evt.get('details', ''))
            severity = evt.get('severity', 'WARNING')

            if event_type in ['tab_hidden', 'window_blur', 'mouse_leave', 'context_menu', 'copy_paste']:
                severity = 'WARNING'
            elif event_type in ['fullscreen_exit', 'shortcut_key']:
                severity = 'CRITICAL'
            elif event_type in ['monitoring_started', 'tab_visible', 'window_focus']:
                severity = 'INFO'

            be = BrowserEvent(
                session_id=session_id,
                email=email,
                course_id=course_id,
                timestamp=ts,
                event_type=event_type,
                severity=severity,
                details=details
            )
            db.session.add(be)
            created_events.append(be)

            self._write_audit_log(
                'activity_events.log',
                f"{ts},{email},{course_id},{event_type},{severity},{details}"
            )

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        return created_events

    def finalize_session_intervals(self, email: str, course_id: str, session_id: Optional[int] = None):
        """Forces closing any active face absence interval upon exam submission."""
        key = f"{email}:{course_id}"
        tracker = self._absence_tracker.get(key)
        if tracker and tracker['absent_since'] is not None:
            now = time.time()
            start_ts = tracker['absent_since']
            duration = round(now - start_ts, 2)
            reason = tracker['reason'] or 'face_absent'

            if tracker['interval_id']:
                interval = db.session.get(FaceAbsenceInterval, tracker['interval_id'])

                if interval:
                    interval.end_timestamp = now
                    interval.duration_seconds = duration
                    try:
                        db.session.commit()
                    except Exception:
                        db.session.rollback()

            self._write_audit_log(
                'face_absence_intervals.log',
                f"{email},{course_id},{reason},finalized,{start_ts},{now},{duration}"
            )
            self._absence_tracker[key] = {'absent_since': None, 'interval_id': None, 'reason': None}


# Singleton event logger instance
event_logger_instance = EventLogger()
