import unittest

from src.app import app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_home_page(self):
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)

    def test_api_endpoint(self):
        response = self.app.get("/api/some_endpoint")
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json, dict)


if __name__ == "__main__":
    unittest.main()
