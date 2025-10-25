"""
Mobile Responsive Tests for HelpChain
Uses pytest framework for automated mobile testing
"""

import time

import pytest
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class TestMobileResponsiveness:
    """Test class for mobile responsive functionality"""

    @pytest.fixture(scope="class")
    def driver(self):
        """Setup Chrome driver for testing"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=chrome_options)
        yield driver
        driver.quit()

    @pytest.fixture(scope="class")
    def base_url(self):
        """Base URL for the application"""
        return "http://127.0.0.1:5000"

    def set_viewport(self, driver, width, height):
        """Set viewport size for testing"""
        driver.set_window_size(width, height)
        time.sleep(0.5)  # Allow time for responsive changes

    def test_mobile_navigation_iphone_se(self, driver, base_url):
        """Test mobile navigation on iPhone SE size"""
        self.set_viewport(driver, 375, 667)
        driver.get(base_url)

        # Check if mobile navigation is present
        mobile_nav = driver.find_elements(
            By.CSS_SELECTOR, ".navbar-toggler, .mobile-menu-toggle, .hamburger"
        )
        assert (
            len(mobile_nav) > 0
        ), "Mobile navigation should be visible on small screens"

    def test_mobile_navigation_ipad(self, driver, base_url):
        """Test navigation on iPad size"""
        self.set_viewport(driver, 768, 1024)
        driver.get(base_url)

        # On tablet size, navigation might be expanded
        navbar_collapse = driver.find_elements(By.CSS_SELECTOR, ".navbar-collapse")
        if navbar_collapse:
            # Check if navbar is expanded on tablet
            is_expanded = driver.execute_script(
                """
                var navbar = document.querySelector('.navbar-collapse');
                return navbar && window.getComputedStyle(navbar).display !== 'none';
            """
            )
            assert is_expanded, "Navigation should be expanded on tablet size"

    def test_no_horizontal_scroll_mobile(self, driver, base_url):
        """Test that pages don't have horizontal scroll on mobile"""
        mobile_devices = [
            (375, 667),  # iPhone SE
            (390, 844),  # iPhone 12
            (412, 915),  # Galaxy S20
        ]

        for width, height in mobile_devices:
            self.set_viewport(driver, width, height)
            driver.get(base_url)

            # Check for horizontal scroll
            scroll_width = driver.execute_script(
                """
                return Math.max(
                    document.body.scrollWidth,
                    document.body.offsetWidth,
                    document.documentElement.clientWidth,
                    document.documentElement.scrollWidth,
                    document.documentElement.offsetWidth
                );
            """
            )

            viewport_width = driver.execute_script("return window.innerWidth;")
            assert (
                scroll_width <= viewport_width + 10
            ), f"Horizontal scroll detected on {width}x{height} device"

    def test_touch_targets_mobile(self, driver, base_url):
        """Test that interactive elements meet touch target requirements"""
        self.set_viewport(driver, 375, 667)  # iPhone SE
        driver.get(base_url)

        # Find interactive elements
        interactive_selectors = [
            "button",
            "a",
            ".btn",
            "input[type='submit']",
            "input[type='button']",
        ]

        min_touch_size = 44  # WCAG minimum

        for selector in interactive_selectors:
            elements = driver.find_elements(By.CSS_SELECTOR, selector)

            for element in elements:
                rect = element.rect
                width = rect["width"]
                height = rect["height"]

                # Check if element meets minimum size or has adequate padding
                if width >= min_touch_size and height >= min_touch_size:
                    continue  # Element is large enough

                # Check padding
                computed_style = driver.execute_script(
                    """
                    var elem = arguments[0];
                    var style = window.getComputedStyle(elem);
                    return {
                        paddingTop: parseFloat(style.paddingTop) || 0,
                        paddingBottom: parseFloat(style.paddingBottom) || 0,
                        paddingLeft: parseFloat(style.paddingLeft) || 0,
                        paddingRight: parseFloat(style.paddingRight) || 0
                    };
                """,
                    element,
                )

                effective_width = (
                    width
                    + computed_style["paddingLeft"]
                    + computed_style["paddingRight"]
                )
                effective_height = (
                    height
                    + computed_style["paddingTop"]
                    + computed_style["paddingBottom"]
                )

                assert (
                    effective_width >= min_touch_size
                    and effective_height >= min_touch_size
                ), f"Touch target too small: {width}x{height} (effective: {effective_width}x{effective_height})"

    def test_text_readability_mobile(self, driver, base_url):
        """Test that text is readable on mobile devices"""
        self.set_viewport(driver, 375, 667)  # iPhone SE
        driver.get(base_url)

        # Check font sizes on text elements
        text_elements = driver.find_elements(
            By.CSS_SELECTOR, "p, h1, h2, h3, h4, h5, h6, span, div"
        )
        min_font_size = 14  # Minimum readable size

        small_text_found = False
        for element in text_elements[:20]:  # Check first 20 text elements
            if not element.text.strip():
                continue

            try:
                font_size = driver.execute_script(
                    """
                    var elem = arguments[0];
                    return parseFloat(window.getComputedStyle(elem).fontSize);
                """,
                    element,
                )

                if font_size < min_font_size:
                    small_text_found = True
                    break
            except:
                continue

        assert not small_text_found, "Some text may be too small to read on mobile"

    def test_images_responsive(self, driver, base_url):
        """Test that images are responsive"""
        self.set_viewport(driver, 375, 667)  # iPhone SE
        driver.get(base_url)

        images = driver.find_elements(By.TAG_NAME, "img")

        for img in images:
            # Check if image has responsive classes or styles
            classes = img.get_attribute("class") or ""
            style = img.get_attribute("style") or ""

            has_responsive_class = any(
                cls in classes for cls in ["img-fluid", "responsive-img"]
            )
            has_max_width = "max-width" in style or "width: 100%" in style

            if not (has_responsive_class or has_max_width):
                # Check computed style
                max_width = driver.execute_script(
                    """
                    var img = arguments[0];
                    return window.getComputedStyle(img).maxWidth;
                """,
                    img,
                )

                assert max_width in [
                    "100%",
                    "none",
                ], f"Image not responsive: max-width={max_width}"

    def test_admin_dashboard_mobile(self, driver, base_url):
        """Test admin dashboard responsiveness"""
        self.set_viewport(driver, 375, 667)  # iPhone SE
        driver.get(f"{base_url}/admin_login")

        # Check if login form is usable on mobile
        form = driver.find_elements(By.TAG_NAME, "form")
        assert len(form) > 0, "Login form should be present"

        # Check form inputs are accessible
        inputs = driver.find_elements(By.CSS_SELECTOR, "input")
        assert len(inputs) > 0, "Form inputs should be present and accessible"

    def test_viewport_meta_tag(self, driver, base_url):
        """Test that viewport meta tag is present"""
        driver.get(base_url)

        viewport_meta = driver.find_elements(By.CSS_SELECTOR, "meta[name='viewport']")
        assert len(viewport_meta) > 0, "Viewport meta tag should be present"

        content = viewport_meta[0].get_attribute("content")
        assert "width=device-width" in content, "Viewport should be set to device-width"
        assert "initial-scale=1" in content, "Initial scale should be set to 1"

    @pytest.mark.parametrize(
        "device_name,width,height",
        [
            ("iPhone_SE", 375, 667),
            ("iPhone_12", 390, 844),
            ("iPad", 768, 1024),
            ("Desktop", 1280, 720),
        ],
    )
    def test_page_loads_across_devices(
        self, driver, base_url, device_name, width, height
    ):
        """Test that pages load correctly across different device sizes"""
        self.set_viewport(driver, width, height)

        test_pages = ["/", "/admin_login"]

        for page in test_pages:
            driver.get(f"{base_url}{page}")

            # Wait for page to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            # Check that page has content
            body_text = driver.find_element(By.TAG_NAME, "body").text
            assert (
                len(body_text) > 0
            ), f"Page {page} should have content on {device_name}"

            # Check that no console errors occurred (basic check)
            logs = driver.get_log("browser")
            errors = [log for log in logs if log["level"] == "SEVERE"]
            assert (
                len(errors) == 0
            ), f"JavaScript errors found on {page} for {device_name}: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
