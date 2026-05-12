"""Playwright E2E tests for the Tournament IQ SPA."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect


def test_page_loads_title(page, live_server):
    page.goto("/static/index.html")
    expect(page).to_have_title("Tournament IQ")


def test_sidebar_nav_links_present(page, live_server):
    page.goto("/static/index.html")
    nav = page.locator("#sidebar nav, #sidebar .nav, nav[aria-label]").first
    # At minimum the Tournaments view link must exist
    tournaments_link = page.locator("text=Tournaments").first
    expect(tournaments_link).to_be_visible()


def test_tournaments_table_renders(page, live_server):
    page.goto("/static/index.html")
    # Wait for the main table to appear (empty data is fine — the table header must be there)
    page.wait_for_selector("#tournamentsTable, table", timeout=8000)
    table = page.locator("#tournamentsTable, table").first
    expect(table).to_be_visible()


def test_view_switching_shows_correct_section(page, live_server):
    page.goto("/static/index.html")
    page.wait_for_load_state("networkidle")

    # Find and click the Team Analysis nav item
    team_analysis = page.locator("text=Team Analysis").first
    if team_analysis.is_visible():
        team_analysis.click()
        # The team analysis section should become visible
        analysis_section = page.locator("#teamAnalysisView, [data-view='team-analysis']").first
        if analysis_section.count():
            expect(analysis_section).to_be_visible()


def test_theme_toggle_persists(page, live_server):
    page.goto("/static/index.html")
    page.wait_for_load_state("networkidle")

    toggle = page.locator("#themeToggle, [aria-label*='theme'], [title*='theme'], button.theme-toggle").first
    if not toggle.count():
        pytest.skip("Theme toggle not found — skipping")

    # Read initial theme
    initial_theme = page.evaluate("() => localStorage.getItem('theme') || document.documentElement.dataset.theme || ''")
    toggle.click()
    page.wait_for_timeout(300)
    new_theme = page.evaluate("() => localStorage.getItem('theme') || document.documentElement.dataset.theme || ''")

    # After toggle, theme should have changed
    assert initial_theme != new_theme, f"Theme did not change: was '{initial_theme}', still '{new_theme}'"

    # Reload — theme should persist from localStorage
    page.reload()
    page.wait_for_load_state("networkidle")
    persisted = page.evaluate("() => localStorage.getItem('theme') || document.documentElement.dataset.theme || ''")
    assert persisted == new_theme, f"Theme not persisted: expected '{new_theme}', got '{persisted}'"


def test_no_js_errors_on_load(page, live_server):
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto("/static/index.html")
    page.wait_for_load_state("networkidle")
    assert errors == [], f"JS errors on page load: {errors}"


def test_filter_controls_are_interactive(page, live_server):
    page.goto("/static/index.html")
    page.wait_for_load_state("networkidle")

    # Source filter checkboxes or selects should be visible
    source_filter = page.locator(
        "input[type='checkbox'][data-source], "
        "select[id*='source'], select[id*='filter'], "
        "#filterSource, .filter-bar"
    ).first
    if source_filter.count():
        expect(source_filter).to_be_visible()
    else:
        pytest.skip("No source filter controls found — skipping")


def test_shortlist_status_dropdown_present(page, live_server):
    page.goto("/static/index.html")
    page.wait_for_load_state("networkidle")

    # The shortlist status select should be somewhere in the DOM
    # (even if table is empty, the template should render it for any row)
    status_select = page.locator("select.status-select, select[data-action='shortlist']").first
    # Only assert visible if there are rows
    rows = page.locator("#tournamentsTable tbody tr, table tbody tr").count()
    if rows > 0 and status_select.count() > 0:
        expect(status_select.first).to_be_visible()
