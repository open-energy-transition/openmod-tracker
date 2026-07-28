# SPDX-FileCopyrightText: openmod-tracker contributors
#
# SPDX-License-Identifier: MIT

"""Data model for energy system modeling tool."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, HttpUrl


class Tool(BaseModel):
    """Master data model for energy system modeling tool.

    Source of truth for generating all CSV output files.
    """

    # ==================== Core Identity ====================
    id: Annotated[str, Field(description="Unique identifier (slug)")]
    name: Annotated[str, Field(description="Display name of the tool")]
    description: Annotated[str | None, Field(description="Brief description")] = None
    url: Annotated[HttpUrl, Field(description="Primary URL (repository or homepage)")]
    source: Annotated[
        str | None, Field(description="Data source(s), comma-separated")
    ] = None
    category: Annotated[
        str | None, Field(description="Tool category(ies), comma-separated")
    ] = None

    # ==================== Repository Metadata ====================
    owner: Annotated[str | None, Field(description="Repository owner/organization")] = (
        None
    )
    archived: Annotated[
        bool | None, Field(description="Whether repository is archived")
    ] = None

    # ==================== Repository Statistics ====================
    stargazers_count: Annotated[
        int | None, Field(description="Number of GitHub stars")
    ] = None
    forks_count: Annotated[
        int | None, Field(description="Number of repository forks")
    ] = None
    language: Annotated[
        str | None, Field(description="Primary programming language")
    ] = None
    license: Annotated[str | None, Field(description="Software license")] = None
    created_at: Annotated[
        datetime | None, Field(description="Repository creation date")
    ] = None
    pushed_at: Annotated[datetime | None, Field(description="Last push date")] = None
    updated_at: Annotated[datetime | None, Field(description="Last update date")] = None
    commit_stats_dds: Annotated[
        float | None, Field(description="Commit diversity score")
    ] = None
    commit_stats_total_committers: Annotated[
        int | None, Field(description="Total number of committers")
    ] = None
    homepage: Annotated[str | None, Field(description="Project homepage URL")] = None
    active_maintainers_count: Annotated[
        int | None, Field(description="Number of active maintainers")
    ] = None
    last_month_downloads: Annotated[
        float | None, Field(description="Downloads in the last month")
    ] = None
    dependent_repos_count: Annotated[
        float | None, Field(description="Number of dependent repositories")
    ] = None
    latest_release_published_at: Annotated[
        str | None, Field(description="Latest release publish date")
    ] = None

    # ==================== OpenSSF Scorecard Metrics ====================
    aggregated_score: Annotated[
        float | None, Field(description="Overall OpenSSF security score")
    ] = None
    score_binary_artifacts: Annotated[
        int | None, Field(ge=0, le=10, description="Binary artifacts score")
    ] = None
    score_branch_protection: Annotated[
        int | None, Field(ge=0, le=10, description="Branch protection score")
    ] = None
    score_ci_tests: Annotated[
        int | None, Field(ge=0, le=10, description="CI tests score")
    ] = None
    score_cii_best_practices: Annotated[
        int | None, Field(ge=0, le=10, description="CII best practices score")
    ] = None
    score_code_review: Annotated[
        int | None, Field(ge=0, le=10, description="Code review score")
    ] = None
    score_contributors: Annotated[
        int | None, Field(ge=0, le=10, description="Contributors score")
    ] = None
    score_dangerous_workflow: Annotated[
        int | None, Field(ge=0, le=10, description="Dangerous workflow score")
    ] = None
    score_dependency_update_tool: Annotated[
        int | None, Field(ge=0, le=10, description="Dependency update tool score")
    ] = None
    score_fuzzing: Annotated[
        int | None, Field(ge=0, le=10, description="Fuzzing score")
    ] = None
    score_license: Annotated[
        int | None, Field(ge=0, le=10, description="License score")
    ] = None
    score_maintained: Annotated[
        int | None, Field(ge=0, le=10, description="Maintained score")
    ] = None
    score_packaging: Annotated[
        int | None, Field(ge=0, le=10, description="Packaging score")
    ] = None
    score_pinned_dependencies: Annotated[
        int | None, Field(ge=0, le=10, description="Pinned dependencies score")
    ] = None
    score_sast: Annotated[int | None, Field(ge=0, le=10, description="SAST score")] = (
        None
    )
    score_security_policy: Annotated[
        int | None, Field(ge=0, le=10, description="Security policy score")
    ] = None
    score_signed_releases: Annotated[
        int | None, Field(ge=0, le=10, description="Signed releases score")
    ] = None
    score_token_permissions: Annotated[
        int | None, Field(ge=0, le=10, description="Token permissions score")
    ] = None
    score_vulnerabilities: Annotated[
        int | None, Field(ge=0, le=10, description="Vulnerabilities score")
    ] = None

    # ==================== Score Explanations ====================
    reason_binary_artifacts: Annotated[
        str | None, Field(description="Explanation for binary artifacts score")
    ] = None
    reason_branch_protection: Annotated[
        str | None, Field(description="Explanation for branch protection score")
    ] = None
    reason_ci_tests: Annotated[
        str | None, Field(description="Explanation for CI tests score")
    ] = None
    reason_cii_best_practices: Annotated[
        str | None, Field(description="Explanation for CII best practices score")
    ] = None
    reason_code_review: Annotated[
        str | None, Field(description="Explanation for code review score")
    ] = None
    reason_contributors: Annotated[
        str | None, Field(description="Explanation for contributors score")
    ] = None
    reason_dangerous_workflow: Annotated[
        str | None, Field(description="Explanation for dangerous workflow score")
    ] = None
    reason_dependency_update_tool: Annotated[
        str | None, Field(description="Explanation for dependency update tool score")
    ] = None
    reason_fuzzing: Annotated[
        str | None, Field(description="Explanation for fuzzing score")
    ] = None
    reason_license: Annotated[
        str | None, Field(description="Explanation for license score")
    ] = None
    reason_maintained: Annotated[
        str | None, Field(description="Explanation for maintained score")
    ] = None
    reason_packaging: Annotated[
        str | None, Field(description="Explanation for packaging score")
    ] = None
    reason_pinned_dependencies: Annotated[
        str | None, Field(description="Explanation for pinned dependencies score")
    ] = None
    reason_sast: Annotated[
        str | None, Field(description="Explanation for SAST score")
    ] = None
    reason_security_policy: Annotated[
        str | None, Field(description="Explanation for security policy score")
    ] = None
    reason_signed_releases: Annotated[
        str | None, Field(description="Explanation for signed releases score")
    ] = None
    reason_token_permissions: Annotated[
        str | None, Field(description="Explanation for token permissions score")
    ] = None
    reason_vulnerabilities: Annotated[
        str | None, Field(description="Explanation for vulnerabilities score")
    ] = None

    # ==================== Documentation ====================
    rtd: Annotated[str | None, Field(description="Read the Docs URL")] = None
    pages: Annotated[str | None, Field(description="GitHub/GitLab Pages URL")] = None
    wiki: Annotated[str | None, Field(description="Wiki URL")] = None

    # ==================== Package Distribution ====================
    pypi_package_url: Annotated[str | None, Field(description="PyPI package URL")] = (
        None
    )
    pypi_package_name: Annotated[str | None, Field(description="PyPI package name")] = (
        None
    )
    anaconda_package_url: Annotated[
        str | None, Field(description="Anaconda package URL")
    ] = None
    juliahub_package_url: Annotated[
        str | None, Field(description="JuliaHub package URL")
    ] = None
    other_source: Annotated[
        str | None, Field(description="Other package source URL")
    ] = None

    # ==================== Download Statistics ====================
    monthly_downloads: Annotated[
        dict[str, float] | None,
        Field(description="Monthly download counts keyed by YYYY-MM"),
    ] = None

    # ==================== Export Methods ====================
    def to_tools_csv_row(self) -> dict:
        """Export format for tools.csv."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "url": str(self.url),
            "source": self.source,
            "category": self.category,
        }

    def to_filtered_csv_row(self) -> dict:
        """Export format for filtered.csv."""
        return {
            "id": self.id,
            "url": str(self.url),
            "name": self.name,
            "source": self.source,
            "category": self.category,
        }

    def to_stats_csv_row(self) -> dict:
        """Export format for stats.csv."""
        return {
            "id": self.id,
            "html_url": str(self.url),
            "owner": self.owner,
            "archived": self.archived,
            "stargazers_count": self.stargazers_count,
            "forks_count": self.forks_count,
            "language": self.language,
            "license": self.license,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "pushed_at": self.pushed_at.isoformat() if self.pushed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "commit_stats.dds": self.commit_stats_dds,
            "commit_stats.total_committers": self.commit_stats_total_committers,
            "homepage": self.homepage,
            "active_maintainers_count": self.active_maintainers_count,
            "last_month_downloads": self.last_month_downloads,
            "dependent_repos_count": self.dependent_repos_count,
            "latest_release_published_at": self.latest_release_published_at,
        }

    def to_scores_csv_row(self) -> dict:
        """Export format for scores.csv."""
        return {
            "id": self.id,
            "html_url": str(self.url),
            "aggregated_score": self.aggregated_score,
            "Binary-Artifacts": self.score_binary_artifacts,
            "Branch-Protection": self.score_branch_protection,
            "CI-Tests": self.score_ci_tests,
            "CII-Best-Practices": self.score_cii_best_practices,
            "Code-Review": self.score_code_review,
            "Contributors": self.score_contributors,
            "Dangerous-Workflow": self.score_dangerous_workflow,
            "Dependency-Update-Tool": self.score_dependency_update_tool,
            "Fuzzing": self.score_fuzzing,
            "License": self.score_license,
            "Maintained": self.score_maintained,
            "Packaging": self.score_packaging,
            "Pinned-Dependencies": self.score_pinned_dependencies,
            "SAST": self.score_sast,
            "Security-Policy": self.score_security_policy,
            "Signed-Releases": self.score_signed_releases,
            "Token-Permissions": self.score_token_permissions,
            "Vulnerabilities": self.score_vulnerabilities,
        }

    def to_reasons_csv_row(self) -> dict:
        """Export format for reasons.csv."""
        return {
            "id": self.id,
            "html_url": str(self.url),
            "Reason Binary-Artifacts": self.reason_binary_artifacts,
            "Reason Branch-Protection": self.reason_branch_protection,
            "Reason CI-Tests": self.reason_ci_tests,
            "Reason CII-Best-Practices": self.reason_cii_best_practices,
            "Reason Code-Review": self.reason_code_review,
            "Reason Contributors": self.reason_contributors,
            "Reason Dangerous-Workflow": self.reason_dangerous_workflow,
            "Reason Dependency-Update-Tool": self.reason_dependency_update_tool,
            "Reason Fuzzing": self.reason_fuzzing,
            "Reason License": self.reason_license,
            "Reason Maintained": self.reason_maintained,
            "Reason Packaging": self.reason_packaging,
            "Reason Pinned-Dependencies": self.reason_pinned_dependencies,
            "Reason SAST": self.reason_sast,
            "Reason Security-Policy": self.reason_security_policy,
            "Reason Signed-Releases": self.reason_signed_releases,
            "Reason Token-Permissions": self.reason_token_permissions,
            "Reason Vulnerabilities": self.reason_vulnerabilities,
        }

    def to_docs_csv_row(self) -> dict:
        """Export format for docs.csv."""
        return {"id": self.id, "rtd": self.rtd, "pages": self.pages, "wiki": self.wiki}

    def to_package_downloads_csv_row(self) -> dict:
        """Export format for package_downloads.csv."""
        row = {
            "id": self.id,
            "html_url": str(self.url),
            "pypi_package_url": self.pypi_package_url,
            "pypi_package_name": self.pypi_package_name,
            "anaconda_package_url": self.anaconda_package_url,
            "juliahub_package_url": self.juliahub_package_url,
            "other_source": self.other_source,
        }

        # Add monthly download columns
        if self.monthly_downloads:
            for month, count in self.monthly_downloads.items():
                # Convert YYYY-MM to column name format (e.g., "2026-05" -> "2026-05")
                row[month] = count

        return row
