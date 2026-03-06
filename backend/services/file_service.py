"""
File Service — Handles file upload, reading, and data summarization.
Supports CSV and Excel files.
"""

import os
import uuid
import pandas as pd
from pathlib import Path

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def save_uploaded_file(file_bytes: bytes, filename: str) -> dict:
    """Save an uploaded file and return session info."""
    session_id = str(uuid.uuid4())[:8]
    ext = Path(filename).suffix.lower()

    if ext not in [".csv", ".xlsx", ".xls"]:
        raise ValueError(f"Unsupported file type: {ext}. Use CSV or Excel files.")

    save_path = UPLOAD_DIR / f"{session_id}_{filename}"
    with open(save_path, "wb") as f:
        f.write(file_bytes)

    return {
        "session_id": session_id,
        "filename": filename,
        "path": str(save_path),
        "extension": ext,
    }


def load_dataframe(file_path: str) -> pd.DataFrame:
    """Load a file into a pandas DataFrame."""
    ext = Path(file_path).suffix.lower()
    if ext == ".csv":
        df = pd.read_csv(file_path)
    elif ext in [".xlsx", ".xls"]:
        df = pd.read_excel(file_path, engine="openpyxl")
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    return df


def get_data_summary(df: pd.DataFrame) -> dict:
    """Generate a comprehensive summary of the DataFrame."""
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime"]).columns.tolist()

    summary = {
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": [],
        "sample_data": df.head(5).to_dict(orient="records"),
        "missing_values": df.isnull().sum().to_dict(),
        "numeric_stats": {},
    }

    for col in df.columns:
        col_info = {
            "name": col,
            "dtype": str(df[col].dtype),
            "null_count": int(df[col].isnull().sum()),
            "unique_count": int(df[col].nunique()),
        }
        if col in numeric_cols:
            col_info["category"] = "numeric"
            col_info["min"] = float(df[col].min()) if not df[col].isnull().all() else None
            col_info["max"] = float(df[col].max()) if not df[col].isnull().all() else None
            col_info["mean"] = float(df[col].mean()) if not df[col].isnull().all() else None
        elif col in categorical_cols:
            col_info["category"] = "categorical"
            col_info["top_values"] = df[col].value_counts().head(5).to_dict()
        elif col in datetime_cols:
            col_info["category"] = "datetime"
        else:
            col_info["category"] = "other"
        summary["columns"].append(col_info)

    if numeric_cols:
        stats = df[numeric_cols].describe().to_dict()
        summary["numeric_stats"] = {
            k: {sk: float(sv) for sk, sv in v.items()} for k, v in stats.items()
        }

    return summary


def get_data_as_text(df: pd.DataFrame, max_rows: int = 50) -> str:
    """Convert DataFrame to a text representation for LLM consumption."""
    info_parts = []
    info_parts.append(f"Dataset: {df.shape[0]} rows × {df.shape[1]} columns")
    info_parts.append(f"\nColumn names and types:")
    for col in df.columns:
        info_parts.append(f"  - {col} ({df[col].dtype})")
    info_parts.append(f"\nFirst {min(max_rows, len(df))} rows:")
    info_parts.append(df.head(max_rows).to_string(index=False))
    info_parts.append(f"\nBasic statistics:")
    info_parts.append(df.describe(include="all").to_string())
    return "\n".join(info_parts)
