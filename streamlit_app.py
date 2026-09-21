import streamlit as st
import pandas as pd
import sqlite3
import os
import json
from datetime import datetime
import base64

# Configure Page
st.set_page_config(
    page_title="Proctor Dashboard | Online Exam System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Premium Design
st.markdown("""
<style>
    /* Main Background and Text */
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }
    
    /* Cards / Metrics */
    div[data-testid="metric-container"] {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1.5rem;
        border-radius: 0.75rem;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #1E293B;
        border-right: 1px solid rgba(255, 255, 255, 0.05);
    }
    
    /* Dataframes */
    .stDataFrame {
        border-radius: 0.5rem;
        overflow: hidden;
    }
    
    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #6366F1 0%, #4F46E5 100%);
        color: white;
        border: none;
        border-radius: 0.5rem;
        padding: 0.5rem 1rem;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(99, 102, 241, 0.4);
    }
</style>
""", unsafe_allow_html=True)

# Database Connection
DB_PATH = os.path.join(os.path.dirname(__file__), "database.db")

@st.cache_resource
def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def load_data(query, params=None):
    conn = get_connection()
    if params:
        return pd.read_sql_query(query, conn, params=params)
    return pd.read_sql_query(query, conn)

# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=60)
st.sidebar.title("Proctor Control")
st.sidebar.markdown("---")
page = st.sidebar.radio("Navigation", ["Overview", "Live Sessions", "Risk Analytics", "Export Center"])
st.sidebar.markdown("---")
st.sidebar.info("System Status: **Active** 🟢")

# ---------------------------------------------------------
# Page: Overview
# ---------------------------------------------------------
if page == "Overview":
    st.title("🛡️ Proctor Dashboard Overview")
    st.markdown("Monitor online examination integrity in real-time.")
    
    # KPIs
    sessions_df = load_data("SELECT * FROM exam_sessions")
    reports_df = load_data("SELECT * FROM suspicious_reports")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sessions", len(sessions_df) if not sessions_df.empty else 0)
    with col2:
        active = len(sessions_df[sessions_df['status'] == 'in_progress']) if not sessions_df.empty else 0
        st.metric("Active Sessions", active)
    with col3:
        high_risk = len(reports_df[reports_df['suspicion_level'].isin(['HIGH', 'CRITICAL'])]) if not reports_df.empty else 0
        st.metric("High Risk Flags", high_risk, delta_color="inverse", delta=f"{high_risk} alerts")
    with col4:
        avg_score = round(reports_df['suspicion_score'].mean(), 1) if not reports_df.empty else 0.0
        st.metric("Avg Suspicion Score", f"{avg_score}%")
        
    st.markdown("### Recent Suspicious Activity")
    if not reports_df.empty:
        recent = reports_df.sort_values(by='created_at', ascending=False).head(5)
        st.dataframe(recent[['email', 'course_id', 'suspicion_score', 'suspicion_level', 'created_at']], use_container_width=True)
    else:
        st.info("No suspicious reports found.")

# ---------------------------------------------------------
# Page: Risk Analytics
# ---------------------------------------------------------
elif page == "Risk Analytics":
    st.title("📈 Data Science Risk Analytics")
    
    reports_df = load_data("SELECT * FROM suspicious_reports")
    events_df = load_data("SELECT * FROM browser_events")
    
    if reports_df.empty:
        st.warning("Insufficient data for analytics.")
    else:
        tab1, tab2, tab3 = st.tabs(["Score Distribution", "Event Heatmap", "Session Clustering"])
        
        with tab1:
            st.markdown("### Integrity Score Distribution")
            import matplotlib.pyplot as plt
            import seaborn as sns
            
            fig, ax = plt.subplots(figsize=(10, 5))
            fig.patch.set_facecolor('#0F172A')
            ax.set_facecolor('#0F172A')
            ax.tick_params(colors='white')
            ax.xaxis.label.set_color('white')
            ax.yaxis.label.set_color('white')
            ax.title.set_color('white')
            
            sns.histplot(data=reports_df, x='suspicion_score', bins=15, kde=True, color='#6366F1', ax=ax)
            ax.set_title("Distribution of Suspicion Scores")
            st.pyplot(fig)
            
        with tab2:
            st.markdown("### Browser Event Frequency by Hour")
            if not events_df.empty:
                events_df['datetime'] = pd.to_datetime(events_df['timestamp'], unit='ms')
                events_df['hour'] = events_df['datetime'].dt.hour
                pivot_df = events_df.groupby(['hour', 'event_type']).size().unstack(fill_value=0)
                
                fig, ax = plt.subplots(figsize=(12, 6))
                fig.patch.set_facecolor('#0F172A')
                ax.set_facecolor('#0F172A')
                ax.tick_params(colors='white')
                sns.heatmap(pivot_df, cmap='magma', annot=True, fmt='d', linewidths=.5, ax=ax)
                st.pyplot(fig)
            else:
                st.info("No browser events available.")
                
        with tab3:
            st.markdown("### K-Means Session Clustering (Risk Cohorts)")
            from sklearn.cluster import KMeans
            
            if len(reports_df) >= 3:
                reports_df['flags_count'] = reports_df['flags_triggered_json'].apply(lambda x: len(json.loads(x)) if isinstance(x, str) else 0)
                X = reports_df[['suspicion_score', 'flags_count']]
                kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
                reports_df['cluster'] = kmeans.fit_predict(X)
                
                fig, ax = plt.subplots(figsize=(10, 6))
                fig.patch.set_facecolor('#0F172A')
                ax.set_facecolor('#0F172A')
                ax.tick_params(colors='white')
                sns.scatterplot(data=reports_df, x='flags_count', y='suspicion_score', hue='cluster', palette='coolwarm', s=100, ax=ax)
                st.pyplot(fig)
                
                st.markdown("#### Cohort Data")
                st.dataframe(reports_df[['email', 'suspicion_score', 'flags_count', 'cluster']], use_container_width=True)
            else:
                st.info("Need at least 3 reports for clustering.")

# ---------------------------------------------------------
# Page: Export Center
# ---------------------------------------------------------
elif page == "Export Center":
    st.title("📥 Export Session Outputs")
    st.markdown("Download JSON and CSV exports of all monitoring data.")
    
    tables = {
        "Exam Sessions": "exam_sessions",
        "Suspicious Reports": "suspicious_reports",
        "Browser Events": "browser_events",
        "Face Absence Intervals": "face_absence_intervals"
    }
    
    selected_table = st.selectbox("Select Data to Export", list(tables.keys()))
    
    if st.button("Generate Export"):
        df = load_data(f"SELECT * FROM {tables[selected_table]}")
        
        st.markdown(f"### Preview: {selected_table}")
        st.dataframe(df.head(10), use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"{tables[selected_table]}_export.csv",
                mime="text/csv",
            )
            
        with col2:
            json_str = df.to_json(orient='records', lines=True)
            st.download_button(
                label="Download JSON",
                data=json_str,
                file_name=f"{tables[selected_table]}_export.json",
                mime="application/json",
            )

# ---------------------------------------------------------
# Page: Live Sessions (AI Summaries Placeholder)
# ---------------------------------------------------------
elif page == "Live Sessions":
    st.title("📹 Live Monitor & AI Summaries")
    
    sessions_df = load_data("SELECT * FROM exam_sessions WHERE status='in_progress'")
    reports_df = load_data("SELECT * FROM suspicious_reports")
    
    if sessions_df.empty:
        st.info("No live sessions at the moment.")
    else:
        for idx, session in sessions_df.iterrows():
            with st.expander(f"Session: {session['email']} | Course: {session['course_id']}"):
                st.write(f"**Start Time:** {session['start_time']}")
                
                session_report = reports_df[reports_df['session_id'] == session['id']]
                if not session_report.empty:
                    rep = session_report.iloc[0]
                    st.warning(f"**Risk Level:** {rep['suspicion_level']} | **Score:** {rep['suspicion_score']}")
                    
                    try:
                        summary = json.loads(rep['summary_json'])
                        if 'ai_summary' in summary:
                            st.markdown("#### AI Integrity Report")
                            st.write(summary['ai_summary'])
                    except:
                        pass
                else:
                    st.success("No suspicious activity reported yet.")
