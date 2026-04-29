# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Streamlit dashboard to visualize OpenSSF Scorecard results."""

from pathlib import Path

import jinja2
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# ── Paths ─────────────────────────────────────────────────────────────────────

path_cwd = Path.cwd()
scores_path = path_cwd / "inventory" / "output" / "scores.csv"
reasons_path = path_cwd / "inventory" / "output" / "reasons.csv"

# ── Jinja2 environment ────────────────────────────────────────────────────────

_templates_dir = path_cwd / "website" / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_templates_dir)),
    autoescape=jinja2.select_autoescape(["html"]),
)

# ── Data loading ──────────────────────────────────────────────────────────────


@st.cache_data
def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Loads scores and reasons data from CSV files."""
    scores = pd.read_csv(scores_path, index_col="id")
    reasons = pd.read_csv(reasons_path, index_col="id")
    return scores, reasons


# ── Score colouring ───────────────────────────────────────────────────────────


def score_to_gradient(score_str: str) -> str:
    """Converts a score string (e.g. '7') to a CSS style string with a color gradient."""
    if str(score_str).strip() in ("?", "N/A", ""):
        return "background: #f0f0f0; color: #888;"
    try:
        value = float(str(score_str).strip())
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

    if isinstance(score_row, pd.DataFrame) or isinstance(reason_row, pd.DataFrame):
        raise ValueError(
            f"Duplicate rows found for tool_id '{tool_id}' in scores or reasons DataFrame. "
            "Each tool must appear only once."
        )
    SCORECARD_DOCS_BASE = "https://github.com/ossf/scorecard/blob/main/docs/checks.md#"

    rows = []
    for check in check_cols:
        raw_score = score_row.get(check, "?")
        try:
            val = float(raw_score)
            if val < 0 or pd.isna(val):
                display_val = "None"
            else:
                display_val = str(int(val)).strip()
        except (ValueError, TypeError):
            display_val = "None"

        cell_style = score_to_gradient(display_val)

        reason_col = reason_col_map.get(check)
        if reason_col and reason_row is not None:
            reason_text = reason_row.get(reason_col, "No reason available")
            # Also skip if reason is NaN
            try:
                if pd.isna(reason_text):
                    continue
            except (TypeError, ValueError):
                pass
        else:
            reason_text = "No reason available"
        if not reason_text.endswith("."):
            reason_text = reason_text + "."

        # Build docs anchor: lowercase, spaces → hyphens
        doc_url = f"{SCORECARD_DOCS_BASE}{check.casefold()}"

        rows.append(
            {
                "cell_style": cell_style,
                "display_val": display_val,
                "doc_url": doc_url,
                "check": check,
                "reason_text": reason_text,
            }
        )

    template = _jinja_env.get_template("ossf_detail_table.html.jinja")
    return template.render(rows=rows)


# ── App ───────────────────────────────────────────────────────────────────────


def preamble():
    """Text to show before the user data plots."""
    st.set_page_config(page_title="OpenSSF Scorecard Dashboard", layout="wide")
    st.title("🔐 OpenSSF Scorecard Dashboard")
    st.markdown(
        """
        The dashboard provides a detailed view of the [OpenSSF Scorecard](https://github.com/ossf/scorecard?tab=readme-ov-file#what-is-scorecard) results for each tool in our inventory.
        Select a tool from the dropdown to see its overall score and a breakdown of individual checks along with
        the reasons for any failed or low-scoring checks. The scores are colour-coded to help you quickly identify
        areas of strength and weakness in the security posture of each tool. The scores shown below are
        on a scale from **0 to 10**, where **10** represents the highest level of security compliance.
         """
    )


def main() -> None:
    """Main function to run the Streamlit app."""
    scores, reasons = load_data()

    # ── Sidebar filters ───────────────────────────────────────────────────────
    st.sidebar.header("Filters")

    selected_tool = st.sidebar.selectbox("Select a tool", options=scores.index.tolist())

    if selected_tool:
        score_row = scores.loc[selected_tool]
        agg = score_row.get("aggregated_score", "?")
        agg_style = score_to_gradient(agg)
        html_url = score_row.get("html_url", "#")

        header_template = _jinja_env.get_template("ossf_tool_header.html.jinja")
        header_html = header_template.render(
            html_url=html_url, selected_tool=selected_tool, agg_style=agg_style, agg=agg
        )
        st.markdown(header_html, unsafe_allow_html=True)

        html_content = build_tool_detail_table(selected_tool, scores, reasons)
        components.html(html_content, height=800, scrolling=True)


if __name__ == "__main__":
    preamble()
    main()
