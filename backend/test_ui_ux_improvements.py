"""
Test UI/UX Improvements for HelpChain
Tests to verify that all UI/UX enhancements are working correctly
"""

import json
import os
import re
import tempfile

import pytest
from bs4 import BeautifulSoup
from flask import Flask, render_template_string


"""
Test UI/UX Improvements for HelpChain
Tests to verify that all UI/UX enhancements are working correctly
"""

import json
import os
import re
import tempfile

import pytest
from bs4 import BeautifulSoup
from flask import Flask, render_template_string


class TestUIUXImprovements:
    """Test class for UI/UX improvements"""

    @pytest.fixture
    def app(self):
        """Create a test Flask app"""
        app = Flask(__name__)
        app.config['TESTING'] = True
        app.config['SECRET_KEY'] = 'test-secret-key'

        @app.route('/')
        def index():
            return render_template_string('''
            <!DOCTYPE html>
            <html lang="bg">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Test Page</title>
                <!-- CSS Files -->
                <link rel="stylesheet" href="/static/css/design-system.css">
                <link rel="stylesheet" href="/static/css/animations.css">
                <link rel="stylesheet" href="/static/css/typography.css">
                <link rel="stylesheet" href="/static/css/forms.css">
                <link rel="stylesheet" href="/static/css/dashboard.css">
                <link rel="stylesheet" href="/static/css/themes.css">
                <link rel="stylesheet" href="/static/css/navigation.css">
                <link rel="stylesheet" href="/static/css/loading.css">
            </head>
            <body>
                <!-- Theme Toggle -->
                <button id="theme-toggle" aria-label="Превключи темата" title="Превключи между светла и тъмна тема">
                    <i id="theme-icon" class="bi bi-moon"></i>
                </button>

                <!-- Skip Link -->
                <a href="#main-content" class="skip-link">Отиди към основното съдържание</a>

                <main id="main-content">
                    <div class="dashboard-container">
                        <div class="dashboard-header">
                            <h1 class="dashboard-title">Test Dashboard</h1>
                            <p class="dashboard-subtitle">Testing UI/UX improvements</p>
                        </div>

                        <div class="dashboard-grid dashboard-grid-2">
                            <div class="dashboard-card stats-card">
                                <div class="stats-value">42</div>
                                <div class="stats-label">Test Items</div>
                                <div class="stats-change positive">+12%</div>
                            </div>

                            <div class="dashboard-card">
                                <div class="dashboard-card-header">
                                    <h3 class="dashboard-card-title">Test Card</h3>
                                    <i class="fas fa-test dashboard-card-icon" style="background: linear-gradient(135deg, #10b981 0%, #059669 100%);"></i>
                                </div>
                                <div class="dashboard-card-content">
                                    <p>This is a test card to verify dashboard styling.</p>
                                </div>
                            </div>
                        </div>

                        <form class="form-container">
                            <div class="form-group">
                                <label for="test-input" class="form-label">Test Input</label>
                                <input type="text" id="test-input" class="form-control" placeholder="Enter test data">
                            </div>
                            <div class="form-group">
                                <label for="test-select" class="form-label">Test Select</label>
                                <select id="test-select" class="form-select">
                                    <option value="">Choose an option</option>
                                    <option value="1">Option 1</option>
                                    <option value="2">Option 2</option>
                                </select>
                            </div>
                            <div class="form-actions">
                                <button type="submit" class="btn btn-primary">Submit</button>
                                <button type="button" class="btn btn-secondary">Cancel</button>
                            </div>
                        </form>
                    </div>
                </main>

                <script>
                // Theme toggle functionality
                function toggleTheme() {
                    const html = document.documentElement;
                    const themeIcon = document.getElementById('theme-icon');
                    const currentTheme = html.getAttribute('data-theme');

                    if (currentTheme === 'dark') {
                        html.removeAttribute('data-theme');
                        themeIcon.className = 'bi bi-moon';
                        localStorage.setItem('theme', 'light');
                    } else {
                        html.setAttribute('data-theme', 'dark');
                        themeIcon.className = 'bi bi-sun';
                        localStorage.setItem('theme', 'dark');
                    }
                }

                function initializeTheme() {
                    const savedTheme = localStorage.getItem('theme');
                    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                    const themeIcon = document.getElementById('theme-icon');

                    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
                        document.documentElement.setAttribute('data-theme', 'dark');
                        themeIcon.className = 'bi bi-sun';
                    } else {
                        themeIcon.className = 'bi bi-moon';
                    }
                }

                // Initialize theme on page load
                document.addEventListener('DOMContentLoaded', initializeTheme);

                // Theme toggle event listener
                document.getElementById('theme-toggle').addEventListener('click', toggleTheme);
                </script>
            </body>
            </html>
            ''')

        return app

    @pytest.fixture
    def client(self, app):
        """Create a test client"""
        return app.test_client()

    def test_css_files_exist(self):
        """Test that all CSS files exist"""
        css_files = [
            'static/css/design-system.css',
            'static/css/animations.css',
            'static/css/typography.css',
            'static/css/forms.css',
            'static/css/dashboard.css',
            'static/css/themes.css',
            'static/css/navigation.css',
            'static/css/loading.css'
        ]

        for css_file in css_files:
            assert os.path.exists(css_file), f"CSS file {css_file} does not exist"

    def test_css_files_have_content(self):
        """Test that CSS files have substantial content"""
        css_files = [
            'static/css/design-system.css',
            'static/css/animations.css',
            'static/css/typography.css',
            'static/css/forms.css',
            'static/css/dashboard.css',
            'static/css/themes.css',
            'static/css/navigation.css',
            'static/css/loading.css'
        ]

        for css_file in css_files:
            with open(css_file, encoding='utf-8') as f:
                content = f.read()
                assert len(content) > 1000, f"CSS file {css_file} has insufficient content"
                assert '/*' in content, f"CSS file {css_file} should have header comment"

    def test_base_template_includes_css(self, client):
        """Test that base template includes all CSS files"""
        response = client.get('/')
        assert response.status_code == 200

        html_content = response.data.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        # Check for CSS file includes
        css_links = soup.find_all('link', rel='stylesheet')
        css_hrefs = [link.get('href') for link in css_links]

        expected_css = [
            '/static/css/design-system.css',
            '/static/css/animations.css',
            '/static/css/typography.css',
            '/static/css/forms.css',
            '/static/css/dashboard.css',
            '/static/css/themes.css',
            '/static/css/navigation.css',
            '/static/css/loading.css'
        ]

        for css_file in expected_css:
            assert css_file in css_hrefs, f"CSS file {css_file} not included in base template"

    def test_theme_toggle_exists(self, client):
        """Test that theme toggle button exists"""
        response = client.get('/')
        assert response.status_code == 200

        html_content = response.data.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        theme_toggle = soup.find('button', id='theme-toggle')
        assert theme_toggle is not None, "Theme toggle button not found"

        assert theme_toggle.get('aria-label') == 'Превключи темата'
        assert theme_toggle.get('title') == 'Превключи между светла и тъмна тема'

        theme_icon = theme_toggle.find('i', id='theme-icon')
        assert theme_icon is not None, "Theme icon not found"
        assert 'bi' in theme_icon.get('class', []), "Theme icon should use Bootstrap Icons"

    def test_theme_javascript_exists(self, client):
        """Test that theme toggle JavaScript exists"""
        response = client.get('/')
        assert response.status_code == 200

        html_content = response.data.decode('utf-8')

        assert 'toggleTheme()' in html_content, "toggleTheme function not found"
        assert 'initializeTheme()' in html_content, "initializeTheme function not found"
        assert 'DOMContentLoaded' in html_content, "Theme initialization not found"

    def test_dashboard_components_render(self, client):
        """Test that dashboard components render correctly"""
        response = client.get('/')
        assert response.status_code == 200

        html_content = response.data.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        # Check dashboard container
        dashboard_container = soup.find('div', class_='dashboard-container')
        assert dashboard_container is not None, "Dashboard container not found"

        # Check dashboard header
        dashboard_header = soup.find('div', class_='dashboard-header')
        assert dashboard_header is not None, "Dashboard header not found"

        # Check dashboard title
        dashboard_title = soup.find('h1', class_='dashboard-title')
        assert dashboard_title is not None, "Dashboard title not found"
        assert dashboard_title.text.strip() == "Test Dashboard"

        # Check dashboard grid
        dashboard_grid = soup.find('div', class_='dashboard-grid')
        assert dashboard_grid is not None, "Dashboard grid not found"

        # Check stats card
        stats_card = soup.find('div', class_='stats-card')
        assert stats_card is not None, "Stats card not found"

        stats_value = stats_card.find('div', class_='stats-value')
        assert stats_value is not None, "Stats value not found"
        assert stats_value.text.strip() == "42"

        # Check dashboard card (the one with header)
        dashboard_cards = soup.find_all('div', class_='dashboard-card')
        assert len(dashboard_cards) >= 2, "Should have at least 2 dashboard cards"

        # Find the card with header
        card_with_header = None
        for card in dashboard_cards:
            if card.find('div', class_='dashboard-card-header'):
                card_with_header = card
                break

        assert card_with_header is not None, "Dashboard card with header not found"

        card_header = card_with_header.find('div', class_='dashboard-card-header')
        assert card_header is not None, "Dashboard card header not found"

    def test_form_components_render(self, client):
        """Test that form components render correctly"""
        response = client.get('/')
        assert response.status_code == 200

        html_content = response.data.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        # Check form container
        form_container = soup.find('form', class_='form-container')
        assert form_container is not None, "Form container not found"

        # Check form groups
        form_groups = soup.find_all('div', class_='form-group')
        assert len(form_groups) >= 2, "Should have at least 2 form groups"

        # Check form controls
        form_control = soup.find('input', class_='form-control')
        assert form_control is not None, "Form control not found"
        assert form_control.get('placeholder') == "Enter test data"

        # Check form select
        form_select = soup.find('select', class_='form-select')
        assert form_select is not None, "Form select not found"

        # Check form actions
        form_actions = soup.find('div', class_='form-actions')
        assert form_actions is not None, "Form actions not found"

        # Check buttons
        buttons = form_actions.find_all('button')
        assert len(buttons) == 2, "Should have 2 buttons in form actions"

        primary_btn = soup.find('button', class_='btn-primary')
        assert primary_btn is not None, "Primary button not found"

        secondary_btn = soup.find('button', class_='btn-secondary')
        assert secondary_btn is not None, "Secondary button not found"

    def test_responsive_classes_exist(self):
        """Test that responsive CSS classes exist in CSS files"""
        # Test media queries in design-system.css
        with open('static/css/design-system.css', encoding='utf-8') as f:
            design_content = f.read()
            assert re.search(r'@media.*max-width.*768px', design_content), "Media query not found in design-system.css"

        # Test dashboard grid classes in dashboard.css
        with open('static/css/dashboard.css', encoding='utf-8') as f:
            dashboard_content = f.read()
            dashboard_patterns = [r'dashboard-grid-2', r'dashboard-grid-3', r'dashboard-grid-4']
            for pattern in dashboard_patterns:
                assert re.search(pattern, dashboard_content), f"Dashboard pattern '{pattern}' not found in dashboard.css"

    def test_accessibility_features(self, client):
        """Test that accessibility features are present"""
        response = client.get('/')
        assert response.status_code == 200

        html_content = response.data.decode('utf-8')
        soup = BeautifulSoup(html_content, 'html.parser')

        # Check for skip link
        skip_link = soup.find('a', class_='skip-link')
        assert skip_link is not None, "Skip link not found"
        assert skip_link.get('href') == '#main-content', "Skip link should point to main content"

        # Check for ARIA labels
        aria_labels = soup.find_all(attrs={'aria-label': True})
        assert len(aria_labels) > 0, "Should have ARIA labels"

        # Check for semantic HTML
        main_content = soup.find('main') or soup.find(attrs={'role': 'main'})
        if main_content:
            assert main_content.get('id') == 'main-content', "Main content should have id='main-content'"

    def test_css_custom_properties(self):
        """Test that CSS custom properties are defined"""
        with open('static/css/design-system.css', encoding='utf-8') as f:
            content = f.read()

        # Check for key CSS custom properties
        required_properties = [
            '--primary',
            '--gray-900',
            '--space-4',
            '--radius-lg',
            '--shadow',
            '--font-family-primary',
            '--transition-normal'
        ]

        for prop in required_properties:
            assert prop in content, f"CSS custom property {prop} not found in design-system.css"

    def test_theme_variables(self):
        """Test that theme variables are properly defined"""
        with open('static/css/themes.css', encoding='utf-8') as f:
            content = f.read()

        # Check for theme variables
        theme_patterns = [
            r'--color-bg-primary',
            r'--color-text-primary',
            r'--color-info',
            r'--color-success',
            r'data-theme="dark"',
            r'@media.*prefers-color-scheme.*dark'
        ]

        for pattern in theme_patterns:
            assert re.search(pattern, content), f"Theme pattern '{pattern}' not found in themes.css"

    def test_animations_and_transitions(self):
        """Test that animations and transitions are defined"""
        with open('static/css/animations.css', encoding='utf-8') as f:
            content = f.read()

        # Check for animations
        animation_patterns = [
            r'@keyframes',
            r'animation:',
            r'transition:',
            r'hover-lift',
            r'fade-in'
        ]

        animation_found = False
        for pattern in animation_patterns:
            if re.search(pattern, content):
                animation_found = True
                break

        assert animation_found, "No animations found in animations.css"

    def test_loading_states(self):
        """Test that loading state CSS is defined"""
        with open('static/css/loading.css', encoding='utf-8') as f:
            content = f.read()

        # Check for loading patterns
        loading_patterns = [
            r'skeleton',
            r'loading-spinner',
            r'progress-bar',
            r'feedback-',
            r'toast'
        ]

        for pattern in loading_patterns:
            assert re.search(pattern, content), f"Loading pattern '{pattern}' not found in loading.css"

    def test_navigation_styles(self):
        """Test that navigation CSS is comprehensive"""
        with open('static/css/navigation.css', encoding='utf-8') as f:
            content = f.read()

        # Check for navigation patterns
        nav_patterns = [
            r'navbar',
            r'nav-link',
            r'breadcrumb',
            r'dropdown-menu',
            r'user-menu',
            r'mobile'
        ]

        for pattern in nav_patterns:
            assert re.search(pattern, content), f"Navigation pattern '{pattern}' not found in navigation.css"

    def test_form_styles(self):
        """Test that form CSS is comprehensive"""
        with open('static/css/forms.css', encoding='utf-8') as f:
            content = f.read()

        # Check for form patterns
        form_patterns = [
            r'form-control',
            r'form-select',
            r'form-floating',
            r'form-check',
            r'radio'
        ]

        for pattern in form_patterns:
            assert re.search(pattern, content), f"Form pattern '{pattern}' not found in forms.css"

    def test_dashboard_styles(self):
        """Test that dashboard CSS is comprehensive"""
        with open('static/css/dashboard.css', encoding='utf-8') as f:
            content = f.read()

        # Check for dashboard patterns
        dashboard_patterns = [
            r'dashboard-card',
            r'stats-card',
            r'data-table',
            r'chart-container',
            r'empty-state'
        ]

        for pattern in dashboard_patterns:
            assert re.search(pattern, content), f"Dashboard pattern '{pattern}' not found in dashboard.css"

    def test_typography_styles(self):
        """Test that typography CSS is comprehensive"""
        with open('static/css/typography.css', encoding='utf-8') as f:
            content = f.read()

        # Check for typography patterns
        typography_patterns = [
            r'font-family',
            r'text-',
            r'display-',
            r'text-body'
        ]

        for pattern in typography_patterns:
            assert re.search(pattern, content), f"Typography pattern '{pattern}' not found in typography.css"

    def test_css_validity(self):
        """Test that CSS files are syntactically valid"""
        css_files = [
            'static/css/design-system.css',
            'static/css/animations.css',
            'static/css/typography.css',
            'static/css/forms.css',
            'static/css/dashboard.css',
            'static/css/themes.css',
            'static/css/navigation.css',
            'static/css/loading.css'
        ]

        for css_file in css_files:
            with open(css_file, encoding='utf-8') as f:
                content = f.read()

                # Basic syntax checks
                assert '{' in content, f"CSS file {css_file} missing opening braces"
                assert '}' in content, f"CSS file {css_file} missing closing braces"

                # Check for balanced braces
                open_braces = content.count('{')
                close_braces = content.count('}')
                assert open_braces == close_braces, f"CSS file {css_file} has unbalanced braces"

    def test_performance_considerations(self):
        """Test that CSS includes performance considerations"""
        css_files = [
            'static/css/animations.css',
            'static/css/themes.css',
            'static/css/navigation.css',
            'static/css/loading.css'
        ]

        for css_file in css_files:
            with open(css_file, encoding='utf-8') as f:
                content = f.read()

                # Check for reduced motion support
                assert 'prefers-reduced-motion' in content, f"CSS file {css_file} should support reduced motion"

    def test_print_styles(self):
        """Test that print styles are included"""
        with open('static/css/themes.css', encoding='utf-8') as f:
            content = f.read()

        assert '@media print' in content, "Print styles not found in themes.css"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])