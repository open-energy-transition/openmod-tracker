# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Streamlit app to display energy system modelling tool feature comparison."""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import yaml
from jinja2 import Environment, FileSystemLoader

SYMBOLS = {"dev": "⎌", "y": "✓", "n": "✕"}
COLOR_SCHEME = {
    "dev": {"sourced": "#007bff", "unsourced": "#fd7e14"},
    "y": {"sourced": "#28a745", "unsourced": "#fd7e14"},
    "n": {"sourced": "#a71d2a", "unsourced": "#fd7e14"},
}


def load_tool_features(tools_dir: Path) -> dict[str, dict]:
    """Load features.yaml for all tools.

    Args:
        tools_dir: Path to the tools directory

    Returns:
        Dictionary mapping tool name to features data
    """
    tools_data = {}
    for tool_path in sorted(tools_dir.rglob("features.yaml")):
        data = yaml.safe_load(tool_path.read_text())
        tools_data[tool_path.parent.name] = data["features"]
    return tools_data


def load_use_case_features(use_cases_dir: Path) -> dict[str, dict]:
    """Load features.yaml for all use cases.

    Args:
        use_cases_dir: Path to the use-cases directory

    Returns:
        Dictionary mapping use case name to full use case data (features, assumptions, description, etc.)
    """
    use_cases_data = {}
    for use_case_path in sorted(use_cases_dir.rglob("features.yaml")):
        data = yaml.safe_load(use_case_path.read_text())
        metadata_path = use_case_path.parent / ".metadata.yml"
        description = yaml.safe_load(metadata_path.read_text())["description"]
        name = use_case_path.parent.name.replace("_", " ").title()
        use_cases_data[name] = {
            "features": data["features"],
            "assumptions": data["assumptions"],
            "description": description,
            "id": use_case_path.name,
        }
    return use_cases_data


def filter_features_by_use_case(
    features_dict: dict, use_case_features: dict | None
) -> dict:
    """Filter features to only those required by a use case.

    Args:
        features_dict: Full features dictionary
        use_case_features: Use case required features (value='y' means required)

    Returns:
        Filtered features dictionary
    """
    if use_case_features is None:
        return features_dict

    filtered = {}
    for category, category_features in features_dict.items():
        if category not in use_case_features:
            continue

        filtered_category = {}
        for feature_name, feature_data in category_features.items():
            if feature_name not in use_case_features[category]:
                continue

            # Only include if use case requires it (value='y')
            use_case_value = use_case_features[category][feature_name].get("value", "n")
            if use_case_value == "y":
                filtered_category[feature_name] = feature_data

        if filtered_category:
            filtered[category] = filtered_category

    return filtered


def calculate_percentage(
    features_dict: dict, count_unsourced: bool = True, count_dev: bool = False
) -> float:
    """Calculate percentage of features that are 'y'.

    Args:
        features_dict: Dictionary of features with 'value' keys
        count_unsourced: Whether to count 'y' without sources
        count_dev: Whether to count 'dev' as implemented

    Returns:
        Percentage of features with value 'y' (and optionally 'dev')
    """
    total = 0
    yes_count = 0

    for value in features_dict.values():
        if isinstance(value, dict) and "value" in value:
            total += 1
            feature_value = value["value"]
            has_source = bool(value.get("source", []))

            if feature_value == "y":
                # Count if: (has source) OR (no source but count_unsourced is True)
                if has_source or count_unsourced:
                    yes_count += 1
            elif feature_value == "dev" and count_dev:
                yes_count += 1
        elif isinstance(value, dict):
            # Nested group
            for feature in value.values():
                if isinstance(feature, dict) and "value" in feature:
                    total += 1
                    feature_value = feature["value"]
                    has_source = bool(feature.get("source", []))

                    if feature_value == "y":
                        if has_source or count_unsourced:
                            yes_count += 1
                    elif feature_value == "dev" and count_dev:
                        yes_count += 1

    return (yes_count / total * 100) if total > 0 else 0


def get_color_for_percentage(percentage: float) -> str:
    """Get color based on percentage using a balanced color scheme.

    Args:
        percentage: Percentage value between 0 and 100

    Returns:
        CSS color string
    """
    # Balanced color scheme: soft coral to warm yellow to medium green
    # More saturated than pastel but softer than the original

    if percentage < 50:
        # Soft coral to warm yellow
        ratio = percentage / 50
        red = int(255 + (255 - 255) * ratio)
        green = int(180 + (235 - 180) * ratio)
        blue = int(180 + (200 - 180) * ratio)
    else:
        # Warm yellow to medium green
        ratio = (percentage - 50) / 50
        red = int(255 - (255 - 180) * ratio)
        green = int(235 - (235 - 220) * ratio)
        blue = int(200 - (200 - 180) * ratio)

    return f"rgb({red}, {green}, {blue})"


def format_value_with_sources(value: str, sources: list[str]) -> str:
    """Format a feature value with colored symbols and sources as superscript hyperlinks.

    Args:
        value: The feature value ('y', 'n', or 'dev')
        sources: List of source URLs

    Returns:
        HTML string with colored symbol and hyperlinked sources
    """
    # Map values to symbols and colors
    color_options = COLOR_SCHEME[value]
    color = color_options["sourced"] if sources else color_options["unsourced"]
    symbol = f'<span style="color: {color}; font-size: 18px;">{SYMBOLS[value]}</span>'

    if not sources:
        return symbol

    source_links = "".join(
        f'<sup><a href="{url}" target="_blank" style="margin-left: 2px;">{i + 1}</a></sup>'
        for i, url in enumerate(sources)
    )
    return f"{symbol}{source_links}"


def format_category_name(category: str) -> str:
    """Format category name to be more readable.

    Args:
        category: Raw category name with underscores

    Returns:
        Formatted category name
    """
    return category.replace("__", " > ").replace("_", " ").title()


def format_feature_name(feature: str) -> str:
    """Format feature name to be more readable.

    Args:
        feature: Raw feature name with underscores

    Returns:
        Formatted feature name
    """
    return feature.replace("_", " ").title()


def main_use_case_comparison(
    tools_data: dict[str, dict], use_cases_data: dict[str, dict], feature_schema: dict
):
    """Use case comparison view - show features as rows, use cases as columns."""
    st.sidebar.header("⚙️ Filter Options")

    # 1. Tool selection (single tool)
    st.sidebar.subheader("1. Select Tool")
    all_tools = sorted(tools_data.keys())
    tool_options = ["None (show requirements only)"] + all_tools
    selected_tool = st.sidebar.selectbox(
        "Choose a tool to evaluate:",
        options=tool_options,
        help="Select which tool to evaluate against use case requirements, or 'None' to only show requirements",
    )

    # Handle None selection
    if selected_tool == "None (show requirements only)":
        selected_tool = None

    # 2. Use case selection
    st.sidebar.subheader("2. Select Use Cases")
    all_use_cases = sorted(use_cases_data.keys())
    selected_use_cases = st.sidebar.multiselect(
        "Choose use cases to compare:",
        options=all_use_cases,
        default=all_use_cases,
        help="Select which use cases to include in the comparison",
    )

    if not selected_use_cases:
        st.warning("⚠️ Please select at least one use case from the sidebar.")
        return

    # Legend in sidebar
    st.sidebar.markdown(
        f"""
        ---
        ## 📖 Legend

        **Match Status:**

        - <span style="color: {COLOR_SCHEME["y"]["sourced"]};">✓</span> Tool has feature (implemented)
        - <span style="color: {COLOR_SCHEME["dev"]["sourced"]};">⎌</span> Tool has feature (in development)
        - <span style="color: {COLOR_SCHEME["n"]["sourced"]};">✕</span> Tool lacks feature (not implemented)
        - ○ Use case does not require this feature
        """,
        unsafe_allow_html=True,
    )

    # Main content
    st.write(
        f"Evaluating **{selected_tool}** against **{len(selected_use_cases)}** use cases: {', '.join(sorted(selected_use_cases))}"
    )

    st.write(
        "Click on 'Overall' to expand all categories. Click on category names to expand/collapse detailed features. "
        "Color coding: Green = tool has feature, Blue = in development, Red = tool lacks feature, Gray = not required by use case."
    )

    st.markdown("---")

    # Generate and display the pivoted table
    table_html = generate_use_case_comparison_table(
        tools_data[selected_tool] if selected_tool else None,
        {uc: use_cases_data[uc] for uc in selected_use_cases},
        feature_schema,
    )
    height = 600  # Fixed height for iframe
    components.html(table_html, height=height, scrolling=True)


def generate_use_case_comparison_table(
    tool_features: dict | None,
    use_cases_data: dict[str, dict],
    schema: dict[str, dict] | None = None,
) -> str:
    """Generate HTML table comparing a single tool against multiple use cases.

    Args:
        tool_features: Features dictionary for a single tool, or None to show only requirements
        use_cases_data: Dictionary of use case data (filtered to selected use cases)
        schema: Feature schema with descriptions for tooltips

    Returns:
        HTML string with the comparison table
    """
    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader(Path(__file__).parent))
    env.filters["format_category_name"] = format_category_name
    env.filters["format_feature_name"] = format_feature_name

    # Get theme
    theme = st.context.theme.type

    # Prepare data structure
    use_case_names = sorted(use_cases_data.keys())

    # Get all categories from all use cases if no tool selected
    if tool_features is None:
        all_categories = set()
        for uc_data in use_cases_data.values():
            all_categories.update(uc_data["features"].keys())
        categories = sorted(all_categories)
    else:
        categories = list(tool_features.keys())

    # Build data structure for template
    categories_data = []
    for cat_idx, category in enumerate(categories):
        category_id = f"cat_{cat_idx}"
        category_desc = ""
        if schema and category in schema:
            category_desc = schema[category].get("description", "")

        features_data = []

        # Get all features for this category
        if tool_features is not None:
            # Tool selected: iterate through tool's features
            category_features = tool_features.get(category, {})
            for feature_name, feature_value in category_features.items():
                feature_desc = ""
                if schema and category in schema and "members" in schema[category]:
                    feature_desc = schema[category]["members"].get(feature_name, "")

                # Get tool's implementation status
                tool_status = feature_value.get("value", "n")

                # Get use case requirements
                use_case_statuses = {}
                for uc_name in use_case_names:
                    uc_features = use_cases_data[uc_name]["features"]
                    if (
                        category in uc_features
                        and feature_name in uc_features[category]
                    ):
                        required = (
                            uc_features[category][feature_name].get("value", "n") == "y"
                        )
                    else:
                        required = False
                    use_case_statuses[uc_name] = {
                        "required": required,
                        "tool_status": tool_status if required else "not_required",
                    }

                features_data.append(
                    {
                        "name": feature_name,
                        "description": feature_desc,
                        "statuses": use_case_statuses,
                    }
                )
        else:
            # No tool selected: collect all features from use cases
            all_features_in_category = set()
            for uc_data in use_cases_data.values():
                if category in uc_data["features"]:
                    all_features_in_category.update(
                        uc_data["features"][category].keys()
                    )

            for feature_name in sorted(all_features_in_category):
                feature_desc = ""
                if schema and category in schema and "members" in schema[category]:
                    feature_desc = schema[category]["members"].get(feature_name, "")

                # Get use case requirements (no tool status)
                use_case_statuses = {}
                for uc_name in use_case_names:
                    uc_features = use_cases_data[uc_name]["features"]
                    if (
                        category in uc_features
                        and feature_name in uc_features[category]
                    ):
                        required = (
                            uc_features[category][feature_name].get("value", "n") == "y"
                        )
                    else:
                        required = False
                    use_case_statuses[uc_name] = {
                        "required": required,
                        "tool_status": "no_tool",  # Special status for no tool selected
                    }

                features_data.append(
                    {
                        "name": feature_name,
                        "description": feature_desc,
                        "statuses": use_case_statuses,
                    }
                )

        if features_data:  # Only add category if it has features
            categories_data.append(
                {
                    "id": category_id,
                    "name": category,
                    "description": category_desc,
                    "features": features_data,
                }
            )

    # Define colors based on theme
    if theme == "dark":
        colors = {
            "bg": "#0e1117",
            "border_light": "#fafafa1a",
            "th_text": "#fafafa",
            "td_text": "#fafafacc",
            "hover_bg": "#26273033",
            "category_bg": "#26273066",
            "overall_bg": "#26273099",
            "button_bg": "#ff4b4b",
            "button_hover": "#ff2b2b",
            "tooltip_bg": "#262730",
            "tooltip_text": "#fafafa",
        }
    else:
        colors = {
            "bg": "#ffffff",
            "border_light": "#d0d0d0",
            "th_text": "#31333f",
            "td_text": "#31333f",
            "hover_bg": "#f0f2f6",
            "category_bg": "#f0f2f6",
            "overall_bg": "#e8eaed",
            "button_bg": "#ff4b4b",
            "button_hover": "#ff2b2b",
            "tooltip_bg": "#31333f",
            "tooltip_text": "#ffffff",
        }

    # Calculate first column width
    first_column_texts = ["Overall"]
    first_column_texts.extend(
        [format_category_name(cat["name"]) for cat in categories_data]
    )
    for cat in categories_data:
        first_column_texts.extend(
            [f"    {format_feature_name(f['name'])}" for f in cat["features"]]
        )

    max_text_length = max(len(text) for text in first_column_texts)
    first_column_width = max(250, min(max_text_length * 8 + 24, 600))

    # Load template
    template = env.get_template("feature_table_use_case.html.jinja")

    context = {
        "use_case_names": use_case_names,
        "categories_data": categories_data,
        "colors": colors,
        "first_column_width": first_column_width,
    }

    return template.render(**context)


def generate_collapsible_table(
    tools_data: dict[str, dict],
    count_unsourced: bool = True,
    count_dev: bool = False,
    schema: dict[str, dict] | None = None,
    search_query: str = "",
) -> str:
    """Generate a single collapsible HTML table with all features.

    Args:
        tools_data: Dictionary mapping tool name to features
        count_unsourced: Whether to count 'y' without sources in percentages
        count_dev: Whether to count 'dev' as implemented in percentages
        schema: Feature schema with descriptions for tooltips
        search_query: Search query to filter features

    Returns:
        HTML string with the complete collapsible table
    """
    # Setup Jinja2 environment with templates directory
    env = Environment(loader=FileSystemLoader(Path(__file__).parent))

    # Register custom filters
    env.filters["format_category_name"] = format_category_name
    env.filters["format_feature_name"] = format_feature_name
    env.filters["get_color_for_percentage"] = get_color_for_percentage
    env.filters["calculate_percentage"] = lambda features: calculate_percentage(
        features, count_unsourced, count_dev
    )

    # Register functions as globals (for functions that need multiple arguments)
    env.globals["format_value_with_sources"] = format_value_with_sources

    # Prepare data for template
    tool_names = list(tools_data.keys())
    first_tool = next(iter(tools_data.values()))
    categories = list(first_tool.keys())

    # Calculate overall percentages
    overall_percentages = {
        tool: calculate_percentage(features, count_unsourced, count_dev)
        for tool, features in tools_data.items()
    }

    # Prepare category data with percentages
    categories_data = []
    for cat_idx, category in enumerate(categories):
        category_id = f"cat_{cat_idx}"
        cat_percentages = {
            tool: calculate_percentage(
                {category: features[category]}, count_unsourced, count_dev
            )
            for tool, features in tools_data.items()
        }

        category_desc = ""
        if schema and category in schema:
            category_desc = schema[category].get("description", "")

        # Prepare features for this category
        feature_list = list(first_tool[category].keys())
        features_data = []
        for feature in feature_list:
            feature_desc = ""
            if schema and category in schema and "members" in schema[category]:
                feature_desc = schema[category]["members"].get(feature, "")

            # Get feature values for each tool
            feature_values = {}
            for tool in tool_names:
                if (
                    category in tools_data[tool]
                    and feature in tools_data[tool][category]
                ):
                    feature_data = tools_data[tool][category][feature]
                    feature_values[tool] = {
                        "value": feature_data.get("value", "n"),
                        "sources": feature_data.get("source", []),
                    }
                else:
                    feature_values[tool] = {"value": "n", "sources": []}

            features_data.append(
                {"name": feature, "description": feature_desc, "values": feature_values}
            )

        categories_data.append(
            {
                "id": category_id,
                "name": category,
                "description": category_desc,
                "percentages": cat_percentages,
                "features": features_data,
            }
        )

    # Load template from file
    template = env.get_template("feature_table.html.jinja")

    # Get current theme from Streamlit context
    theme = st.context.theme.type

    # Calculate first column width based on longest text
    # Collect all first column texts
    first_column_texts = ["Overall"]  # Header row
    first_column_texts.extend(
        [format_category_name(cat["name"]) for cat in categories_data]
    )
    for cat in categories_data:
        first_column_texts.extend(
            [f"    {format_feature_name(f['name'])}" for f in cat["features"]]
        )

    # Estimate width: ~8px per character as a rough approximation for the font
    # Add padding (0.5rem * 2 = ~16px) and some buffer
    max_text_length = max(len(text) for text in first_column_texts)
    first_column_width = max_text_length * 8 + 24  # 8px per char + 24px padding

    # Set reasonable min/max bounds
    first_column_width = max(250, min(first_column_width, 600))

    # Define simplified color palettes for each theme
    if theme == "dark":
        colors = {
            "bg": "#0e1117",
            "border_light": "#fafafa1a",
            "th_text": "#fafafa",
            "td_text": "#fafafacc",
            "percentage_text": "#000000",
            "hover_bg": "#26273033",
            "category_bg": "#26273066",
            "overall_bg": "#26273099",
            "button_bg": "#ff4b4b",
            "button_hover": "#ff2b2b",
            "input_bg": "#262730",
            "input_text": "#fafafa",
            "input_border": "#fafafa33",
            "input_focus": "#ff4b4b",
            "input_placeholder": "#fafafa66",
            "tooltip_bg": "#262730",
            "tooltip_text": "#fafafa",
            "link": "#58a6ff",
        }
    else:  # light theme
        colors = {
            "bg": "#ffffff",
            "border_light": "#d0d0d0",
            "th_text": "#31333f",
            "td_text": "#31333f",
            "percentage_text": "#000000",
            "hover_bg": "#f0f2f6",
            "category_bg": "#f0f2f6",
            "overall_bg": "#e8eaed",
            "button_bg": "#ff4b4b",
            "button_hover": "#ff2b2b",
            "input_bg": "#ffffff",
            "input_text": "#31333f",
            "input_border": "#d0d0d0",
            "input_focus": "#ff4b4b",
            "input_placeholder": "#a0a0a0",
            "tooltip_bg": "#31333f",
            "tooltip_text": "#ffffff",
            "link": "#0068c9",
        }

    context = {
        "tool_names": tool_names,
        "overall_percentages": overall_percentages,
        "categories_data": categories_data,
        "search_query": search_query,
        "colors": colors,
        "first_column_width": first_column_width,
    }

    return template.render(**context)


def main(
    tools_data: dict[str, dict], use_cases_data: dict[str, dict], feature_schema: dict
):
    """Main Streamlit app."""
    # Sidebar for filtering options
    st.sidebar.header("⚙️ View Options")

    # 0. View mode selection
    view_mode = st.sidebar.radio(
        "Select View Mode:",
        options=["Tools Comparison", "Use Cases Comparison"],
        help="Choose between comparing tools or comparing use cases against a single tool",
    )

    if view_mode == "Use Cases Comparison":
        main_use_case_comparison(tools_data, use_cases_data, feature_schema)
        return

    st.sidebar.header("⚙️ Filter Options")

    # 1. Tool selection
    st.sidebar.subheader("1. Select Tools")
    all_tools = sorted(tools_data.keys())
    selected_tools = st.sidebar.multiselect(
        "Choose tools to compare:",
        options=all_tools,
        default=all_tools,
        help="Select which tools to include in the comparison table",
    )

    if not selected_tools:
        st.warning("⚠️ Please select at least one tool from the sidebar.")
        return

    # Filter tools data based on selection
    filtered_tools_data = {
        tool: features
        for tool, features in tools_data.items()
        if tool in selected_tools
    }

    # 2. Percentage calculation options
    st.sidebar.subheader("2. Percentage Calculation")
    count_unsourced = st.sidebar.checkbox(
        "Include unsourced features",
        value=True,
        help="Count features marked as 'y' without source references in percentage calculations",
    )
    count_dev = st.sidebar.checkbox(
        "Include in-development features",
        value=False,
        help="Count features marked as 'dev' as implemented in percentage calculations",
    )

    # 3. Use case filtering
    st.sidebar.subheader("3. Filter by Use Case")
    use_case_options = ["All Features"] + sorted(use_cases_data.keys())
    selected_use_case = st.sidebar.selectbox(
        "Filter features by use case:",
        options=use_case_options,
        help="Show only features required by a specific use case",
    )

    # Apply use case filtering if selected
    use_case_data = None
    if selected_use_case != "All Features":
        use_case_data = use_cases_data[selected_use_case]
        use_case_features = use_case_data["features"]
        filtered_tools_data = {
            tool: filter_features_by_use_case(features, use_case_features)
            for tool, features in filtered_tools_data.items()
        }

        # Check if any features remain after filtering
        has_features = any(bool(features) for features in filtered_tools_data.values())
        if not has_features:
            st.warning(
                f"⚠️ No features found for use case '{selected_use_case}' in the selected tools."
            )
            return

    # Legend in sidebar
    st.sidebar.markdown(
        f"""
        ---
        ## 📖 Legend

        **Feature Symbols:**

        - <span style="color: {COLOR_SCHEME["y"]["sourced"]};">{SYMBOLS["y"]}</span> Implemented
          (<span style="color: {COLOR_SCHEME["y"]["unsourced"]};">{SYMBOLS["y"]}</span> without sources)
        - <span style="color: {COLOR_SCHEME["dev"]["sourced"]};">{SYMBOLS["dev"]}</span> In development
          (<span style="color: {COLOR_SCHEME["dev"]["unsourced"]};">{SYMBOLS["dev"]}</span> without sources)
        - <span style="color: {COLOR_SCHEME["n"]["sourced"]};">{SYMBOLS["n"]}</span> Not implemented
          (<span style="color: {COLOR_SCHEME["n"]["unsourced"]};">{SYMBOLS["n"]}</span> without sources)
        """,
        unsafe_allow_html=True,
    )

    st.sidebar.markdown(
        f"""
        **Percentage Calculation:**

        - Unsourced: {"✓ Included" if count_unsourced else "✗ Excluded"}
        - In-dev: {"✓ Included" if count_dev else "✗ Excluded"}
        """
    )

    # Main content
    st.write(
        f"Comparing **{len(selected_tools)}** tools: {', '.join(sorted(selected_tools))}"
    )

    # Display use case information if selected
    if selected_use_case != "All Features" and use_case_data:
        # Show use case name and description in info box
        description = use_case_data.get("description", "")
        if description:
            st.info(f"📋 **Use Case:** {selected_use_case}\n\n{description}")
        else:
            st.info(f"📋 **Use Case:** {selected_use_case}")

        # Show assumptions in an expander if they exist
        assumptions = use_case_data.get("assumptions", [])
        if assumptions:
            with st.expander("📌 View Use Case Assumptions"):
                for assumption in assumptions:
                    st.markdown(f"- {assumption}")
        elif assumptions == []:
            with st.expander("📌 View Use Case Assumptions"):
                st.markdown("*No specific assumptions defined for this use case.*")

    st.write(
        "Click on 'Overall' to expand all categories. Click on category names to expand/collapse detailed features. "
        "Hover over feature names to see their descriptions."
    )

    st.markdown("---")

    # Generate and display the collapsible table
    # Use a very large height to accommodate fully expanded table
    # The iframe will auto-resize via JavaScript postMessage
    table_html = generate_collapsible_table(
        filtered_tools_data, count_unsourced, count_dev, feature_schema, ""
    )
    height = (
        sum(len(v) + 1 for v in next(iter(filtered_tools_data.values())).values()) * 40
    )  # Rough estimate: 40px per feature row
    components.html(table_html, height=height, scrolling=False)


if __name__ == "__main__":
    st.set_page_config(
        page_title="Energy System Modelling Tool Features",
        page_icon="🔩",
        layout="wide",
    )

    st.title("Tool Feature Gap Analysis")

    # Load data
    features_output_dir = Path(__file__).parent.parent.parent / "features" / "output"
    tools_dir = features_output_dir / "tools"
    tools_data = load_tool_features(tools_dir)

    use_cases_dir = features_output_dir / "use-cases"
    use_cases_data = load_use_case_features(use_cases_dir)

    schema_path = features_output_dir / "features.yaml"
    feature_schema = yaml.safe_load(schema_path.read_text())

    if not tools_data:
        st.error("No tool data found. Please check the tools/ directory.")

    main(tools_data, use_cases_data, feature_schema)
