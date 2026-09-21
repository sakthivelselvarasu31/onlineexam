import json
import os
import time
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, render_template, session, redirect, url_for

from models.user import db, User
from models.proctor import ExamSession, FaceAbsenceInterval, BrowserEvent, SuspiciousReport
from services.face_detector import face_detector_instance
from services.event_logger import event_logger_instance
from services.suspicion_engine import SuspicionEngine, suspicion_engine_instance

exam = Blueprint('exam', __name__)

COURSES = [
    {'id': 'math101', 'title': 'Math 101', 'description': 'Basic algebra and problem solving'},
    {'id': 'eng201', 'title': 'English 201', 'description': 'Reading and writing assessment'},
    {'id': 'cs301', 'title': 'Computer Science 301', 'description': 'Programming and logic exam'},
]

QUESTIONS_BY_COURSE = {
    'math101': [
        {'question': 'What is 2 + 2?', 'options': ['3', '4', '5', '6'], 'answer': '4'},
        {'question': 'What is the square root of 16?', 'options': ['2', '4', '8', '16'], 'answer': '4'},
        {'question': 'What is 5 * 6?', 'options': ['11', '25', '30', '35'], 'answer': '30'},
        {'question': 'What is 10 - 3?', 'options': ['6', '7', '8', '9'], 'answer': '7'},
        {'question': 'What is 12 / 4?', 'options': ['2', '3', '4', '6'], 'answer': '3'},
        {'question': 'What is 3 squared?', 'options': ['6', '9', '12', '27'], 'answer': '9'},
        {'question': 'What is 15 + 25?', 'options': ['30', '35', '40', '45'], 'answer': '40'},
        {'question': 'What is 100 / 10?', 'options': ['5', '10', '20', '100'], 'answer': '10'},
        {'question': 'What is 8 * 8?', 'options': ['16', '32', '64', '88'], 'answer': '64'},
        {'question': 'What is 50 - 20?', 'options': ['20', '30', '40', '50'], 'answer': '30'},
    ],
    'eng201': [
        {'question': 'Choose the correct sentence.', 'options': ['She go to school.', 'She goes to school.', 'She going to school.', 'She gone to school.'], 'answer': 'She goes to school.'},
        {'question': 'What is a synonym for "happy"?', 'options': ['Sad', 'Angry', 'Joyful', 'Tired'], 'answer': 'Joyful'},
        {'question': 'What is the antonym of "fast"?', 'options': ['Quick', 'Slow', 'Rapid', 'Swift'], 'answer': 'Slow'},
        {'question': 'What is the plural of "child"?', 'options': ['Childs', 'Childrens', 'Children', 'Childes'], 'answer': 'Children'},
        {'question': 'What is the past tense of "go"?', 'options': ['Goes', 'Going', 'Went', 'Gone'], 'answer': 'Went'},
        {'question': 'Identify the noun in the sentence: "The apple is red."', 'options': ['The', 'apple', 'is', 'red'], 'answer': 'apple'},
        {'question': 'Identify the verb in the sentence: "They run fast."', 'options': ['They', 'run', 'fast', 'none'], 'answer': 'run'},
        {'question': 'Identify the adjective in the sentence: "She is a beautiful girl."', 'options': ['She', 'is', 'beautiful', 'girl'], 'answer': 'beautiful'},
        {'question': 'Choose the correctly spelled word.', 'options': ['Definately', 'Definitly', 'Definitely', 'Definitely'], 'answer': 'Definitely'},
        {'question': 'What does the idiom "piece of cake" mean?', 'options': ['Hard', 'Easy', 'Tasty', 'Complicated'], 'answer': 'Easy'},
    ],
    'cs301': [
        {'question': 'What does CPU stand for?', 'options': ['Central Processing Unit', 'Computer Personal Unit', 'Central Program Unit', 'Common Processing Unit'], 'answer': 'Central Processing Unit'},
        {'question': 'What does RAM stand for?', 'options': ['Read Access Memory', 'Random Access Memory', 'Run Access Memory', 'Real Access Memory'], 'answer': 'Random Access Memory'},
        {'question': 'What does HTML stand for?', 'options': ['HyperText Markup Language', 'HyperText Machine Language', 'HyperTool Markup Language', 'HighText Markup Language'], 'answer': 'HyperText Markup Language'},
        {'question': 'What is the binary representation of the number 2?', 'options': ['01', '10', '11', '100'], 'answer': '10'},
        {'question': 'What does HTTP stand for?', 'options': ['HyperText Transfer Protocol', 'HyperText Transit Protocol', 'HighText Transfer Protocol', 'HyperText Transfer Program'], 'answer': 'HyperText Transfer Protocol'},
        {'question': 'What does OS stand for?', 'options': ['Open System', 'Operating System', 'Optical System', 'Output System'], 'answer': 'Operating System'},
        {'question': 'Who created Python?', 'options': ['Dennis Ritchie', 'Bjarne Stroustrup', 'Guido van Rossum', 'James Gosling'], 'answer': 'Guido van Rossum'},
        {'question': 'What does SQL stand for?', 'options': ['Structured Query Language', 'Simple Query Language', 'Standard Query Language', 'Sequential Query Language'], 'answer': 'Structured Query Language'},
        {'question': 'Who is considered the first computer programmer?', 'options': ['Alan Turing', 'Charles Babbage', 'Ada Lovelace', 'Grace Hopper'], 'answer': 'Ada Lovelace'},
        {'question': 'What does WWW stand for?', 'options': ['World Wide Web', 'World Web Wide', 'Wide World Web', 'Web World Wide'], 'answer': 'World Wide Web'},
    ],
}


def get_course(course_id):
    return next((course for course in COURSES if course['id'] == course_id), None)


def get_questions(course_id):
    return QUESTIONS_BY_COURSE.get(course_id, [])


def get_or_create_session(email: str, course_id: str, student_name: str = "") -> ExamSession:
    user = User.query.filter_by(email=email).first()
    active_session = ExamSession.query.filter_by(email=email, course_id=course_id, status='in_progress').order_by(ExamSession.id.desc()).first()
    if not active_session:
        active_session = ExamSession(
            user_id=user.id if user else None,
            email=email,
            student_name=student_name or (user.name if user else email),
            course_id=course_id,
            status='in_progress',
            start_time=datetime.utcnow()
        )
        db.session.add(active_session)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    return active_session


@exam.route('/exam/list')
def exam_list():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    return render_template('exam_list.html', courses=COURSES)


@exam.route('/exam/start/<course_id>')
def exam_start(course_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    course = get_course(course_id) or {'id': course_id, 'title': course_id}
    return render_template(
        'exam_form.html',
        course_id=course['id'],
        course_title=course['title'],
        name=session.get('name', ''),
        email=session.get('email', ''),
        college=session.get('college', ''),
        address=session.get('address', ''),
        city=session.get('city', ''),
        state=session.get('state', ''),
        phone=session.get('phone', ''),
    )


@exam.route('/exam/take/<course_id>', methods=['GET', 'POST'])
def exam_take(course_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    course = get_course(course_id) or {'id': course_id, 'title': course_id}
    questions = get_questions(course['id'])

    if request.method == 'POST':
        session['college'] = request.form.get('college', '')
        session['address'] = request.form.get('address', '')
        session['city'] = request.form.get('city', '')
        session['state'] = request.form.get('state', '')
        session['phone'] = request.form.get('phone', '')
        session['name'] = request.form.get('name', session.get('name', ''))
        session['email'] = request.form.get('email', session.get('email', ''))

    email = session.get('email', '')
    student_name = session.get('name', '')

    active_session = get_or_create_session(email, course['id'], student_name)
    rules = current_app.config.get('SUSPICION_RULES', SuspicionEngine.DEFAULT_RULES)

    return render_template(
        'exam_take.html',
        course_id=course['id'],
        course_title=course['title'],
        name=student_name,
        email=email,
        college=session.get('college', ''),
        address=session.get('address', ''),
        city=session.get('city', ''),
        state=session.get('state', ''),
        phone=session.get('phone', ''),
        questions=questions,
        duration_seconds=300,
        rules=rules,
        session_id=active_session.id
    )


@exam.route('/exam/monitor/face-check', methods=['POST'])
def exam_monitor_face_check():
    payload = request.get_json(silent=True) or {}
    email = payload.get('email') or session.get('email', 'anonymous')
    course_id = payload.get('course') or payload.get('course_id', 'unknown')
    image_data = payload.get('image_data')
    session_id = payload.get('session_id')

    img = face_detector_instance.decode_image(image_data)
    detection = face_detector_instance.detect_faces(img)

    face_present = detection['face_present']
    face_count = detection['face_count']

    process_res = event_logger_instance.process_face_check(
        email=email,
        course_id=course_id,
        face_present=face_present,
        face_count=face_count,
        session_id=session_id
    )

    return jsonify({
        'face_present': face_present,
        'face_count': face_count,
        'is_multi_face': detection['is_multi_face'],
        'current_absence_duration': process_res['current_absence_duration'],
        'timestamp': int(time.time()),
        'status': detection['status']
    }), 200


@exam.route('/exam/monitor/log-events', methods=['POST'])
def exam_monitor_log_events():
    payload = request.get_json(silent=True) or {}
    email = payload.get('email') or session.get('email', 'anonymous')
    course_id = payload.get('course') or payload.get('course_id', 'unknown')
    events = payload.get('events', [])
    summary = payload.get('summary', {})
    session_id = payload.get('session_id')

    logged_events = event_logger_instance.log_browser_events(
        email=email,
        course_id=course_id,
        events=events,
        session_id=session_id
    )

    engine = SuspicionEngine.from_config()
    evaluation = engine.evaluate(
        focus_loss_count=summary.get('focusLossCount', 0),
        tab_switch_count=summary.get('tabSwitchCount', 0),
        face_absence_total_seconds=summary.get('faceAbsentTotalSeconds', 0),
        multi_face_count=summary.get('multiFaceCount', 0),
        unauthorized_actions_count=summary.get('unauthorizedActionsCount', 0),
        browser_events=events
    )

    return jsonify({
        'status': 'ok',
        'suspicion_score': evaluation['suspicion_score'],
        'suspicion_level': evaluation['suspicion_level'],
        'is_suspicious': evaluation['is_suspicious'],
        'flags_triggered': evaluation['flags_triggered'],
        'rules': engine.rules
    }), 200


@exam.route('/exam/submit', methods=['POST'])
def exam_submit():
    payload = request.get_json(silent=True) or {}
    email = payload.get('email') or session.get('email')
    course_id = payload.get('course') or payload.get('course_id')
    name = payload.get('name') or session.get('name')
    answers = payload.get('answers', [])
    monitor_summary = payload.get('monitorSummary', {})
    session_id = payload.get('session_id')

    if not email or not course_id:
        return jsonify({'status': 'error', 'message': 'Missing email or course ID'}), 400

    # Finalize ongoing face absence intervals
    event_logger_instance.finalize_session_intervals(email, course_id, session_id)

    # Fetch active exam session or get from ID
    exam_session = None
    if session_id:
        exam_session = db.session.get(ExamSession, session_id)
    if not exam_session:
        exam_session = ExamSession.query.filter_by(email=email, course_id=course_id, status='in_progress').first()
    if not exam_session:
        user = User.query.filter_by(email=email).first()
        exam_session = ExamSession(
            user_id=user.id if user else None,
            email=email,
            student_name=name,
            course_id=course_id,
            start_time=datetime.utcnow()
        )
        db.session.add(exam_session)

    # Grade answers if available
    questions = get_questions(course_id)
    correct_count = 0
    for idx, q in enumerate(questions):
        if idx < len(answers) and str(answers[idx]) == q.get('answer'):
            correct_count += 1
    total_q = len(questions) or 1
    score_pct = round((correct_count / total_q) * 100.0, 1)

    exam_session.status = 'submitted'
    exam_session.end_time = datetime.utcnow()
    exam_session.score = score_pct
    exam_session.answers_json = json.dumps(answers)

    db.session.commit()

    # Query all face intervals & browser events for this session
    face_intervals = FaceAbsenceInterval.query.filter_by(session_id=exam_session.id).all()
    browser_events = BrowserEvent.query.filter_by(session_id=exam_session.id).all()

    # Evaluate suspicion with engine
    engine = SuspicionEngine.from_config()
    evaluation = engine.evaluate(
        focus_loss_count=monitor_summary.get('focusLossCount', 0),
        tab_switch_count=monitor_summary.get('tabSwitchCount', 0),
        face_absence_total_seconds=monitor_summary.get('faceAbsentTotalSeconds', 0),
        face_absence_count=monitor_summary.get('faceAbsentCount', 0),
        face_intervals=face_intervals,
        browser_events=[e.to_dict() for e in browser_events],
        multi_face_count=monitor_summary.get('multiFaceCount', 0),
        unauthorized_actions_count=monitor_summary.get('unauthorizedActionsCount', 0)
    )

    if evaluation['is_suspicious']:
        exam_session.status = 'flagged'

    # Save SuspiciousReport
    report = SuspiciousReport(
        session_id=exam_session.id,
        email=email,
        course_id=course_id,
        suspicion_score=evaluation['suspicion_score'],
        suspicion_level=evaluation['suspicion_level'],
        is_suspicious=evaluation['is_suspicious'],
    )
    report.flags_triggered = evaluation['flags_triggered']
    report.summary = evaluation['summary']

    db.session.add(report)
    db.session.commit()

    # Audit log
    log_dir = event_logger_instance.get_log_dir()
    with open(os.path.join(log_dir, 'exam_sessions.log'), 'a', encoding='utf-8') as fh:
        fh.write(f"{datetime.utcnow().isoformat()},{email},{name},{course_id},{evaluation['suspicion_score']},{evaluation['suspicion_level']}\n")

    return jsonify({
        'status': 'ok',
        'session_id': exam_session.id,
        'score': score_pct,
        'suspicion_level': evaluation['suspicion_level'],
        'is_suspicious': evaluation['is_suspicious']
    }), 200


@exam.route('/exam/report/<int:session_id>')
def exam_report(session_id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    exam_session = db.session.get(ExamSession, session_id)
    if not exam_session:
        return render_template('proctor_report.html', error="Session not found"), 404

    face_intervals = FaceAbsenceInterval.query.filter_by(session_id=session_id).order_by(FaceAbsenceInterval.id.asc()).all()
    browser_events = BrowserEvent.query.filter_by(session_id=session_id).order_by(BrowserEvent.id.asc()).all()
    report = SuspiciousReport.query.filter_by(session_id=session_id).order_by(SuspiciousReport.id.desc()).first()

    course = get_course(exam_session.course_id) or {'id': exam_session.course_id, 'title': exam_session.course_id}

    # Build question-answer review data
    questions = get_questions(exam_session.course_id)
    student_answers = []
    try:
        student_answers = json.loads(exam_session.answers_json or '[]')
    except Exception:
        student_answers = []

    correct_count = 0
    total_questions = len(questions)
    question_review = []
    for idx, q in enumerate(questions):
        chosen = student_answers[idx] if idx < len(student_answers) else ''
        correct_ans = q.get('answer', '')
        is_correct = (str(chosen) == str(correct_ans))
        if is_correct:
            correct_count += 1
        question_review.append({
            'number': idx + 1,
            'question': q['question'],
            'options': q.get('options', []),
            'chosen': chosen,
            'correct_answer': correct_ans,
            'is_correct': is_correct,
        })

    # Compute proctoring summary counts from report
    summary = report.summary if report else {}
    face_absent_count = summary.get('face_absence_count', len(face_intervals))
    multi_face_count = summary.get('multi_face_count', 0)
    tab_switch_count = summary.get('tab_switch_count', 0)

    return render_template(
        'proctor_report.html',
        exam_session=exam_session,
        face_intervals=face_intervals,
        browser_events=browser_events,
        report=report,
        course=course,
        question_review=question_review,
        correct_count=correct_count,
        total_questions=total_questions,
        face_absent_count=face_absent_count,
        multi_face_count=multi_face_count,
        tab_switch_count=tab_switch_count,
    )


@exam.route('/exam/feedback', methods=['POST'])
def feedback():
    data = request.get_json(silent=True) or {}
    log_dir = event_logger_instance.get_log_dir()
    with open(os.path.join(log_dir, 'feedback.log'), 'a', encoding='utf-8') as fh:
        fh.write(f"{datetime.utcnow().isoformat()},{data.get('user')},{data.get('message')}\n")
    return jsonify({'status': 'saved'}), 200


@exam.route('/exam/results')
def results():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    email = session.get('email')
    
    # Get all submitted exam sessions for this user
    exam_sessions = ExamSession.query.filter_by(email=email).filter(ExamSession.status.in_(['submitted', 'flagged'])).order_by(ExamSession.end_time.desc()).all()
    
    # Map to course details
    results_data = []
    for s in exam_sessions:
        course = get_course(s.course_id) or {'id': s.course_id, 'title': s.course_id}
        results_data.append({
            'session_id': s.id,
            'course_title': course['title'],
            'score': s.score,
            'status': s.status,
            'end_time': s.end_time.strftime("%B %d, %Y, %H:%M") if s.end_time else "N/A"
        })
        
    return render_template('results.html', results=results_data, name=session.get('name'))
