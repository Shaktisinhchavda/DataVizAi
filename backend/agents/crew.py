"""
CrewAI Multi-Agent Pipeline for Data Analysis & Visualization.

Flow: Orchestrator → Planner → Code Generator → (Code Executor) → Visualizer → Insight
Supports Gemini and Groq LLMs via LiteLLM.
"""

import os
import json
import time
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from backend.agents.tools import (
    data_profile_tool, code_executor_tool,
    get_current_df, get_last_result,
)

load_dotenv()

_llm = None


def get_llm():
    """Lazily initialize the LLM."""
    global _llm
    if _llm is None:
        model = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash-lite-preview-02-05")
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GROQ_API_KEY")
        
        # Standard LiteLLM routing for all models
        _llm = LLM(
            model=model,
            api_key=api_key,
            temperature=0.1,
        )
    return _llm


# ─── Agent Definitions ───────────────────────────────────────

# ─── Agent Definitions ───────────────────────────────────────

def create_agents():
    """Create a hybrid 3-agent pipeline for the optimal balance of depth and speed."""
    llm = get_llm()

    # 1. The Architect (Strategy + Schema)
    architect = Agent(
        role="Data Architect",
        goal="Structure the analysis plan and identify correct data mappings",
        backstory=(
            "You are a master strategist. First, you understand the user's intent. "
            "You MUST use the Data Profiler tool before planning any code to verify "
            "exactly which columns exist. Do not assume names like 'Revenue' exist; "
            "check if it is 'Sales', 'Amount', or something else. map user terms to "
            "actual columns explicitly in your plan."
        ),
        tools=[data_profile_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    # 2. The Data Scientist (Analysis + Visualization)
    data_scientist = Agent(
        role="Data Scientist",
        goal="Write and execute code for analysis and optional visualization",
        backstory=(
            "You are a coding powerhouse. Based on the Architect's plan, you write "
            "Python pandas and plotly code. You use the Code Executor to run it. "
            "You MUST print() the final aggregated results (sums, counts, averages) "
            "clearly so the Insight Analyst can see the exact ground-truth numbers."
        ),
        tools=[code_executor_tool],
        llm=llm,
        verbose=True,
        allow_delegation=False,
        max_iter=3,
    )

    # 3. The Insight Analyst (Synthesis)
    insight_analyst = Agent(
        role="Insight Analyst",
        goal="Generate a rich, multi-paragraph business narrative and JSON output",
        backstory=(
            "You are a senior business analyst known for deep narrative depth. "
            "You synthesize the raw data results into a structured JSON object. "
            "CRITICAL: Do not just list stats. Provide a 2-3 paragraph explanation of "
            "the 'WHY' behind the data. If comparing Date vs Open, talk about the "
            "progression, volatility, and specific periods of growth or decline. "
            "Every claim must be CROSS-CHECKED against the raw numbers from the Data Scientist."
        ),
        llm=llm,
        verbose=True,
        allow_delegation=False,
    )

    return {
        "architect": architect,
        "data_scientist": data_scientist,
        "insight_analyst": insight_analyst,
    }


# ─── Pipeline Execution ──────────────────────────────────────

def run_analysis_crew(user_query: str, data_summary_text: str) -> dict:
    """Run the optimized hybrid pipeline."""
    short_ctx = data_summary_text[:600]
    agents = create_agents()

    # Task 1: Architecture & Schema
    arch_task = Task(
        description=f"Plan the analysis for: '{user_query}'. Map query terms to real columns using Data Profiler.",
        expected_output="A strategy and precise column mapping (e.g., 'segment' -> 'Customer_Segment').",
        agent=agents["architect"],
    )

    # Task 2: Data & Viz Execution
    execute_task = Task(
        description=f"Execute the full analysis for: '{user_query}'. Write Pandas/Plotly code using the Architect's mapping. print() the result and assign figure to 'fig'.",
        expected_output="The output from code execution including printed findings and optional chart.",
        agent=agents["data_scientist"],
    )

    # Task 3: Narrative Synthesis
    insight_task = Task(
        description=f"""Synthesize findings for: '{user_query}'. 
        Output a structured JSON with: 'preview' (string), 'insights' (list), and 'chart_status' (Boolean).""",
        expected_output="A structured JSON summary with business-ready insights.",
        agent=agents["insight_analyst"],
    )

    crew = Crew(
        agents=list(agents.values()),
        tasks=[arch_task, execute_task, insight_task],
        process=Process.sequential,
        verbose=True,
    )

    # Execute with retry for rate limits
    max_retries = 3
    print(f"[Crew] Starting analysis for: {user_query[:50]}...")
    for attempt in range(max_retries):
        try:
            start_time = time.time()
            print(f"[Crew] Kickoff attempt {attempt+1}...")
            result = crew.kickoff()
            elapsed = time.time() - start_time
            print(f"[Crew] Pipeline finished in {elapsed:.1f}s")
            return parse_pipeline_output(result)
        except Exception as e:
            error_str = str(e).lower()
            if "rate_limit" in error_str or "429" in error_str:
                wait = 30 * (attempt + 1)
                print(f"[Rate limit] Waiting {wait}s (retry {attempt+1}/{max_retries})...")
                time.sleep(wait)
                global _llm
                _llm = None
            else:
                print(f"[Pipeline error] {e}")
                last = get_last_result()
                if last and last.get("success"):
                    return {
                        "analysis": last.get("stdout", str(e)),
                        "chart": last.get("chart"),
                        "agent_steps": [],
                    }
                raise

    return {
        "analysis": "AI service rate-limited. Please wait a minute and try again.",
        "chart": None,
        "agent_steps": [],
    }


def parse_pipeline_output(result) -> dict:
    """Parse the crew output to extract analysis text and chart JSON."""
    output = {
        "analysis": "",
        "chart": None,
        "agent_steps": [],
    }

    last = get_last_result()
    if last:
        output["chart"] = last.get("chart")

    raw_result = str(result)
    
    try:
        if "{" in raw_result and "}" in raw_result:
            import re
            m = re.search(r'(\{.*?\})', raw_result, re.DOTALL)
            if m:
                # Clean up any potential markdown backticks or formatting
                clean_json = m.group(1).replace("```json", "").replace("```", "").strip()
                data = json.loads(clean_json)
                preview = data.get("preview", "")
                insights_list = data.get("insights", [])
                insights = "\n".join([f"• {i}" for i in insights_list])
                output["analysis"] = f"{preview}\n\n{insights}"
            else:
                output["analysis"] = raw_result
        else:
            output["analysis"] = raw_result
    except Exception:
        output["analysis"] = raw_result

    if not output["analysis"] and last and last.get("stdout"):
        output["analysis"] = last.get("stdout")

    return output

