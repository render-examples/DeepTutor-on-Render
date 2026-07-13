#!/usr/bin/env python
"""
Constants for DeepTutor
"""

from pathlib import Path

# Project root directory - central location for all path calculations
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# Valid tools for investigate agent
VALID_INVESTIGATE_TOOLS = ["rag", "web_search", "none"]

# Valid tools for solve agent
VALID_SOLVE_TOOLS = [
    "web_search",
    "code_execution",
    "rag",
    "none",
    "finish",
]

# Standard stdlib log level tags.
LOG_LEVEL_TAGS = [
    "DEBUG",
    "INFO",
    "WARNING",
    "ERROR",
    "CRITICAL",
]

# Canonical model pricing table (USD per 1K tokens), shared by the research
# token tracker and the LLM stats logger so the two never drift. OpenAI's
# GPT-5.6 family is priced per 1M tokens upstream (Luna $1/$6, Terra $2.50/$15,
# Sol $5/$30) — divide by 1000 for the per-1K rates below.
MODEL_PRICING = {
    # OpenAI GPT-5.6 family
    "gpt-5.6-luna": {"input": 0.001, "output": 0.006},
    "gpt-5.6-terra": {"input": 0.0025, "output": 0.015},
    "gpt-5.6-sol": {"input": 0.005, "output": 0.030},
    # OpenAI legacy
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
    # DeepSeek
    "deepseek-chat": {"input": 0.00014, "output": 0.00028},
    "deepseek-coder": {"input": 0.00014, "output": 0.00028},
    "deepseek-v4-flash": {"input": 0.00014, "output": 0.00028},
    "deepseek-v4-pro": {"input": 0.000435, "output": 0.00087},
    # Anthropic Claude
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
}
