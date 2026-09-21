import os

class Config:
    SECRET_KEY = "online_exam_secret"

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))

    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "database.db")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    MONITOR_LOG_DIR = os.path.join(BASE_DIR, "monitor_logs")

    SUSPICION_RULES = {
        "focus_loss_max": 3,
        "tab_switch_max": 2,
        "face_absence_max_seconds": 10,
        "face_absence_single_max_seconds": 5,
        "multi_face_max": 1,
        "unauthorized_actions_max": 2,
    }