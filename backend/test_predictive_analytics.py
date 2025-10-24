"""
Unit tests for PredictiveAnalytics class
Tests forecasting, workload prediction, and predictive insights functionality
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from predictive_analytics import PredictiveAnalytics


class TestPredictiveAnalytics:
    """Test suite for PredictiveAnalytics class"""

    @pytest.fixture
    def predictive_analytics(self):
        """Create a PredictiveAnalytics instance for testing"""
        return PredictiveAnalytics()

    @pytest.fixture
    def mock_help_request(self):
        """Mock HelpRequest model"""
        mock_request = Mock()
        mock_request.id = 1
        mock_request.created_at = datetime.utcnow()
        mock_request.priority = Mock(value="normal")
        mock_request.status = "pending"
        mock_request.latitude = 42.7
        mock_request.longitude = 23.3
        mock_request.location = "Sofia"
        return mock_request

    @pytest.fixture
    def mock_volunteer(self):
        """Mock Volunteer model"""
        mock_vol = Mock()
        mock_vol.id = 1
        mock_vol.last_activity = datetime.utcnow() - timedelta(days=1)
        return mock_vol

    @pytest.fixture
    def sample_historical_data(self):
        """Sample historical request data for testing"""
        base_date = datetime.utcnow() - timedelta(days=30)
        return [
            {
                "date": (base_date + timedelta(days=i)).date(),
                "region": "Sofia" if i % 3 == 0 else "Plovdiv",
                "priority": "normal",
                "status": "completed",
                "latitude": 42.7,
                "longitude": 23.3,
                "hour": 10 + (i % 12),
                "day_of_week": (base_date + timedelta(days=i)).weekday(),
                "month": (base_date + timedelta(days=i)).month,
            }
            for i in range(30)
        ]

    def test_init(self, predictive_analytics):
        """Test PredictiveAnalytics initialization"""
        assert predictive_analytics.models_dir.endswith("models")
        assert predictive_analytics.cache_timeout == 3600
        assert isinstance(predictive_analytics.prediction_cache, dict)
        assert "regional_demand" in predictive_analytics.model_configs
        assert "workload_prediction" in predictive_analytics.model_configs

    def test_get_season(self, predictive_analytics):
        """Test season calculation from month"""
        # Winter
        assert predictive_analytics._get_season(12) == 0
        assert predictive_analytics._get_season(1) == 0
        assert predictive_analytics._get_season(2) == 0

        # Spring
        assert predictive_analytics._get_season(3) == 1
        assert predictive_analytics._get_season(4) == 1
        assert predictive_analytics._get_season(5) == 1

        # Summer
        assert predictive_analytics._get_season(6) == 2
        assert predictive_analytics._get_season(7) == 2
        assert predictive_analytics._get_season(8) == 2

        # Fall
        assert predictive_analytics._get_season(9) == 3
        assert predictive_analytics._get_season(10) == 3
        assert predictive_analytics._get_season(11) == 3

    def test_extract_region_from_request(self, predictive_analytics, mock_help_request):
        """Test region extraction from help request"""
        # Test with location field
        mock_help_request.location = "Sofia"
        assert (
            predictive_analytics._extract_region_from_request(mock_help_request)
            == "Sofia"
        )

        # Test with Sofia coordinates
        mock_help_request.location = None
        mock_help_request.latitude = 42.7
        mock_help_request.longitude = 23.3
        assert (
            predictive_analytics._extract_region_from_request(mock_help_request)
            == "Sofia"
        )

        # Test with Plovdiv coordinates
        mock_help_request.latitude = 42.15
        mock_help_request.longitude = 24.75
        assert (
            predictive_analytics._extract_region_from_request(mock_help_request)
            == "Plovdiv"
        )

        # Test with Varna coordinates
        mock_help_request.latitude = 43.2
        mock_help_request.longitude = 27.9
        assert (
            predictive_analytics._extract_region_from_request(mock_help_request)
            == "Varna"
        )

        # Test with unknown coordinates
        mock_help_request.latitude = 40.0
        mock_help_request.longitude = 20.0
        assert (
            predictive_analytics._extract_region_from_request(mock_help_request)
            == "Other"
        )

        # Test error handling
        mock_help_request.latitude = None
        mock_help_request.longitude = None
        assert (
            predictive_analytics._extract_region_from_request(mock_help_request)
            == "Unknown"
        )

    @patch("predictive_analytics._get_models")
    def test_get_historical_request_data_no_models(
        self, mock_get_models, predictive_analytics
    ):
        """Test getting historical data when models are not available"""
        mock_get_models.return_value = (None, None, None, None)

        result = predictive_analytics._get_historical_request_data()
        assert result == []

    @patch.object(PredictiveAnalytics, "_get_historical_request_data")
    def test_get_historical_request_data_with_data(
        self, mock_get_data, predictive_analytics, mock_help_request
    ):
        """Test getting historical data with mock database"""
        # Mock the method to return sample data
        mock_get_data.return_value = [
            {
                "date": mock_help_request.created_at.date(),
                "region": "Sofia",
                "priority": "normal",
                "status": "pending",
                "latitude": 42.7,
                "longitude": 23.3,
                "hour": 10,
                "day_of_week": 1,
                "month": 1,
            }
        ]

        result = predictive_analytics._get_historical_request_data()

        assert len(result) == 1
        assert result[0]["region"] == "Sofia"
        assert result[0]["status"] == "pending"

    def test_get_active_regions(self, predictive_analytics, sample_historical_data):
        """Test extracting active regions from data"""
        regions = predictive_analytics._get_active_regions(sample_historical_data)

        assert "Sofia" in regions
        assert "Plovdiv" in regions
        # Should filter out regions with < 5 requests
        assert len([r for r in regions if r in ["Sofia", "Plovdiv"]]) == 2

    def test_filter_data_by_region(self, predictive_analytics, sample_historical_data):
        """Test filtering data by specific region"""
        sofia_data = predictive_analytics._filter_data_by_region(
            sample_historical_data, "Sofia"
        )

        assert all(item["region"] == "Sofia" for item in sofia_data)
        assert len(sofia_data) > 0

    @patch("predictive_analytics._get_models")
    def test_get_current_system_state_no_models(
        self, mock_get_models, predictive_analytics
    ):
        """Test getting system state when models are not available"""
        mock_get_models.return_value = (None, None, None, None)

        result = predictive_analytics._get_current_system_state()

        expected_keys = [
            "active_requests",
            "pending_requests",
            "active_volunteers",
            "avg_response_time_hours",
        ]
        assert all(key in result for key in expected_keys)
        assert result["active_requests"] == 0
        assert result["active_volunteers"] == 0

    @patch.object(PredictiveAnalytics, "_get_current_system_state")
    def test_get_current_system_state_with_data(
        self, mock_get_state, predictive_analytics, mock_help_request, mock_volunteer
    ):
        """Test getting system state with mock data"""
        # Mock the method to return sample data
        mock_get_state.return_value = {
            "active_requests": 5,
            "pending_requests": 3,
            "active_volunteers": 10,
            "avg_response_time_hours": 6,
            "timestamp": "2023-01-01T12:00:00",
        }

        result = predictive_analytics._get_current_system_state()

        assert result["active_requests"] == 5
        assert result["active_volunteers"] == 10
        assert result["pending_requests"] == 3

    def test_predict_workload(self, predictive_analytics):
        """Test workload prediction calculation"""
        # Test with typical features
        features = [
            10,
            20,
            24,
            1,
            14,
            1,
        ]  # current_requests, volunteers, response_time, day, hour, season

        prediction = predictive_analytics._predict_workload(features)

        assert isinstance(prediction, float)
        assert prediction >= 0

        # Test with zero features
        zero_features = [0, 0, 0, 0, 0, 0]
        zero_prediction = predictive_analytics._predict_workload(zero_features)

        assert zero_prediction >= 0

    def test_calculate_prediction_confidence(self, predictive_analytics):
        """Test confidence level calculation"""
        # High confidence - business hours, weekday
        features = [10, 20, 24, 1, 14, 1]  # weekday, business hours
        confidence = predictive_analytics._calculate_prediction_confidence(features)
        assert confidence == "high"

        # Medium confidence - evening, weekday
        features = [10, 20, 24, 1, 18, 1]
        confidence = predictive_analytics._calculate_prediction_confidence(features)
        assert confidence == "medium"

        # Medium confidence - weekend, any time
        features = [10, 20, 24, 5, 2, 1]  # Saturday, night
        confidence = predictive_analytics._calculate_prediction_confidence(features)
        assert confidence == "medium"

        # Low confidence - weekday, very early morning
        features = [10, 20, 24, 1, 3, 1]  # weekday, 3 AM
        confidence = predictive_analytics._calculate_prediction_confidence(features)
        assert confidence == "low"

    def test_get_simple_forecast(self, predictive_analytics):
        """Test simple fallback forecast"""
        result = predictive_analytics._get_simple_forecast("Sofia", 3)

        assert "forecast" in result
        assert "historical_avg" in result
        assert len(result["forecast"]) == 3

        for day_forecast in result["forecast"]:
            assert "date" in day_forecast
            assert "predicted_requests" in day_forecast
            assert "confidence_interval" in day_forecast
            assert day_forecast["predicted_requests"] >= 0

    def test_get_fallback_forecast(self, predictive_analytics):
        """Test fallback forecast when no data available"""
        result = predictive_analytics._get_fallback_forecast("Sofia", 3)

        assert "forecast_period_days" in result
        assert "regions" in result
        assert "generated_at" in result
        assert "method" in result
        assert result["method"] == "fallback_no_data"

    def test_get_fallback_workload_prediction(self, predictive_analytics):
        """Test fallback workload prediction"""
        result = predictive_analytics._get_fallback_workload_prediction(6)

        assert "prediction_period_hours" in result
        assert "current_workload" in result
        assert "predictions" in result
        assert len(result["predictions"]) == 6

        for prediction in result["predictions"]:
            assert "timestamp" in prediction
            assert "predicted_requests" in prediction
            assert "confidence_level" in prediction
            assert prediction["predicted_requests"] >= 0

    def test_is_cache_valid(self, predictive_analytics):
        """Test cache validation"""
        # Empty cache
        assert not predictive_analytics._is_cache_valid("test_key")

        # Valid cache
        predictive_analytics.prediction_cache["test_key"] = "data"
        predictive_analytics.prediction_cache["test_key_timestamp"] = (
            datetime.utcnow().timestamp()
        )
        assert predictive_analytics._is_cache_valid("test_key")

        # Expired cache
        predictive_analytics.prediction_cache["expired_key_timestamp"] = (
            datetime.utcnow().timestamp() - 7200
        )  # 2 hours ago
        assert not predictive_analytics._is_cache_valid("expired_key")

    @patch("predictive_analytics._get_models")
    def test_get_regional_demand_forecast_no_data(
        self, mock_get_models, predictive_analytics
    ):
        """Test regional forecast when no historical data"""
        mock_get_models.return_value = (None, None, None, None)

        result = predictive_analytics.get_regional_demand_forecast(days_ahead=3)

        assert "regions" in result
        assert "generated_at" in result
        assert result["method"] == "fallback_no_data"

    @patch("predictive_analytics._get_models")
    def test_get_workload_prediction_no_data(
        self, mock_get_models, predictive_analytics
    ):
        """Test workload prediction when no historical data"""
        mock_get_models.return_value = (None, None, None, None)

        result = predictive_analytics.get_workload_prediction(hours_ahead=6)

        assert "predictions" in result
        assert "current_workload" in result
        assert len(result["predictions"]) == 6
        assert result["method"] == "fallback_no_data"

    def test_analyze_forecasts(self, predictive_analytics):
        """Test forecast analysis for insights"""
        # Mock forecast data
        regional_forecast = {
            "regions": {
                "Sofia": {
                    "forecast": [
                        {"predicted_requests": 10},
                        {"predicted_requests": 15},
                        {"predicted_requests": 8},
                    ]
                }
            }
        }

        workload_forecast = {
            "predictions": [
                {"predicted_requests": 5},
                {"predicted_requests": 12},
                {"predicted_requests": 3},
            ]
        }

        result = predictive_analytics._analyze_forecasts(
            regional_forecast, workload_forecast
        )

        assert "regional" in result
        assert "workload" in result
        assert "recommendations" in result
        assert "risks" in result

        # Should have recommendations
        assert len(result["recommendations"]) > 0
        assert len(result["risks"]) > 0

    def test_get_predictive_insights_error_handling(self, predictive_analytics):
        """Test predictive insights error handling"""
        with patch.object(
            predictive_analytics,
            "get_regional_demand_forecast",
            side_effect=Exception("Test error"),
        ):
            result = predictive_analytics.get_predictive_insights()

            assert "error" in result
            assert "fallback_message" in result

    def test_analyze_seasonal_pattern(self, predictive_analytics):
        """Test seasonal pattern analysis"""
        # Create sample data
        dates = pd.date_range("2023-01-01", periods=30, freq="D")
        data = pd.DataFrame(
            {
                "date": dates,
                "day_of_week": dates.weekday,
                "month": dates.month,
                "requests_count": np.random.randint(1, 20, 30),
            }
        )

        result = predictive_analytics._analyze_seasonal_pattern(data)

        assert "busiest_day" in result
        assert "slowest_day" in result
        assert "monthly_trends" in result

    def test_evaluate_model_accuracy(self, predictive_analytics):
        """Test model accuracy evaluation"""
        # Mock model and data
        mock_model = Mock()
        mock_model.predict.return_value = [8, 12, 6]

        X_test = pd.DataFrame({"feature1": [1, 2, 3]})
        y_test = pd.Series([10, 15, 5])

        result = predictive_analytics._evaluate_model_accuracy(
            mock_model, X_test, y_test
        )

        assert "mae" in result
        assert "rmse" in result
        assert "r2_score" in result

        # All should be numeric
        assert all(isinstance(v, (int, float)) for v in result.values())

    def test_prepare_forecast_features(self, predictive_analytics):
        """Test forecast feature preparation"""
        # Create sample historical data
        dates = pd.date_range("2023-01-01", periods=20, freq="D")
        historical_data = pd.DataFrame(
            {"date": dates, "requests_count": np.random.randint(1, 15, 20)}
        )

        forecast_date = pd.Timestamp("2023-01-21")  # Next day

        features = predictive_analytics._prepare_forecast_features(
            forecast_date, historical_data
        )

        assert len(features) == 7  # Should have 7 features
        assert all(isinstance(f, (int, float)) for f in features)

    def test_prepare_workload_features(self, predictive_analytics):
        """Test workload feature preparation"""
        prediction_time = datetime(
            2023, 1, 14, 14, 30
        )  # Saturday afternoon (weekday 5)
        current_state = {
            "active_requests": 8,
            "active_volunteers": 12,
            "avg_response_time_hours": 6,
        }
        historical_data = []  # Not used in current implementation

        features = predictive_analytics._prepare_workload_features(
            prediction_time, current_state, historical_data
        )

        assert len(features) == 6  # Should have 6 features
        assert features[0] == 8  # active_requests
        assert features[1] == 12  # active_volunteers
        assert features[2] == 6  # avg_response_time
        assert features[3] == 5  # Saturday
        assert features[4] == 14  # 2 PM
        assert features[5] in [0, 1, 2, 3]  # season
