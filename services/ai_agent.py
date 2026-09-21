import os
import json
from typing import Dict, Any, List
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate

class IntegrityAgent:
    """
    LangChain-based AI Integrity Report Agent.
    Analyzes session logs and scores to generate a natural language integrity report.
    """
    def __init__(self):
        self.api_key = os.environ.get("GOOGLE_API_KEY")
        self.llm = None
        
        if self.api_key:
            try:
                self.llm = ChatGoogleGenerativeAI(
                    model="gemini-1.5-flash",
                    temperature=0.2,
                    google_api_key=self.api_key
                )
            except Exception as e:
                logging.error(f"Failed to initialize LangChain LLM: {e}")
        else:
            logging.warning("GOOGLE_API_KEY not found. AI Agent will run in mock mode.")

        self.prompt_template = PromptTemplate(
            input_variables=["student_name", "score", "risk_level", "event_summary", "flags"],
            template="""
You are an AI Proctoring Assistant for an online exam system.
Review the following exam session data and provide a concise, professional integrity report.

Student Name: {student_name}
Integrity Score: {score}/100 (Higher is more suspicious)
Risk Level: {risk_level}
Triggered Flags: {flags}

Event Summary (Browser Activity & Face Detection):
{event_summary}

Based on this data, provide:
1. An overall assessment of the session's integrity.
2. A brief analysis of the specific events and flags.
3. A recommendation on whether human review is required.

Keep the response strictly professional, objective, and under 3 paragraphs.
"""
        )
        
        if self.llm:
            try:
                self.chain = self.prompt_template | self.llm
            except Exception as e:
                logging.error(f"Failed to create LCEL chain: {e}")
                self.chain = None
        else:
            self.chain = None

    def generate_report(self, student_name: str, report_data: Dict[str, Any]) -> str:
        """Generates the AI integrity report."""
        score = report_data.get('suspicion_score', 0)
        risk_level = report_data.get('suspicion_level', 'UNKNOWN')
        flags = ", ".join(report_data.get('flags_triggered', [])) or "None"
        summary = json.dumps(report_data.get('summary', {}), indent=2)
        
        if self.chain:
            try:
                result = self.chain.invoke({
                    "student_name": student_name or "Unknown Student",
                    "score": score,
                    "risk_level": risk_level,
                    "flags": flags,
                    "event_summary": summary
                })
                # Result might be an AIMessage object, so extract the text content
                if hasattr(result, 'content'):
                    return result.content.strip()
                return str(result).strip()
            except Exception as e:
                logging.error(f"Error generating AI report: {e}")
                return f"Error generating AI report: {str(e)}"
        else:
            # Mock response if no API key
            return (
                f"**MOCK AI REPORT (No API Key)**\n\n"
                f"Based on the Integrity Score of {score} ({risk_level} risk), "
                f"the system noted the following flags: {flags}.\n"
                f"Please review the detailed logs. Set GOOGLE_API_KEY to enable real AI analysis."
            )
