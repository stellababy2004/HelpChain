"""
Load testing scenarios for HelpChain application using Locust.

This file defines realistic user behavior patterns for different user types:
- Volunteer users: Browse tasks, update availability, view dashboard
- Admin users: Monitor analytics, manage volunteers, view reports
- Mixed users: Combination of volunteer and admin behaviors

Usage:
    locust -f locustfile.py --host=http://localhost:5000
    # Then open http://localhost:8089 to access the web interface
"""

import json
import random
import time

from locust import HttpUser, between, events, tag, task
from locust.env import Environment
from locust.stats import print_stats


class VolunteerUser(HttpUser):
    """Simulates volunteer user behavior"""

    wait_time = between(1, 3)  # Realistic think time between actions

    def on_start(self):
        """Login as volunteer on test start"""
        # Simulate login - in real scenario, you'd get a valid token
        self.token = "test_volunteer_token"
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(3)  # Higher weight - most common action
    def view_dashboard(self):
        """View volunteer dashboard"""
        with self.client.get(
            "/api/volunteer/dashboard", headers=self.headers, catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                # Token expired, re-authenticate
                self._refresh_token()
            else:
                response.failure(f"Dashboard failed: {response.status_code}")

    @task(2)
    def browse_tasks(self):
        """Browse available tasks"""
        with self.client.get(
            "/api/volunteer/tasks", headers=self.headers, catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Tasks failed: {response.status_code}")

    @task(1)
    def update_profile(self):
        """Update volunteer profile"""
        profile_data = {
            "skills": ["medical", "transport", "support"][: random.randint(1, 3)],
            "availability": random.choice(["available", "busy", "offline"]),
            "location": f"Test Location {random.randint(1, 100)}",
        }

        with self.client.put(
            "/api/user/profile",
            json=profile_data,
            headers=self.headers,
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Profile update failed: {response.status_code}")

    @task(1)
    def check_notifications(self):
        """Check for new notifications"""
        with self.client.get(
            "/api/notifications", headers=self.headers, catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Notifications failed: {response.status_code}")

    def _refresh_token(self):
        """Simulate token refresh"""
        # In real scenario, this would make an actual refresh request
        self.token = f"refreshed_token_{random.randint(1000, 9999)}"
        self.headers = {"Authorization": f"Bearer {self.token}"}


class AdminUser(HttpUser):
    """Simulates admin user behavior"""

    wait_time = between(2, 5)  # Admins think longer between actions

    def on_start(self):
        """Login as admin on test start"""
        self.token = "test_admin_token"
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(4)  # Most common admin action
    def view_admin_dashboard(self):
        """View admin dashboard with analytics"""
        with self.client.get(
            "/api/admin/dashboard", headers=self.headers, catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 401:
                self._refresh_token()
            else:
                response.failure(f"Admin dashboard failed: {response.status_code}")

    @task(2)
    def view_analytics(self):
        """View detailed analytics"""
        with self.client.get(
            "/api/analytics/dashboard", headers=self.headers, catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Analytics failed: {response.status_code}")

    @task(1)
    def manage_volunteers(self):
        """View volunteer management interface"""
        with self.client.get(
            "/api/admin/volunteers", headers=self.headers, catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Volunteer management failed: {response.status_code}")

    @task(1)
    def check_system_status(self):
        """Check system health and AI status"""
        with self.client.get(
            "/api/ai/status", headers=self.headers, catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"System status failed: {response.status_code}")

    def _refresh_token(self):
        """Simulate admin token refresh"""
        self.token = f"admin_refreshed_token_{random.randint(1000, 9999)}"
        self.headers = {"Authorization": f"Bearer {self.token}"}


class MixedUser(HttpUser):
    """Simulates mixed user behavior (volunteer + admin)"""

    wait_time = between(1, 4)

    def on_start(self):
        """Login with mixed permissions"""
        self.token = "test_mixed_token"
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.user_type = random.choice(["volunteer", "admin"])

    @task(2)
    def dashboard_access(self):
        """Access appropriate dashboard based on user type"""
        if self.user_type == "volunteer":
            endpoint = "/api/volunteer/dashboard"
        else:
            endpoint = "/api/admin/dashboard"

        with self.client.get(
            endpoint, headers=self.headers, catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Dashboard access failed: {response.status_code}")

    @task(1)
    def general_browsing(self):
        """General browsing behavior"""
        endpoints = ["/api/user/profile", "/api/notifications", "/api/ai/status"]

        endpoint = random.choice(endpoints)
        with self.client.get(
            endpoint, headers=self.headers, catch_response=True
        ) as response:
            if response.status_code in [200, 404]:
                response.success()
            else:
                response.failure(f"Browsing failed: {response.status_code}")


class PublicUser(HttpUser):
    """Simulates public/unauthenticated user behavior"""

    wait_time = between(3, 8)  # Public users browse more slowly

    @task(5)
    def view_homepage(self):
        """View public homepage"""
        with self.client.get("/", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Homepage failed: {response.status_code}")

    @task(2)
    def view_static_assets(self):
        """Load static assets"""
        assets = [
            "/static/styles.css",
            "/static/bootstrap.min.css",
            "/static/jquery.min.js",
        ]

        asset = random.choice(assets)
        with self.client.get(asset, catch_response=True) as response:
            if response.status_code in [
                200,
                404,
            ]:  # 404 is acceptable for missing assets
                response.success()
            else:
                response.failure(f"Static asset failed: {response.status_code}")

    @task(1)
    def test_error_pages(self):
        """Test error handling"""
        error_endpoints = ["/nonexistent", "/api/invalid", "/admin/unauthorized"]

        endpoint = random.choice(error_endpoints)
        with self.client.get(endpoint, catch_response=True) as response:
            if response.status_code in [404, 401, 403]:  # Expected error codes
                response.success()
            else:
                response.failure(f"Unexpected error response: {response.status_code}")


# Custom event handlers for monitoring
@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs):
    """Called when a load test starts"""
    print("🚀 Starting HelpChain load test...")
    print(f"Target host: {environment.host}")
    print(f"Expected users: {environment.parsed_options.num_users}")
    print(f"Spawn rate: {environment.parsed_options.spawn_rate}")


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **kwargs):
    """Called when a load test stops"""
    print("\n✅ Load test completed!")
    print("📊 Final Statistics:")
    print_stats(environment.stats)


@events.request.add_listener
def on_request(
    request_type,
    name,
    response_time,
    response_length,
    response,
    context,
    exception,
    start_time,
    url,
    **kwargs,
):
    """Monitor individual requests"""
    if exception:
        print(f"❌ Request failed: {name} - {exception}")
    elif response and response.status_code >= 400:
        print(f"⚠️  Request error: {name} - Status: {response.status_code}")


# Configuration for different test scenarios
TEST_CONFIGS = {
    "light_load": {
        "users": 10,
        "spawn_rate": 2,
        "run_time": "1m",
        "description": "Light load test (10 users)",
    },
    "medium_load": {
        "users": 50,
        "spawn_rate": 5,
        "run_time": "2m",
        "description": "Medium load test (50 users)",
    },
    "heavy_load": {
        "users": 100,
        "spawn_rate": 10,
        "run_time": "3m",
        "description": "Heavy load test (100 users)",
    },
    "stress_test": {
        "users": 200,
        "spawn_rate": 20,
        "run_time": "5m",
        "description": "Stress test (200 users)",
    },
}


def run_scenario(scenario_name: str):
    """Run a specific test scenario"""
    if scenario_name not in TEST_CONFIGS:
        print(f"❌ Unknown scenario: {scenario_name}")
        print(f"Available scenarios: {list(TEST_CONFIGS.keys())}")
        return

    config = TEST_CONFIGS[scenario_name]
    print(f"🎯 Running scenario: {scenario_name}")
    print(f"📝 Description: {config['description']}")

    # Import here to avoid circular imports
    from locust import run_single_user
    from locust.env import Environment
    from locust.stats import print_stats

    # Create environment with mixed user types
    env = Environment(
        user_classes=[VolunteerUser, AdminUser, MixedUser, PublicUser],
        host="http://localhost:5000",
    )

    # Configure test parameters
    env.parsed_options = type(
        "Options",
        (),
        {
            "num_users": config["users"],
            "spawn_rate": config["spawn_rate"],
            "run_time": config["run_time"],
        },
    )()

    # Run the test
    env.create_local_runner()
    env.runner.start(
        env.parsed_options.num_users, spawn_rate=env.parsed_options.spawn_rate
    )

    # Wait for specified time
    time.sleep(parse_time(config["run_time"]))

    # Stop the test
    env.runner.stop()

    # Print results
    print_stats(env.stats)


def parse_time(time_str: str) -> int:
    """Parse time string like '1m', '30s', '2h' to seconds"""
    if time_str.endswith("s"):
        return int(time_str[:-1])
    elif time_str.endswith("m"):
        return int(time_str[:-1]) * 60
    elif time_str.endswith("h"):
        return int(time_str[:-1]) * 3600
    else:
        return int(time_str)


if __name__ == "__main__":
    # Allow running scenarios from command line
    import sys

    if len(sys.argv) > 1:
        scenario = sys.argv[1]
        run_scenario(scenario)
    else:
        print("HelpChain Load Testing")
        print("======================")
        print("Available scenarios:")
        for name, config in TEST_CONFIGS.items():
            print(f"  {name}: {config['description']}")
        print("\nUsage: python locustfile.py <scenario_name>")
        print("Or run with: locust -f locustfile.py --host=http://localhost:5000")
