# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Streamlit dashboard to visualize OpenSSF Scorecard results."""

import pathlib

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ── Paths ─────────────────────────────────────────────────────────────────────

path_cwd = pathlib.Path.cwd()
scores_path = pathlib.Path(path_cwd, "inventory", "output", "scores.csv")
reasons_path = pathlib.Path(path_cwd, "inventory", "output", "reasons.csv")

# ── Data loading ──────────────────────────────────────────────────────────────


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Loads scores and reasons data from CSV files."""
    scores = pd.read_csv(scores_path, index_col="id")
    reasons = pd.read_csv(reasons_path, index_col="id")
    return scores, reasons


# ── Score colouring ───────────────────────────────────────────────────────────


def score_to_gradient(score_str: str) -> str:
    """Converts a score string (e.g. '7/10') to a CSS style string with a color gradient."""
    try:
        value = float(str(score_str).split("/")[0].strip())
    except (ValueError, AttributeError):
        return "background: #f0f0f0; color: #888;"
    if value >= 8:
        return "background: linear-gradient(135deg, #d4edda, #a8d5b5); color: #1a6b3a;"
    elif value >= 5:
        return "background: linear-gradient(135deg, #fff3cd, #ffe08a); color: #856404;"
    else:
        return "background: linear-gradient(135deg, #fde8e8, #f5b7b7); color: #a93226;"


# ── HTML table builder ────────────────────────────────────────────────────────


def build_tool_detail_table(
    tool_id: str, scores: pd.DataFrame, reasons: pd.DataFrame
) -> str:
    """Builds an HTML table showing detailed scores and reasons for a specific tool."""
    check_cols = [
        c for c in scores.columns if c not in ("html_url", "aggregated_score")
    ]

    reason_col_map = {
        col.removeprefix("Reason "): col
        for col in reasons.columns
        if col.startswith("Reason ")
    }

    score_row = scores.loc[tool_id]
    reason_row = reasons.loc[tool_id] if tool_id in reasons.index else None

    rows_html = []
    for check in check_cols:
        score_val = score_row.get(check, "?")
        cell_style = score_to_gradient(score_val)

        reason_col = reason_col_map.get(check)
        if reason_col and reason_row is not None:
            reason_text = reason_row.get(reason_col, "No reason available")
        else:
            reason_text = "No reason available"

        rows_html.append(f"""
            <tr class="detail-row">
                <td class="score-col">
                    <span class="score-badge" style="{cell_style}">{score_val}</span>
                </td>
                <td class="check-col">
                    <div class="check-name">{check}</div>
                    <div class="check-reason">{reason_text}</div>
                </td>
            </tr>
        """)

    table_style = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

        .detail-wrapper {
            overflow-x: auto;
            border-radius: 12px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.08);
            background: #ffffff;
            border: 1px solid #e5e7eb;
            padding: 4px;
        }

        table.detail-table {
            border-collapse: separate;
            border-spacing: 0;
            width: 100%;
            font-family: 'Inter', sans-serif;
            background: #ffffff;
            border-radius: 10px;
            overflow: hidden;
        }

        table.detail-table thead tr {
            background: #ffffff;
        }

        table.detail-table th {
            color: #3c3c6e;
            padding: 10px 16px;
            white-space: nowrap;
            font-weight: 600;
            letter-spacing: 0.04em;
            border-bottom: 2px solid #c5cae9;
            text-align: left;
            font-size: 0.82rem;
        }

        table.detail-table td {
            padding: 10px 16px;
            border-bottom: 1px solid #f0f0f0;
            vertical-align: middle;
        }

        td.score-col {
            width: 80px;
            text-align: center;
            vertical-align: middle;
        }

        .score-badge {
            display: inline-block;
            padding: 6px 14px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.9rem;
            box-shadow: 0 2px 6px rgba(0,0,0,0.10);
            letter-spacing: 0.04em;
            white-space: nowrap;
        }

        td.check-col {
            text-align: left;
        }

        .check-name {
            font-weight: 600;
            font-size: 0.85rem;
            color: #3c3c6e;
            margin-bottom: 4px;
        }

        .check-reason {
            font-size: 0.78rem;
            color: #666;
            line-height: 1.4;
        }

        tr.detail-row:hover td {
            background-color: #f5f5ff;
        }
    </style>
    """

    html = (
        table_style
        + '<div class="detail-wrapper">'
        + '<table class="detail-table">'
        + "<thead><tr><th>Score</th><th>Check &amp; Reason</th></tr></thead>"
        + "<tbody>"
        + "\n".join(rows_html)
        + "</tbody>"
        + "</table></div>"
    )
    return html


# ── App ───────────────────────────────────────────────────────────────────────


def main() -> None:
    """Main function to run the Streamlit app."""
    st.set_page_config(page_title="OpenSSF Scorecard Dashboard", layout="wide")
    st.title("🔐 OpenSSF Scorecard Dashboard")

    scores, reasons = load_data()

    # ── Sidebar filters ───────────────────────────────────────────────────────
    st.sidebar.header("Filters")

    selected_tool = st.sidebar.selectbox("Select a tool", options=scores.index.tolist())

    if selected_tool:
        score_row = scores.loc[selected_tool]
        agg = score_row.get("aggregated_score", "?")
        agg_style = score_to_gradient(agg)
        html_url = score_row.get("html_url", "#")

        st.markdown(
            f"""
            <div style="display:flex; align-items:center; gap:16px; margin-bottom:16px; flex-wrap:wrap;">
                <a href="{html_url}" target="_blank"
                   style="font-size:1.1rem; font-weight:700; color:#5c6bc0;
                          text-decoration:none; font-family:'Inter',sans-serif;">
                    🔧 {selected_tool}
                </a>
                <span style="{agg_style} padding:5px 16px; border-radius:20px;
                             font-weight:700; font-size:0.95rem;
                             box-shadow:0 2px 6px rgba(0,0,0,0.12);">
                    ⭐ {agg}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div style="display:flex; gap:12px; align-items:center; margin-bottom:12px; flex-wrap:wrap;">
                <span style="font-size:0.8rem; color:#666; font-weight:600; font-family:'Inter',sans-serif;">Score legend:</span>
                <span style="background:linear-gradient(135deg,#d4edda,#a8d5b5); color:#1a6b3a;
                             padding:3px 12px; border-radius:20px; font-size:0.78rem; font-weight:600;
                             box-shadow:0 1px 4px rgba(0,0,0,0.1);">≥ 8 — High</span>
                <span style="background:linear-gradient(135deg,#fff3cd,#ffe08a); color:#856404;
                             padding:3px 12px; border-radius:20px; font-size:0.78rem; font-weight:600;
                             box-shadow:0 1px 4px rgba(0,0,0,0.1);">≥ 5 — Medium</span>
                <span style="background:linear-gradient(135deg,#fde8e8,#f5b7b7); color:#a93226;
                             padding:3px 12px; border-radius:20px; font-size:0.78rem; font-weight:600;
                             box-shadow:0 1px 4px rgba(0,0,0,0.1);">< 5 — Low</span>
                <span style="background:#f0f0f0; color:#888;
                             padding:3px 12px; border-radius:20px; font-size:0.78rem; font-weight:600;
                             box-shadow:0 1px 4px rgba(0,0,0,0.1);">N/A</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        html_content = build_tool_detail_table(selected_tool, scores, reasons)
        components.html(html_content, height=800, scrolling=True)


if __name__ == "__main__":
    main()
