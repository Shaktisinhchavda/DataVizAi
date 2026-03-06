"""
Tools for CrewAI agents.
- CodeExecutorTool: Executes Python (pandas/plotly) code in a sandboxed environment
- DataProfileTool: Quick dataset inspection
"""

import json
import io
import sys
import traceback
from typing import Type
import pandas as pd
import plotly
import plotly.express as px
import plotly.graph_objects as go
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

# ─── Global Data Store ────────────────────────────────────────

_current_df: pd.DataFrame = None
_current_summary: dict = None
_last_execution_result: dict = None  # Stores last code execution output


def set_current_data(df: pd.DataFrame, summary: dict):
    """Set the current DataFrame for tools to use."""
    global _current_df, _current_summary
    _current_df = df
    _current_summary = summary


def get_current_df() -> pd.DataFrame:
    return _current_df


def get_last_result() -> dict:
    return _last_execution_result


# ─── Code Executor Tool ──────────────────────────────────────

class CodeExecutorInput(BaseModel):
    code: str = Field(
        description="Python code to execute. Has access to 'df' (the pandas DataFrame), 'pd' (pandas), 'px' (plotly.express), and 'go' (plotly.graph_objects). Print results to stdout. To create a chart, assign it to a variable called 'fig'."
    )


class CodeExecutorTool(BaseTool):
    name: str = "Code Executor"
    description: str = (
        "Execute Python code for data analysis or visualization. "
        "You have access to: df (pandas DataFrame), pd (pandas), px (plotly.express), go (plotly.graph_objects). "
        "Print analysis results with print(). For charts, assign the plotly figure to a variable named 'fig'. "
        "Example analysis: print(df.groupby('Category')['Sales'].sum()) "
        "Example chart: fig = px.bar(df.groupby('Category')['Sales'].sum().reset_index(), x='Category', y='Sales', title='Sales by Category')"
    )
    args_schema: Type[BaseModel] = CodeExecutorInput

    def _run(self, code: str) -> str:
        global _last_execution_result
        if _current_df is None:
            return "Error: No data loaded."

        # Clean up code — remove markdown code fences if present
        code = code.strip()
        if code.startswith("```python"):
            code = code[len("```python"):].strip()
        if code.startswith("```"):
            code = code[3:].strip()
        if code.endswith("```"):
            code = code[:-3].strip()

        # Set up sandboxed execution environment
        local_vars = {
            "df": _current_df.copy(),
            "pd": pd,
            "px": px,
            "go": go,
            "json": json,
        }

        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()

        try:
            exec(code, {"__builtins__": __builtins__}, local_vars)

            stdout_text = captured_output.getvalue()

            # Check for a plotly figure
            fig = local_vars.get("fig", None)
            chart_json = None
            if fig is not None:
                try:
                    # Apply dark theme
                    fig.update_layout(
                        template="plotly_dark",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Inter, sans-serif"),
                        margin=dict(l=40, r=40, t=60, b=40),
                    )
                    chart_json = json.loads(plotly.io.to_json(fig))
                except Exception as e:
                    stdout_text += f"\nChart serialization error: {e}"

            # Check for result DataFrame
            result_df = local_vars.get("result", None)
            if isinstance(result_df, pd.DataFrame):
                stdout_text += f"\n{result_df.to_string()}"
            elif isinstance(result_df, pd.Series):
                stdout_text += f"\n{result_df.to_string()}"

            # Store the execution result globally
            _last_execution_result = {
                "stdout": stdout_text.strip(),
                "chart": chart_json,
                "success": True,
            }

            output = stdout_text.strip() if stdout_text.strip() else "(Code executed successfully, no output printed)"
            if chart_json:
                output += "\n[Chart generated successfully]"

            return output

        except Exception as e:
            error_msg = f"Code execution error: {type(e).__name__}: {str(e)}"
            _last_execution_result = {
                "stdout": error_msg,
                "chart": None,
                "success": False,
            }
            return error_msg

        finally:
            sys.stdout = old_stdout


# ─── Data Profile Tool ───────────────────────────────────────

class DataProfileInput(BaseModel):
    aspect: str = Field(
        description="One of: overview, columns, statistics, missing, sample, dtypes"
    )


class DataProfileTool(BaseTool):
    name: str = "Data Profiler"
    description: str = (
        "Get information about the dataset. Set aspect to one of: "
        "overview (shape + columns), columns (detailed column info), "
        "statistics (describe()), missing (null counts), sample (first 5 rows), "
        "dtypes (data types of each column)."
    )
    args_schema: Type[BaseModel] = DataProfileInput

    def _run(self, aspect: str) -> str:
        if _current_df is None:
            return "No data loaded."
        df = _current_df
        try:
            if aspect == "overview":
                cols_info = ", ".join(f"{c} ({df[c].dtype})" for c in df.columns)
                return (
                    f"Shape: {df.shape[0]} rows × {df.shape[1]} columns\n"
                    f"Columns: {cols_info}\n"
                    f"Numeric: {df.select_dtypes(include='number').columns.tolist()}\n"
                    f"Categorical: {df.select_dtypes(include=['object','category']).columns.tolist()}"
                )
            elif aspect == "columns":
                return "\n".join(
                    f"- {c}: type={df[c].dtype}, nulls={df[c].isnull().sum()}, "
                    f"unique={df[c].nunique()}, sample={df[c].iloc[0]}"
                    for c in df.columns
                )
            elif aspect == "statistics":
                return df.describe(include="all").to_string()
            elif aspect == "missing":
                return f"Missing values:\n{df.isnull().sum().to_string()}"
            elif aspect == "sample":
                return f"First 5 rows:\n{df.head(5).to_string()}"
            elif aspect == "dtypes":
                return df.dtypes.to_string()
            else:
                return "Unknown aspect. Use: overview, columns, statistics, missing, sample, dtypes"
        except Exception as e:
            return f"Error: {e}"


# ─── Create tool instances ───────────────────────────────────

data_profile_tool = DataProfileTool()
code_executor_tool = CodeExecutorTool()
