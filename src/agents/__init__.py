"""
Agentic Workflows Module for MegaDoc.

Provides LangGraph-based agents for complex, multi-step document analysis.

Available Agents:
- InvestigatorAgent: Mission-driven document investigation with 4-node workflow
  (Decomposer -> Retriever -> Analyzer -> Validator)
"""

from agents.investigator import InvestigatorAgent, InvestigatorState

__all__ = ['InvestigatorAgent', 'InvestigatorState']
