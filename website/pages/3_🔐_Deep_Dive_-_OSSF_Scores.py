# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Streamlit dashboard to visualize OpenSSF Scorecard results."""

import pathlib

import pandas as pd
import streamlit as st

# ── Paths ─────────────────────────────────────────────────────────────────────

path_cwd = pathlib.Path.cwd()
scores_path = pathlib.Path(path_cwd, "inventory", "output", "scores.csv")
reasons_path = pathlib.Path(path_cwd, "inventory", "output", "reasons.csv")

# ── Data loading ──────────────────────────────────────────────────────────────

@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    scores = pd.read_csv(scores_path, index_col="id")
    reasons = pd.read_csv(reasons_path, index_col="id")
    return scores, reasons


# ── Score colouring ───────────────────────────────────────────────────────────

def score_to_color(score_str: str) -> str:
    """Return a CSS background colour based on the numeric score."""
    try:
        value = float(str(score_str).split("/")[0].strip())
    except (ValueError, AttributeError):
        return "#d3d3d3"  # grey for N/A or '?'

    if value >= 8:
        return "#90ee90"  # green
    elif value >= 5:
        return "#ffd700"  # yellow
    else:
        return "#ff7f7f"  # red


# ── HTML table builder ────────────────────────────────────────────────────────

def build_html_table(scores: pd.DataFrame, reasons: pd.DataFrame) -> str:
    check_cols = [
        c for c in scores.columns if c not in ("html_url", "aggregated_score")
    ]

    reason_col_map = {
        col.removeprefix("Reason "): col for col in reasons.columns if col.startswith("Reason ")
    }

    def score_to_gradient(score_str: str) -> str:
        try:
            value = float(str(score_str).split("/")[0].strip())
        except (ValueError, AttributeError):
            return "background: linear-gradient(135deg, #e0e0e0, #bdbdbd); color: #666;"
        if value >= 8:
            return "background: linear-gradient(135deg, #56ab2f, #a8e063); color: #fff;"
        elif value >= 5:
            return "background: linear-gradient(135deg, #f7971e, #ffd200); color: #fff;"
        else:
            return "background: linear-gradient(135deg, #cb2d3e, #ef473a); color: #fff;"

    rows_html = []
    for tool_id, score_row in scores.iterrows():
        cells = [
            f'<td class="tool-name">'
            f'<a href="{score_row["html_url"]}" target="_blank">🔧 {tool_id}</a>'
            f'</td>'
        ]

        agg = score_row.get("aggregated_score", "?")
        agg_style = score_to_gradient(agg)
        cells.append(
            f'<td class="agg-cell"><span class="agg-badge" style="{agg_style}">{agg}</span></td>'
        )

        for check in check_cols:
            score_val = score_row.get(check, "?")
            cell_style = score_to_gradient(score_val)

            reason_col = reason_col_map.get(check)
            if reason_col and tool_id in reasons.index:
                reason_text = reasons.loc[tool_id, reason_col]
            else:
                reason_text = "No reason available"

            safe_reason = str(reason_text).replace("'", "&#39;").replace('"', "&quot;")

            cells.append(
                f'<td class="score-cell" style="{cell_style}" title="{safe_reason}">'
                f'{score_val}'
                f'</td>'
            )

        rows_html.append("<tr class='data-row'>" + "".join(cells) + "</tr>")

    header_cells = (
        "<th>🛠 Tool</th>"
        "<th>⭐ Aggregated</th>"
        + "".join(f"<th>{c}</th>" for c in check_cols)
    )

    table_style = """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

        .scorecard-wrapper {
            overflow-x: auto;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.18);
            background: #1a1a2e;
            padding: 4px;
        }

        table.scorecard {
            border-collapse: separate;
            border-spacing: 0;
            width: 100%;
            font-size: 0.78rem;
            font-family: 'Inter', sans-serif;
            background: #16213e;
            border-radius: 10px;
            overflow: hidden;
        }

        table.scorecard thead tr {
            background: linear-gradient(90deg, #0f3460, #533483);
        }

        table.scorecard th {
            color: #e0e0e0;
            padding: 10px 14px;
            white-space: nowrap;
            font-weight: 600;
            letter-spacing: 0.04em;
            border-bottom: 2px solid #533483;
            text-align: center;
        }

        table.scorecard th:first-child {
            text-align: left;
        }

        table.scorecard td {
            padding: 7px 12px;
            white-space: nowrap;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            transition: all 0.2s ease;
            text-align: center;
        }

        td.tool-name {
            text-align: left;
            background: rgba(255,255,255,0.03);
            font-weight: 600;
        }

        td.tool-name a {
            color: #a78bfa;
            text-decoration: none;
            transition: color 0.2s;
        }

        td.tool-name a:hover {
            color: #c4b5fd;
            text-decoration: underline;
        }

        td.score-cell {
            border-radius: 6px;
            font-weight: 600;
            font-size: 0.75rem;
            cursor: help;
            box-shadow: inset 0 0 6px rgba(0,0,0,0.2);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }

        td.score-cell:hover {
            transform: scale(1.12);
            box-shadow: 0 0 12px rgba(255,255,255,0.3);
            z-index: 10;
            position: relative;
        }

        td.agg-cell {
            background: transparent !important;
            text-align: center;
        }

        .agg-badge {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.85rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            letter-spacing: 0.05em;
        }

        tr.data-row:hover td {
            background-color: rgba(255,255,255,0.05) !important;
        }

        tr.data-row:hover td.score-cell {
            background-color: unset !important;
        }
    </style>
    """

    html = (
        table_style
        + '<div class="scorecard-wrapper">'
        + '<table class="scorecard">'
        + "<thead><tr>" + header_cells + "</tr></thead>"
        + "<tbody>" + "\n".join(rows_html) + "</tbody>"
        + "</table></div>"
    )
    return html



# ── App ───────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(page_title="OpenSSF Scorecard Dashboard", layout="wide")
    st.title("🔐 OpenSSF Scorecard Dashboard")
    st.caption(
        "Hover over any score cell to read the reason behind that score. "
        "Colors: 🟢 ≥ 8 · 🟡 ≥ 5 · 🔴 < 5 · ⬜ N/A"
    )

    scores, reasons = load_data()

    # ── Sidebar filters ───────────────────────────────────────────────────────
    st.sidebar.header("Filters")

    tool_filter = st.sidebar.multiselect(
        "Select tools",
        options=scores.index.tolist(),
        default=scores.index.tolist(),
    )

    min_agg = st.sidebar.slider(
        "Minimum aggregated score",
        min_value=0.0,
        max_value=10.0,
        value=0.0,
        step=0.1,
    )

    # ── Apply filters ─────────────────────────────────────────────────────────
    filtered_scores = scores.loc[tool_filter].copy()
    filtered_reasons = reasons.loc[
        [i for i in tool_filter if i in reasons.index]
    ].copy()

    try:
        filtered_scores = filtered_scores[
            pd.to_numeric(filtered_scores["aggregated_score"], errors="coerce") >= min_agg
        ]
    except Exception:
        pass

    st.markdown(f"Showing **{len(filtered_scores)}** tool(s)")
    st.markdown(
        build_html_table(filtered_scores, filtered_reasons),
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
