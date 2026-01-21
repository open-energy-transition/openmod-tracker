# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Streamlit app to display energy system modelling tool feature comparison."""

import base64
import json
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
    return {
        tool_path.parent.name: yaml.safe_load(tool_path.read_text())["features"]
        for tool_path in sorted(tools_dir.rglob("features.yaml"))
    }


def load_use_case_features(use_cases_dir: Path) -> dict[str, dict]:
    """Load features.yaml for all use cases.

    Args:
        use_cases_dir: Path to the use-cases directory

    Returns:
        Dictionary mapping use case name to full use case data (features, assumptions, description, etc.)
    """

    def _load_use_case(use_case_path: Path) -> tuple[str, dict]:
        data = yaml.safe_load(use_case_path.read_text())
        metadata_path = use_case_path.parent / ".metadata.yml"
        description = yaml.safe_load(metadata_path.read_text())["description"]
        name = use_case_path.parent.name.replace("_", " ").title()
        return name, {
            "features": data["features"],
            "assumptions": data["assumptions"],
            "description": description,
            "id": use_case_path.name,
        }

    return dict(
        _load_use_case(path) for path in sorted(use_cases_dir.rglob("features.yaml"))
    )


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


def _count_feature_as_met(
    feature_value: str, has_source: bool, count_unsourced: bool, count_dev: bool
) -> bool:
    """Helper to determine if a feature should be counted as met.

    Args:
        feature_value: The feature value ('y', 'n', or 'dev')
        has_source: Whether the feature has source references
        count_unsourced: Whether to count 'y' without sources
        count_dev: Whether to count 'dev' as met

    Returns:
        True if feature should be counted as met
    """
    if feature_value == "y":
        return has_source or count_unsourced
    elif feature_value == "dev":
        return count_dev
    return False


def calculate_use_case_coverage(
    tool_features: dict,
    use_case_features: dict,
    count_unsourced: bool = True,
    count_dev: bool = False,
) -> float | None:
    """Calculate percentage of use case requirements met by a tool.

    Args:
        tool_features: Features dictionary for a single tool
        use_case_features: Use case required features (value='y' means required)
        count_unsourced: Whether to count 'y' without sources as met
        count_dev: Whether to count 'dev' as met

    Returns:
        Percentage of required features that are met by the tool, or None if no requirements
    """
    total_required = 0
    met_count = 0

    for category, category_features in use_case_features.items():
        if category not in tool_features:
            # Category doesn't exist in tool - count all required features as unmet
            for feature_name, feature_data in category_features.items():
                if feature_data.get("value", "n") == "y":
                    total_required += 1
            continue

        for feature_name, feature_data in category_features.items():
            # Only count features required by the use case
            if feature_data.get("value", "n") != "y":
                continue

            total_required += 1

            # Check if tool has this feature
            if feature_name not in tool_features[category]:
                continue  # Tool doesn't have this feature

            tool_feature = tool_features[category][feature_name]
            tool_value = tool_feature.get("value", "n")
            has_source = bool(tool_feature.get("source", []))

            # Check if feature is met based on criteria
            if _count_feature_as_met(
                tool_value, has_source, count_unsourced, count_dev
            ):
                met_count += 1

    return (met_count / total_required * 100) if total_required > 0 else None


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
            if _count_feature_as_met(
                feature_value, has_source, count_unsourced, count_dev
            ):
                yes_count += 1
        elif isinstance(value, dict):
            # Nested group
            for feature in value.values():
                if isinstance(feature, dict) and "value" in feature:
                    total += 1
                    feature_value = feature["value"]
                    has_source = bool(feature.get("source", []))
                    if _count_feature_as_met(
                        feature_value, has_source, count_unsourced, count_dev
                    ):
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


def get_theme_colors() -> dict[str, str]:
    """Get color scheme based on current Streamlit theme.

    Returns:
        Dictionary of color values for the current theme
    """
    theme = st.context.theme.type

    if theme == "dark":
        return {
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
            "checkbox_border": "#fafafa33",
        }
    else:  # light theme
        return {
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
            "checkbox_border": "#d0d0d0",
        }


def encode_custom_use_case(features: dict, name: str = "Custom Use Case") -> str:
    """Encode custom use case features to URL-safe string.

    Args:
        features: Dictionary of category -> {feature_name: True/False}
        name: Name for the custom use case

    Returns:
        Base64 URL-safe encoded string
    """
    # Compress to only include True values
    compressed = {"_name": name}
    for category, feature_dict in features.items():
        selected = [f for f, v in feature_dict.items() if v]
        if selected:
            compressed[category] = selected

    json_str = json.dumps(compressed, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(json_str.encode()).decode()
    return encoded


def decode_custom_use_case(encoded: str) -> tuple[dict, str]:
    """Decode custom use case from URL parameter.

    Args:
        encoded: Base64 URL-safe encoded string

    Returns:
        Tuple of (features dictionary, name string)
    """
    try:
        json_str = base64.urlsafe_b64decode(encoded.encode()).decode()
        compressed = json.loads(json_str)
        # Extract name (default to "Custom Use Case" for backward compatibility)
        name = compressed.pop("_name", "Custom Use Case")
        # Expand to full format with True values
        features = {}
        for category, feature_list in compressed.items():
            features[category] = {f: True for f in feature_list}
        return features, name
    except Exception:
        return {}, "Custom Use Case"


def load_custom_use_case_from_url() -> tuple[dict | None, str | None]:
    """Load custom use case from URL parameters if present.

    Returns:
        Tuple of (features dictionary or None, name or None)
    """
    query_params = st.query_params
    custom_encoded = query_params.get("custom_features", None)

    if custom_encoded:
        return decode_custom_use_case(custom_encoded)
    return None, None


def _get_feature_description(
    schema: dict | None, category: str, feature_name: str = ""
) -> str:
    """Get description from schema for a category or feature.

    Args:
        schema: Feature schema dictionary
        category: Category name
        feature_name: Optional feature name within category

    Returns:
        Description string or empty string if not found
    """
    if not schema or category not in schema:
        return ""

    if feature_name:
        # Get feature description
        return schema[category].get("members", {}).get(feature_name, "")
    else:
        # Get category description
        return schema[category].get("description", "")


def add_coverage_calculation_checkboxes(
    section_number: str = "2", section_title: str = "Percentage Calculation"
) -> tuple[bool, bool]:
    """Add sidebar checkboxes for coverage calculation options.

    Args:
        section_number: Section number to display in sidebar
        section_title: Title for the sidebar section

    Returns:
        Tuple of (count_unsourced, count_dev) boolean values
    """
    st.sidebar.subheader(f"{section_number}. {section_title}")
    count_unsourced = st.sidebar.checkbox(
        "Include unvalidated features",
        value=True,
        help="Count features marked as 'y' without source references in percentage calculations",
    )
    count_dev = st.sidebar.checkbox(
        "Include in-development features",
        value=False,
        help="Count features marked as 'dev' as implemented in percentage calculations",
    )
    return count_unsourced, count_dev


def main_use_case_comparison(
    tools_data: dict[str, dict], use_cases_data: dict[str, dict], feature_schema: dict
):
    """Use case comparison view - show features as rows, use cases as columns."""
    st.sidebar.header("⚙️ Filter Options")

    # 1. Tool selection (single tool)
    st.sidebar.subheader("1. Select Tool")
    all_tools = sorted(tools_data.keys())
    tool_options = ["None (show requirements only)"] + all_tools
    selected_tool_raw = st.sidebar.selectbox(
        "Choose a tool to evaluate:",
        options=tool_options,
        help="Select which tool to evaluate against use case requirements, or 'None' to only show requirements",
    )

    # Handle None selection
    selected_tool: str | None = (
        None
        if selected_tool_raw == "None (show requirements only)"
        else selected_tool_raw
    )

    # 2. Use case selection
    st.sidebar.subheader("2. Select Use Cases")
    # Put custom use case first if it exists
    other_use_cases = sorted(
        [uc for uc in use_cases_data.keys() if not uc.endswith(" (custom)")]
    )
    custom_use_case_list = [
        uc for uc in use_cases_data.keys() if uc.endswith(" (custom)")
    ]
    all_use_cases = custom_use_case_list + other_use_cases

    # Default to custom use case if it exists, otherwise all use cases
    default_selection = custom_use_case_list if custom_use_case_list else all_use_cases

    selected_use_cases = st.sidebar.multiselect(
        "Choose use cases to compare:",
        options=all_use_cases,
        default=default_selection,
        help="Select which use cases to include in the comparison",
    )

    if not selected_use_cases:
        st.warning("⚠️ Please select at least one use case from the sidebar.")
        return

    # 3. Coverage calculation options (only show if tool is selected)
    if selected_tool:
        count_unsourced, count_dev = add_coverage_calculation_checkboxes(
            "3", "Coverage Calculation"
        )
    else:
        count_unsourced, count_dev = True, False

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
    if selected_tool:
        st.write(
            f"Evaluating **{selected_tool}** against **{len(selected_use_cases)}** use cases: {', '.join(sorted(selected_use_cases))}"
        )
        st.write(
            "Click on 'Overall' to expand all categories. Click on category names to expand/collapse detailed features. "
            "Color coding: Green = tool has feature, Blue = in development, Red = tool lacks feature, Gray = not required by use case."
        )
    else:
        st.write(
            f"Showing feature requirements for **{len(selected_use_cases)}** use cases: {', '.join(sorted(selected_use_cases))}"
        )
        st.write(
            "Click on 'Overall' to expand all categories. Click on category names to expand/collapse detailed features. "
            "✓ indicates required features, ○ indicates optional features."
        )

    st.markdown("---")

    # Generate and display the pivoted table
    table_html = generate_use_case_comparison_table(
        tools_data[selected_tool] if selected_tool else None,
        {uc: use_cases_data[uc] for uc in selected_use_cases},
        feature_schema,
        count_unsourced=count_unsourced,
        count_dev=count_dev,
    )
    height = 600  # Fixed height for iframe
    components.html(table_html, height=height, scrolling=True)


def _build_use_case_status(
    feature_name: str,
    category: str,
    tool_status: str,
    use_case_name: str,
    use_case_features: dict,
) -> dict[str, str | bool]:
    """Build status dictionary for a feature in a use case.

    Args:
        feature_name: Name of the feature
        category: Category name
        tool_status: Tool's implementation status ('y', 'n', 'dev', 'no_tool', 'not_required')
        use_case_name: Name of the use case
        use_case_features: Use case features dictionary

    Returns:
        Dictionary with 'required' and 'tool_status' keys
    """
    required = (
        category in use_case_features
        and feature_name in use_case_features[category]
        and use_case_features[category][feature_name].get("value", "n") == "y"
    )

    if tool_status in ("no_tool", "not_required"):
        status = tool_status
    else:
        status = tool_status if required else "not_required"

    return {"required": required, "tool_status": status}


def generate_use_case_comparison_table(
    tool_features: dict | None,
    use_cases_data: dict[str, dict],
    schema: dict[str, dict] | None = None,
    count_unsourced: bool = True,
    count_dev: bool = False,
) -> str:
    """Generate HTML table comparing a single tool against multiple use cases.

    Args:
        tool_features: Features dictionary for a single tool, or None to show only requirements
        use_cases_data: Dictionary of use case data (filtered to selected use cases)
        schema: Feature schema with descriptions for tooltips
        count_unsourced: Whether to count 'y' without sources as met
        count_dev: Whether to count 'dev' as met

    Returns:
        HTML string with the comparison table
    """
    # Setup Jinja2 environment
    env = Environment(loader=FileSystemLoader(Path(__file__).parent))
    env.filters["format_category_name"] = format_category_name
    env.filters["format_feature_name"] = format_feature_name
    env.filters["get_color_for_percentage"] = get_color_for_percentage

    # Get theme colors
    colors = get_theme_colors()

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

    # Calculate overall percentages per use case (only if tool is selected)
    overall_percentages = {}
    if tool_features is not None:
        for uc_name in use_case_names:
            uc_features = use_cases_data[uc_name]["features"]
            overall_percentages[uc_name] = calculate_use_case_coverage(
                tool_features, uc_features, count_unsourced, count_dev
            )

    # Build data structure for template
    def _build_category_data(cat_idx: int, category: str) -> dict | None:
        """Build data for a single category."""
        # Calculate category percentages per use case (only if tool is selected)
        category_percentages = {}
        if tool_features is not None:
            category_percentages = {
                uc_name: (
                    calculate_use_case_coverage(
                        tool_features,
                        {category: use_cases_data[uc_name]["features"][category]},
                        count_unsourced,
                        count_dev,
                    )
                    if category in use_cases_data[uc_name]["features"]
                    else None
                )
                for uc_name in use_case_names
            }

        # Get all features for this category
        if tool_features is not None:
            # Tool selected: iterate through tool's features
            category_features = tool_features.get(category, {})
            features_data = [
                {
                    "name": feature_name,
                    "description": _get_feature_description(
                        schema, category, feature_name
                    ),
                    "statuses": {
                        uc_name: _build_use_case_status(
                            feature_name,
                            category,
                            feature_value.get("value", "n"),
                            uc_name,
                            use_cases_data[uc_name]["features"],
                        )
                        for uc_name in use_case_names
                    },
                }
                for feature_name, feature_value in category_features.items()
            ]
        else:
            # No tool selected: collect all features from use cases
            all_features_in_category = {
                feature_name
                for uc_data in use_cases_data.values()
                if category in uc_data["features"]
                for feature_name in uc_data["features"][category].keys()
            }

            features_data = [
                {
                    "name": feature_name,
                    "description": _get_feature_description(
                        schema, category, feature_name
                    ),
                    "statuses": {
                        uc_name: _build_use_case_status(
                            feature_name,
                            category,
                            "no_tool",
                            uc_name,
                            use_cases_data[uc_name]["features"],
                        )
                        for uc_name in use_case_names
                    },
                }
                for feature_name in sorted(all_features_in_category)
            ]

        if not features_data:  # Skip categories without features
            return None

        return {
            "id": f"cat_{cat_idx}",
            "name": category,
            "description": _get_feature_description(schema, category),
            "features": features_data,
            "percentages": category_percentages,
        }

    categories_data = [
        cat_data
        for cat_idx, category in enumerate(categories)
        if (cat_data := _build_category_data(cat_idx, category)) is not None
    ]

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
        "overall_percentages": overall_percentages,
        "has_tool": tool_features is not None,
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
        features_data = [
            {
                "name": feature,
                "description": _get_feature_description(schema, category, feature),
                "values": {
                    tool: (
                        {
                            "value": tools_data[tool][category][feature].get(
                                "value", "n"
                            ),
                            "sources": tools_data[tool][category][feature].get(
                                "source", []
                            ),
                        }
                        if category in tools_data[tool]
                        and feature in tools_data[tool][category]
                        else {"value": "n", "sources": []}
                    )
                    for tool in tool_names
                },
            }
            for feature in first_tool[category].keys()
        ]

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

    # Calculate first column width based on longest text
    first_column_texts = (
        ["Overall"]
        + [format_category_name(cat["name"]) for cat in categories_data]
        + [
            f"    {format_feature_name(f['name'])}"
            for cat in categories_data
            for f in cat["features"]
        ]
    )

    # Estimate width: ~8px per character, with min/max bounds
    max_text_length = max(len(text) for text in first_column_texts)
    first_column_width = max(250, min(max_text_length * 8 + 24, 600))

    # Get theme colors
    colors = get_theme_colors()

    context = {
        "tool_names": tool_names,
        "overall_percentages": overall_percentages,
        "categories_data": categories_data,
        "search_query": search_query,
        "colors": colors,
        "first_column_width": first_column_width,
    }

    return template.render(**context)


def main_use_case_builder(feature_schema: dict, use_cases_data: dict[str, dict]):
    """Use case builder view - interactive table for creating custom use cases."""
    st.write("### 🎨 Custom Use Case Builder")
    st.write(
        "Select the features you need for your use case. Categories can be expanded by clicking their names. "
        "When you're done selecting features, click 'Apply Custom Use Case' to make it available in other views."
    )

    # Load existing custom use case from URL
    existing_custom_features, existing_custom_name = load_custom_use_case_from_url()

    st.write("#### Starting Point")

    template_use_cases = {
        k: v for k, v in use_cases_data.items() if not k.endswith(" (custom)")
    }
    use_case_options = ["Start from scratch"] + sorted(template_use_cases.keys())

    selected_template = st.selectbox(
        "Choose a use case as a starting point:",
        options=use_case_options,
        help="Select an existing use case to pre-populate features, or start from scratch",
    )

    if selected_template != "Start from scratch":
        if st.button(
            f"📋 Load '{selected_template}' features", use_container_width=True
        ):
            template_features = template_use_cases[selected_template]["features"]
            template_selections = {}
            for category, features in template_features.items():
                template_selections[category] = {}
                for feature_name, feature_data in features.items():
                    if feature_data.get("value", "n") == "y":
                        template_selections[category][feature_name] = True

            # Encode and save to URL so it persists across rerun
            encoded = encode_custom_use_case(template_selections)
            st.query_params.update({"custom_features": encoded})
            st.success(f"✅ Loaded features from '{selected_template}'")
            st.rerun()

    st.markdown("---")

    preselected = existing_custom_features or {}

    # Use a form for feature selection
    with st.form("custom_use_case_form"):
        st.write("#### Name Your Use Case")
        custom_name = st.text_input(
            "Use case name:",
            value=existing_custom_name or "My Use Case",
            help="This name will be used to identify your custom use case in other views",
            placeholder="Enter a descriptive name...",
        )

        st.write("#### Select Features")

        selected_features = {}

        for category in sorted(feature_schema.keys()):
            if "members" not in feature_schema[category]:
                continue

            category_desc = feature_schema[category].get("description", "")
            category_name = format_category_name(category)

            with st.expander(
                f"**{category_name}**"
                + (f" - {category_desc}" if category_desc else "")
            ):
                # Individual feature checkboxes
                for feature_name in sorted(feature_schema[category]["members"].keys()):
                    feature_desc = feature_schema[category]["members"].get(
                        feature_name, ""
                    )
                    default_val = preselected.get(category, {}).get(feature_name, False)

                    is_selected = st.checkbox(
                        format_feature_name(feature_name),
                        value=default_val,
                        key=f"feature_{category}_{feature_name}",
                        help=feature_desc if feature_desc else None,
                    )

                    if is_selected:
                        if category not in selected_features:
                            selected_features[category] = {}
                        selected_features[category][feature_name] = True

        st.markdown("---")

        col1, col2, _ = st.columns([2, 2, 1])

        with col1:
            submitted = st.form_submit_button(
                "🔄 Apply Custom Use Case", type="primary", use_container_width=True
            )

        with col2:
            cleared = st.form_submit_button(
                "🗑️ Clear Selection", use_container_width=True
            )

    if submitted:
        if selected_features:
            # Encode and update query params
            encoded = encode_custom_use_case(
                selected_features, custom_name.strip() or "My Use Case"
            )
            st.query_params.update({"custom_features": encoded})
            st.success(
                f"✅ '{custom_name}' applied! ({sum(len(f) for f in selected_features.values())} features selected)"
            )
            st.info(
                "💡 Switch to 'Tools Comparison' or 'Use Cases Comparison' view to use your custom use case."
            )
            st.rerun()
        else:
            st.warning("⚠️ Please select at least one feature before applying.")

    if cleared:
        st.query_params.clear()
        st.success("✅ Selection cleared!")
        st.rerun()

    # Display info if custom use case exists
    if existing_custom_features and not submitted and not cleared:
        feature_count = sum(
            len(features) for features in existing_custom_features.values()
        )
        st.info(
            f"ℹ️ Currently loaded: {feature_count} features selected. Modify selections above and click 'Apply' to update."
        )


def main(
    tools_data: dict[str, dict], use_cases_data: dict[str, dict], feature_schema: dict
):
    """Main Streamlit app."""
    # Sidebar for filtering options
    st.sidebar.header("⚙️ View Options")

    # 0. View mode selection
    view_mode = st.sidebar.radio(
        "Select View Mode:",
        options=["Tools Comparison", "Use Cases Comparison", "Use Case Builder"],
        help="Choose between comparing tools, comparing use cases, or building a custom use case",
    )

    # Handle Use Case Builder view
    if view_mode == "Use Case Builder":
        main_use_case_builder(feature_schema, use_cases_data)
        return

    # Load custom use case from URL (available in comparison views)
    custom_features, custom_name = load_custom_use_case_from_url()

    # Add custom use case to use_cases_data if it exists
    if custom_features:
        use_cases_data = dict(use_cases_data)  # Make a copy
        # Convert custom features format to match expected format
        formatted_features = {}
        for category, features in custom_features.items():
            formatted_features[category] = {
                feature_name: {"value": "y"} for feature_name in features.keys()
            }

        # Use custom name with " (custom)" suffix
        custom_use_case_display_name = f"{custom_name} (custom)"
        use_cases_data[custom_use_case_display_name] = {
            "features": formatted_features,
            "assumptions": [],
            "description": f"Custom use case: {custom_name}",
            "id": "custom",
        }

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
    count_unsourced, count_dev = add_coverage_calculation_checkboxes()

    # 3. Use case filtering
    st.sidebar.subheader("3. Filter by Use Case")
    # Put custom use case first if it exists, then alphabetize others
    other_use_cases = sorted(
        [uc for uc in use_cases_data.keys() if not uc.endswith(" (custom)")]
    )
    custom_use_case_list = [
        uc for uc in use_cases_data.keys() if uc.endswith(" (custom)")
    ]
    use_case_options = ["All Features"] + custom_use_case_list + other_use_cases

    # Initialize session state for persisting use case selection
    if "selected_use_case" not in st.session_state:
        st.session_state.selected_use_case = "All Features"

    # Only switch to custom use case if it was just created
    if custom_features and not st.session_state.selected_use_case.endswith(" (custom)"):
        # Check if custom use case was just created by seeing if it's a new addition
        if custom_use_case_list and "last_custom_check" not in st.session_state:
            st.session_state.selected_use_case = custom_use_case_list[0]
    st.session_state.last_custom_check = bool(custom_use_case_list)

    # Ensure the selected use case is still valid (it might have been removed)
    if st.session_state.selected_use_case not in use_case_options:
        st.session_state.selected_use_case = "All Features"

    default_index = use_case_options.index(st.session_state.selected_use_case)

    selected_use_case = st.sidebar.selectbox(
        "Filter features by use case:",
        options=use_case_options,
        index=default_index,
        key="use_case_selector",
        help="Show only features required by a specific use case",
    )

    # Update session state when selection changes
    if selected_use_case != st.session_state.selected_use_case:
        st.session_state.selected_use_case = selected_use_case

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
