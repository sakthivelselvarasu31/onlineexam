import os
import io
import base64
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Anti-Grain Geometry (Agg) backend so Matplotlib doesn't use Xwindows or GUI
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.cluster import KMeans
from typing import List, Dict, Any, Tuple
from models.proctor import ExamSession, SuspiciousReport, BrowserEvent

class ProctorAnalytics:
    def __init__(self, static_dir: str):
        self.static_dir = static_dir
        self.analytics_dir = os.path.join(static_dir, 'analytics')
        os.makedirs(self.analytics_dir, exist_ok=True)
        
        # Set Seaborn theme for premium look
        sns.set_theme(style="darkgrid")
        plt.style.use("dark_background")
        
    def generate_score_distribution(self, reports: List[SuspiciousReport]) -> str:
        """Generates a histogram of integrity scores."""
        if not reports:
            return ""
            
        scores = [r.suspicion_score for r in reports]
        df = pd.DataFrame({'Score': scores})
        
        plt.figure(figsize=(10, 6))
        ax = sns.histplot(data=df, x='Score', bins=10, kde=True, color='#4F46E5')
        plt.title('Integrity Score Distribution', fontsize=16, color='white')
        plt.xlabel('Suspicion Score', color='white')
        plt.ylabel('Frequency', color='white')
        
        filepath = os.path.join(self.analytics_dir, 'score_dist.png')
        plt.savefig(filepath, transparent=True, bbox_inches='tight')
        plt.close()
        
        return 'analytics/score_dist.png'
        
    def generate_event_heatmap(self, events: List[BrowserEvent]) -> str:
        """Generates a heatmap of browser events over time/type."""
        if not events:
            return ""
            
        df = pd.DataFrame([e.to_dict() for e in events])
        if df.empty or 'event_type' not in df.columns or 'timestamp' not in df.columns:
            return ""
            
        # Convert timestamp to datetime
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['hour'] = df['datetime'].dt.hour
        
        # Group by hour and event type
        pivot_df = df.groupby(['hour', 'event_type']).size().unstack(fill_value=0)
        
        plt.figure(figsize=(12, 8))
        sns.heatmap(pivot_df, cmap='magma', annot=True, fmt='d', linewidths=.5)
        plt.title('Event Frequency Heatmap by Hour', fontsize=16, color='white')
        plt.xlabel('Event Type', color='white')
        plt.ylabel('Hour of Day', color='white')
        
        filepath = os.path.join(self.analytics_dir, 'event_heatmap.png')
        plt.savefig(filepath, transparent=True, bbox_inches='tight')
        plt.close()
        
        return 'analytics/event_heatmap.png'
        
    def run_session_clustering(self, reports: List[SuspiciousReport]) -> Tuple[str, Dict[int, str]]:
        """
        Uses K-Means to cluster sessions based on suspicion_score and number of flags.
        Returns the path to the plot and a dict mapping cluster IDs to risk profiles.
        """
        if len(reports) < 3:
            return "", {}
            
        data = []
        for r in reports:
            flags_count = len(r.flags_triggered) if r.flags_triggered else 0
            data.append({
                'session_id': r.session_id,
                'score': r.suspicion_score,
                'flags_count': flags_count
            })
            
        df = pd.DataFrame(data)
        
        # K-Means Clustering (3 clusters: Low, Medium, High risk)
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        df['cluster'] = kmeans.fit_predict(df[['score', 'flags_count']])
        
        # Map clusters to risk profiles based on average score
        cluster_means = df.groupby('cluster')['score'].mean().sort_values()
        risk_labels = ['Low Risk Cohort', 'Medium Risk Cohort', 'High Risk Cohort']
        cluster_map = {cluster_id: risk_labels[i] for i, cluster_id in enumerate(cluster_means.index)}
        
        df['Risk Profile'] = df['cluster'].map(cluster_map)
        
        plt.figure(figsize=(10, 6))
        sns.scatterplot(
            data=df, x='flags_count', y='score', hue='Risk Profile', 
            palette={'Low Risk Cohort': '#10B981', 'Medium Risk Cohort': '#F59E0B', 'High Risk Cohort': '#EF4444'},
            s=100, alpha=0.8
        )
        plt.title('K-Means Session Clustering', fontsize=16, color='white')
        plt.xlabel('Number of Flags Triggered', color='white')
        plt.ylabel('Suspicion Score', color='white')
        
        filepath = os.path.join(self.analytics_dir, 'session_clusters.png')
        plt.savefig(filepath, transparent=True, bbox_inches='tight')
        plt.close()
        
        return 'analytics/session_clusters.png', cluster_map
