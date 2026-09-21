from flask import Blueprint, render_template, session, redirect, url_for, jsonify
from models.user import User
from models.proctor import ExamSession, SuspiciousReport, FaceAbsenceInterval, BrowserEvent

proctor_bp = Blueprint('proctor', __name__)


@proctor_bp.route('/proctor/dashboard')
def proctor_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    # Optional role check: standard student or proctor can view
    sessions = ExamSession.query.order_by(ExamSession.start_time.desc()).all()
    reports = SuspiciousReport.query.order_by(SuspiciousReport.created_at.desc()).all()

    reports_by_session_id = {r.session_id: r for r in reports}

    total_sessions = len(sessions)
    flagged_sessions = [s for s in sessions if s.status == 'flagged']
    flagged_count = len(flagged_sessions)
    clean_count = total_sessions - flagged_count

    return render_template(
        'proctor_dashboard.html',
        user=user,
        sessions=sessions,
        reports=reports,
        reports_by_session_id=reports_by_session_id,
        total_sessions=total_sessions,
        flagged_count=flagged_count,
        clean_count=clean_count
    )


@proctor_bp.route('/api/proctor/stats')
def proctor_stats_api():
    sessions = ExamSession.query.all()
    reports = SuspiciousReport.query.all()
    return jsonify({
        'total_sessions': len(sessions),
        'flagged_count': len([s for s in sessions if s.status == 'flagged']),
        'submitted_count': len([s for s in sessions if s.status == 'submitted']),
        'reports_count': len(reports)
    })

@proctor_bp.route('/proctor/analytics')
def proctor_analytics():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    
    from flask import current_app
    from services.analytics import ProctorAnalytics
    
    analytics = ProctorAnalytics(current_app.static_folder)
    
    reports = SuspiciousReport.query.all()
    events = BrowserEvent.query.all()
    
    score_dist_url = analytics.generate_score_distribution(reports)
    event_heatmap_url = analytics.generate_event_heatmap(events)
    clusters_url, cluster_map = analytics.run_session_clustering(reports)
    
    return render_template(
        'proctor_analytics.html',
        user=user,
        score_dist_url=score_dist_url,
        event_heatmap_url=event_heatmap_url,
        clusters_url=clusters_url,
        cluster_map=cluster_map
    )

@proctor_bp.route('/api/proctor/report/<int:session_id>/ai')
def generate_ai_report(session_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    try:
        report = SuspiciousReport.query.filter_by(session_id=session_id).first()
        if not report:
            return jsonify({'error': 'Report not found'}), 404
            
        session_obj = ExamSession.query.get(session_id)
        student_name = session_obj.student_name if session_obj else "Unknown"
        
        from services.ai_agent import IntegrityAgent
        agent = IntegrityAgent()
        
        ai_text = agent.generate_report(student_name, report.to_dict())
        
        return jsonify({'ai_report': ai_text})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f"Server error: {str(e)}"}), 500
