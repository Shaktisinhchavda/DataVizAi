"""
FastAPI application — Main API server for DataViz AI.
Handles file uploads, queries, and WebSocket connections.
"""

import os
import json
import asyncio
import traceback
from pathlib import Path
from typing import Optional
import pandas as pd

import sys
import io

# Fix Windows console emoji encoding errors ('charmap' codec can't encode) used by CrewAI
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
if sys.stderr.encoding.lower() != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from backend.services.file_service import (
    save_uploaded_file,
    load_dataframe,
    get_data_summary,
    get_data_as_text,
)
from backend.agents.tools import set_current_data
from backend.agents.crew import run_analysis_crew

load_dotenv()

app = FastAPI(
    title="DataViz AI",
    description="AI-Powered Data Visualization Platform",
    version="1.0.0",
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory session storage
sessions = {}


class QueryRequest(BaseModel):
    session_id: str
    query: str


class SessionData:
    def __init__(self, file_info: dict, df, summary: dict, data_text: str):
        self.file_info = file_info
        self.df = df
        self.summary = summary
        self.data_text = data_text
        self.chat_history = []


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "DataViz AI"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a CSV or Excel file for analysis."""
    try:
        # Validate file type
        ext = Path(file.filename).suffix.lower()
        if ext not in [".csv", ".xlsx", ".xls"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Please upload CSV or Excel files.",
            )

        # Read and save
        contents = await file.read()
        file_info = save_uploaded_file(contents, file.filename)

        # Load into DataFrame
        df = load_dataframe(file_info["path"])
        summary = get_data_summary(df)
        data_text = get_data_as_text(df)

        # Set data for agent tools
        set_current_data(df, summary)

        # Store session
        session = SessionData(file_info, df, summary, data_text)
        sessions[file_info["session_id"]] = session

        return {
            "session_id": file_info["session_id"],
            "filename": file_info["filename"],
            "summary": summary,
            "preview": df.head(20).to_dict(orient="records"),
            "columns": df.columns.tolist(),
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@app.post("/api/query")
async def query_data(request: QueryRequest):
    """Send a natural language query to the multi-agent pipeline."""
    session = sessions.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found. Please upload a file first.")

    try:
        # Ensure current data is set for tools
        set_current_data(session.df, session.summary)

        query_lower = request.query.lower()
        query_type = await asyncio.get_event_loop().run_in_executor(
            None, classify_query, query_lower
        )

        # Generate chart instantly (direct handler)
        if query_type == "summary":
            result = generate_summary_response(session.df)
        elif query_type == "viz":
            result = generate_direct_response(session.df, request.query)
        else:
            # Complex analysis — try pipeline, fallback to direct
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, run_analysis_crew, request.query, session.data_text
                )
            except Exception as e:
                print(f"[Pipeline fallback] {e}")
                result = generate_direct_response(session.df, request.query)

        # Enhance the raw stats with LLM-generated insights (ONLY for direct/viz path)
        # Deep analysis pipeline already has an Insight Generator
        raw_analysis = result.get("analysis", "")
        if query_type != "analysis" and raw_analysis and not raw_analysis.startswith("⚠️"):
            try:
                enhanced = await asyncio.get_event_loop().run_in_executor(
                    None, enhance_with_llm, request.query, raw_analysis, session.summary
                )
                if enhanced:
                    result["analysis"] = enhanced
            except Exception as e:
                print(f"[LLM enhance skipped] {e}")

        # Add to chat history
        session.chat_history.append({"role": "user", "content": request.query})
        session.chat_history.append({
            "role": "assistant",
            "content": result.get("analysis", ""),
            "chart": result.get("chart"),
        })

        return {
            "analysis": result.get("analysis", "No analysis available."),
            "chart": result.get("chart"),
            "agent_steps": result.get("agent_steps", []),
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


def enhance_with_llm(user_query: str, raw_stats: str, data_summary: dict) -> str:
    """Use Gemini to rewrite raw stats into polished, insightful analysis."""
    import os

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    model_name = os.getenv("LLM_MODEL", "gemini/gemini-3.1-flash-lite-preview")
    # Strip the "gemini/" prefix for the SDK
    model_name = model_name.replace("gemini/", "")

    prompt = f"""User asked: "{user_query}"
Data stats: {raw_stats[:500]}

Write 2-3 sentence analysis. Be specific with numbers. Interpret the data, don't just repeat it. Use professional language."""

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        text = response.text.strip() if response.text else None
        return text
    except Exception as e:
        print(f"[LLM enhance error] {e}")
        return None


def classify_query_fallback(q: str) -> str:
    """Fallback keyword-based classification."""
    analysis_keywords = [
        "why", "explain", "predict", "recommend", "reason", "cause", 
        "what if", "forecast", "anomal", "underperform", "outperform",
        "strategy", "conclusion", "deep dive"
    ]
    if any(kw in q for kw in analysis_keywords):
        return "analysis"

    summary_keywords = [
        "summary", "summarize", "describe", "overview", "info",
        "tell me about", "what is this", "what's in", "columns",
        "dataset", "data info", "shape", "how many rows",
        "how many columns", "what data"
    ]
    if any(kw in q for kw in summary_keywords):
        return "summary"

    viz_keywords = [
        "chart", "bar", "pie", "line", "scatter", "histogram",
        "heatmap", "box plot", "plot", "graph", "visualize",
        "distribution", "trend", "trends", "compare", "correlation",
        "top", "dashboard", "over time", "show me", "show the",
        "give me", "display", "by", "vs", "per", "across", "between",
        "highest", "lowest", "most", "least", "average", "total"
    ]
    if any(kw in q for kw in viz_keywords):
        return "viz"
    return "analysis"


def classify_query(q: str) -> str:
    """Classify query intelligently using Gemini into: summary, viz, or analysis."""
    import os
    from google import genai

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return classify_query_fallback(q)

    model_name = os.getenv("LLM_MODEL", "gemini/gemini-3.1-flash-lite-preview")
    model_name = model_name.replace("gemini/", "")
    
    prompt = f'''You are a Senior Data Query Architect. Your job is to route user queries to the most capable internal engine.
User Query: "{q}"

Classify it into exactly ONE of these three categories:
1. "summary": Quick requests for dataset info, column lists, or general overviews ("what's in here?", "show columns").
2. "viz": Direct requests for specific charts ("pie chart of sales", "histogram of ages") or simple single-stat lookups ("what is the max sales?").
3. "analysis": ANY query asking about "Relationships", "Trends", "Why", "Reason", "Explain", "Compare", or "Analyze". If the user wants to understand patterns or multi-column correlations, use this. Relationship queries MUST be analysis.

Respond with ONLY the category name: summary, viz, or analysis. No punctuation.'''

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        cat = response.text.strip().lower()
        if "summary" in cat: return "summary"
        if "viz" in cat: return "viz"
        if "analysis" in cat: return "analysis"
    except Exception as e:
        print(f"[LLM Classify Error] {e}")
        pass
        
    return classify_query_fallback(q)


def generate_summary_response(df) -> dict:
    """Generate a comprehensive data summary."""
    import plotly
    import plotly.express as px

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    date_cols = [c for c in df.columns if "date" in c.lower() or "time" in c.lower()]

    parts = []
    parts.append(f"📊 **Dataset Overview**")
    parts.append(f"• Rows: {df.shape[0]:,} | Columns: {df.shape[1]}")
    parts.append(f"• Memory: {df.memory_usage(deep=True).sum() / 1024:.1f} KB")
    parts.append("")

    if cat_cols:
        parts.append(f"📝 **Categorical Columns** ({len(cat_cols)}):")
        for c in cat_cols:
            parts.append(f"• {c}: {df[c].nunique()} unique values ({', '.join(df[c].value_counts().head(3).index.tolist())}...)")
        parts.append("")

    if numeric_cols:
        parts.append(f"🔢 **Numeric Columns** ({len(numeric_cols)}):")
        for c in numeric_cols:
            parts.append(f"• {c}: min={df[c].min():.2f}, max={df[c].max():.2f}, mean={df[c].mean():.2f}")
        parts.append("")

    if date_cols:
        parts.append(f"📅 **Date Columns**: {', '.join(date_cols)}")
        parts.append("")

    missing = df.isnull().sum()
    if missing.any():
        parts.append(f"⚠️ **Missing Values**:")
        for c in missing[missing > 0].index:
            parts.append(f"• {c}: {missing[c]} missing ({missing[c]/len(df)*100:.1f}%)")
    else:
        parts.append(f"✅ No missing values")

    # Create a summary chart — column averages for numeric cols
    chart = None
    if numeric_cols:
        try:
            stats = df[numeric_cols].describe().loc[["mean", "min", "max"]].T.reset_index()
            stats.columns = ["Column", "Mean", "Min", "Max"]
            fig = px.bar(stats, x="Column", y="Mean", title="Average Values by Column",
                         text="Mean", color="Mean", color_continuous_scale="viridis")
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, sans-serif"),
                margin=dict(l=40, r=40, t=60, b=40),
            )
            fig.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            chart = json.loads(plotly.io.to_json(fig))
        except Exception:
            pass

    return {"analysis": "\n".join(parts), "chart": chart, "agent_steps": []}


def generate_direct_response(df, query: str) -> dict:
    """Generate analysis and chart directly from data without LLM.
    Handles time series, categorical, and multi-column queries."""
    import plotly
    import plotly.express as px
    import plotly.graph_objects as go
    import re

    q = query.lower()
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    cat_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    # Detect date/time columns
    date_col = None
    for c in df.columns:
        if c.lower() in ["date", "time", "datetime", "timestamp", "period"]:
            date_col = c
            break
    if not date_col:
        for c in cat_cols:
            try:
                pd.to_datetime(df[c].head(5))
                date_col = c
                break
            except Exception:
                pass

    # Find mentioned columns in query
    mentioned_numeric = [c for c in numeric_cols if c.lower() in q]
    mentioned_cat = [c for c in cat_cols if c.lower() in q]

    # Determine chart type
    chart_type = "bar"
    if "pie" in q:
        chart_type = "pie"
    elif "line" in q or "trend" in q or "over time" in q:
        chart_type = "line"
    elif "scatter" in q or "vs" in q or "relationship" in q:
        chart_type = "scatter"
    elif "histogram" in q or "distribution" in q:
        chart_type = "histogram"
    elif "heatmap" in q or "correlation" in q:
        chart_type = "heatmap"
    elif "box" in q:
        chart_type = "box"
    elif "dashboard" in q:
        chart_type = "dashboard"

    # Determine aggregation
    agg = "mean" if date_col else "sum"
    if "sum" in q or "total" in q:
        agg = "sum"
    elif "average" in q or "mean" in q or "avg" in q:
        agg = "mean"
    elif "count" in q:
        agg = "count"

    # Top N
    top_n = None
    nums = re.findall(r'top\s*(\d+)', q)
    if nums:
        top_n = int(nums[0])

    analysis_parts = []
    chart_data = None

    try:
        # ── 1. DASHBOARD (always check first) ──
        if chart_type == "dashboard":
            from plotly.subplots import make_subplots
            cols_to_show = numeric_cols[:4]
            fig = make_subplots(rows=2, cols=2, subplot_titles=cols_to_show)
            for i, col in enumerate(cols_to_show):
                row, col_idx = (i // 2) + 1, (i % 2) + 1
                if date_col:
                    df_s = df.copy()
                    try:
                        df_s[date_col] = pd.to_datetime(df_s[date_col])
                        df_s = df_s.sort_values(date_col)
                    except Exception:
                        pass
                    fig.add_trace(go.Scatter(x=df_s[date_col], y=df_s[col], name=col), row=row, col=col_idx)
                else:
                    fig.add_trace(go.Histogram(x=df[col], name=col), row=row, col=col_idx)
            fig.update_layout(title="Executive Dashboard", showlegend=False)
            analysis_parts.append("📊 **Executive Dashboard**:")
            for col in cols_to_show:
                vals = df[col].dropna()
                analysis_parts.append(f"  • {col}: mean={vals.mean():.2f}, range=[{vals.min():.2f}, {vals.max():.2f}]")

        # ── 2. CORRELATION HEATMAP ──
        elif chart_type == "heatmap" and len(numeric_cols) >= 2:
            corr = df[numeric_cols].corr()
            fig = px.imshow(corr, title="Correlation Heatmap", text_auto=".2f", aspect="auto")
            analysis_parts.append("🔗 **Correlation Analysis**:")
            for i, c1 in enumerate(numeric_cols):
                for c2 in numeric_cols[i+1:]:
                    val = corr.loc[c1, c2]
                    if abs(val) > 0.5:
                        analysis_parts.append(f"  • {c1} ↔ {c2}: {val:.2f} {'(strong)' if abs(val) > 0.7 else ''}")

        # ── 3. HISTOGRAM ──
        elif chart_type == "histogram":
            col = mentioned_numeric[0] if mentioned_numeric else (numeric_cols[0] if numeric_cols else cat_cols[0])
            fig = px.histogram(df, x=col, title=f"Distribution of {col}", nbins=30)
            vals = df[col].dropna()
            analysis_parts.append(f"📊 **Distribution of {col}**:")
            if col in numeric_cols:
                analysis_parts.append(f"  • Min: {vals.min():.2f}, Max: {vals.max():.2f}")
                analysis_parts.append(f"  • Mean: {vals.mean():.2f}, Median: {vals.median():.2f}")
                analysis_parts.append(f"  • Std Dev: {vals.std():.2f}")

        # 4. SCATTER PLOT
        elif chart_type == "scatter" and len(numeric_cols) >= 2:
            # Prioritize Date if mentioned or available, else first numeric
            x = date_col if (date_col and (date_col.lower() in q or "date" in q)) else (mentioned_numeric[0] if mentioned_numeric else numeric_cols[0])
            y = mentioned_numeric[0] if (mentioned_numeric and x != mentioned_numeric[0]) else (mentioned_numeric[1] if len(mentioned_numeric) > 1 else [c for c in numeric_cols if c != x][0])
            color = mentioned_cat[0] if mentioned_cat else (cat_cols[0] if cat_cols and len(df[cat_cols[0]].unique()) < 20 else None)
            fig = px.scatter(df, x=x, y=y, color=color, title=f"{x} vs {y}")
            analysis_parts.append(f"📊 **{x} vs {y}** scatter plot")
            if x in numeric_cols and y in numeric_cols:
                corr_val = df[x].corr(df[y])
                analysis_parts.append(f"  • Correlation: {corr_val:.2f}")

        # ── 5. PIE CHART ──
        elif chart_type == "pie":
            if mentioned_cat:
                x_col = mentioned_cat[0]
            elif cat_cols and not date_col:
                x_col = cat_cols[0]
            else:
                # For date-based data, try grouping by month
                x_col = None
            y_col = mentioned_numeric[0] if mentioned_numeric else (numeric_cols[0] if numeric_cols else None)
            if x_col and y_col:
                plot_df = df.groupby(x_col)[y_col].sum().reset_index().sort_values(y_col, ascending=False).head(10)
                fig = px.pie(plot_df, names=x_col, values=y_col, title=f"{y_col} by {x_col}")
                analysis_parts.append(f"📊 **{y_col} by {x_col}**:")
                for _, row in plot_df.head(5).iterrows():
                    analysis_parts.append(f"  • {row[x_col]}: {row[y_col]:,.2f}")
            else:
                fig = px.pie(df[numeric_cols[:4]].mean().reset_index().rename(columns={"index":"Column", 0:"Mean"}),
                             names="Column", values="Mean", title="Column Proportions")
                analysis_parts.append("📊 Column proportions (by mean)")

        # ── 6. TIME SERIES (line/trend) — only for explicit trend queries ──
        elif chart_type == "line" and date_col:
            df_sorted = df.copy()
            try:
                df_sorted[date_col] = pd.to_datetime(df_sorted[date_col])
                df_sorted = df_sorted.sort_values(date_col)
            except Exception:
                pass

            y_cols = mentioned_numeric if mentioned_numeric else numeric_cols[:3]
            if len(y_cols) == 1:
                fig = px.line(df_sorted, x=date_col, y=y_cols[0], title=f"{y_cols[0]} Over Time")
            else:
                fig = go.Figure()
                for col in y_cols:
                    fig.add_trace(go.Scatter(x=df_sorted[date_col], y=df_sorted[col], mode='lines', name=col))
                fig.update_layout(title=f"{', '.join(y_cols)} Over Time")

            for col in y_cols:
                vals = df_sorted[col].dropna()
                analysis_parts.append(f"📈 **{col}**:")
                analysis_parts.append(f"  • Range: {vals.min():.2f} → {vals.max():.2f}")
                analysis_parts.append(f"  • Mean: {vals.mean():.2f}, Std: {vals.std():.2f}")
                if len(vals) > 1:
                    change = vals.iloc[-1] - vals.iloc[0]
                    pct = (change / vals.iloc[0]) * 100 if vals.iloc[0] != 0 else 0
                    direction = "📈 Up" if change > 0 else "📉 Down"
                    analysis_parts.append(f"  • Trend: {direction} {abs(pct):.1f}% ({change:+.2f})")

        # ── 7. BAR CHART ──
        elif chart_type == "bar":
            if mentioned_cat and not date_col:
                # Categorical bar chart
                x_col = mentioned_cat[0]
                y_col = mentioned_numeric[0] if mentioned_numeric else (numeric_cols[0] if numeric_cols else None)
            elif cat_cols and not date_col:
                x_col = cat_cols[0]
                y_col = mentioned_numeric[0] if mentioned_numeric else (numeric_cols[0] if numeric_cols else None)
            elif date_col:
                # Bar chart with date data — show top dates by value
                x_col = date_col
                y_col = mentioned_numeric[0] if mentioned_numeric else (numeric_cols[0] if numeric_cols else None)
            else:
                x_col, y_col = None, None

            if x_col and y_col:
                plot_df = df.groupby(x_col)[y_col].agg(agg).reset_index()
                plot_df = plot_df.sort_values(y_col, ascending=False)
                if top_n:
                    plot_df = plot_df.head(top_n)
                elif len(plot_df) > 15:
                    plot_df = plot_df.head(10)
                    top_n = 10

                title = f"{'Top ' + str(top_n) + ' ' if top_n else ''}{y_col} by {x_col} ({agg})"
                fig = px.bar(plot_df, x=x_col, y=y_col, title=title)
                analysis_parts.append(f"📊 **{title}**:")
                for _, row in plot_df.head(10).iterrows():
                    val = row[y_col]
                    analysis_parts.append(f"  • {row[x_col]}: {val:,.2f}" if isinstance(val, float) else f"  • {row[x_col]}: {val}")
            else:
                # Fallback bar chart of column means
                fig = px.bar(
                    df[numeric_cols].mean().reset_index().rename(columns={"index": "Column", 0: "Mean"}),
                    x="Column", y="Mean", title="Column Averages"
                )
                analysis_parts.append("📊 **Column Averages**:")
                for c in numeric_cols[:5]:
                    analysis_parts.append(f"  • {c}: {df[c].mean():.2f}")

        # ── FALLBACK ──
        else:
            if numeric_cols:
                fig = px.bar(
                    df[numeric_cols].mean().reset_index().rename(columns={"index": "Column", 0: "Mean"}),
                    x="Column", y="Mean", title="Column Averages"
                )
            else:
                fig = px.histogram(df, x=df.columns[0], title=f"Distribution of {df.columns[0]}")
            analysis_parts.append(f"📊 **Dataset**: {df.shape[0]} rows × {df.shape[1]} columns")
            for c in numeric_cols[:5]:
                analysis_parts.append(f"  • {c}: mean={df[c].mean():.2f}, range=[{df[c].min():.2f}, {df[c].max():.2f}]")

        # Apply dark theme
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter, sans-serif"),
            margin=dict(l=40, r=40, t=60, b=40),
        )

        chart_data = json.loads(plotly.io.to_json(fig))

    except Exception as e:
        traceback.print_exc()
        analysis_parts.append(f"⚠️ Chart generation error: {str(e)}")

    return {
        "analysis": "\n".join(analysis_parts),
        "chart": chart_data,
        "agent_steps": [],
    }


@app.get("/api/data/{session_id}")
async def get_data(session_id: str, page: int = 0, page_size: int = 50):
    """Get paginated data preview."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    start = page * page_size
    end = start + page_size
    df_page = session.df.iloc[start:end]

    return {
        "data": df_page.to_dict(orient="records"),
        "total_rows": len(session.df),
        "page": page,
        "page_size": page_size,
        "total_pages": (len(session.df) + page_size - 1) // page_size,
        "columns": session.df.columns.tolist(),
    }


@app.get("/api/history/{session_id}")
async def get_chat_history(session_id: str):
    """Get chat history for a session."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"history": session.chat_history}


# WebSocket for real-time agent activity
active_connections: dict[str, list[WebSocket]] = {}


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    if session_id not in active_connections:
        active_connections[session_id] = []
    active_connections[session_id].append(websocket)

    try:
        while True:
            data = await websocket.receive_text()
            # Echo or handle messages
            message = json.loads(data)
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        active_connections[session_id].remove(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
