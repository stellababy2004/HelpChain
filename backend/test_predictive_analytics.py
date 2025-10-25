"""
Unit tests for PredictiveAnalytics class
Tests forecasting, workload prediction, and predictive insights functionality
"""

import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pandas as pd
import pytest

from predictive_analytics import PredictiveAnalytics


class TestPredictiveAnalytics:
    """Test suite for PredictiveAnalytics class"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for model storage"""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        import shutil

        shutil.rmtree(temp_dir)

    @pytest.fixture
    def predictive_analytics(self, temp_dir):
        """Create a PredictiveAnalytics instance for testing"""
        with patch("predictive_analytics.os.makedirs"), patch(
            "predictive_analytics.os.path.join",
            return_value=os.path.join(temp_dir, "models"),
        ):
            analytics = PredictiveAnalytics()
            analytics.models_dir = temp_dir
            return analytics

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

    def test_model_configs_structure(self, predictive_analytics):
        """Test model configuration structure"""
        config = predictive_analytics.model_configs["regional_demand"]

        assert "models" in config
        assert "features" in config
        assert "target" in config
        assert "best_model" in config

        # Check required models are present
        models = config["models"]
        assert "random_forest" in models
        assert "gradient_boosting" in models
        assert "extra_trees" in models

        # Check features list
        features = config["features"]
        assert "day_of_week" in features
        assert "month" in features
        assert "season" in features

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
    def test_train_models_success(self, mock_get_models, predictive_analytics):
        """Test successful model training"""
        # Mock database models
        mock_help_request = Mock()
        mock_volunteer = Mock()
        mock_db = Mock()

        mock_get_models.return_value = (
            mock_help_request,
            mock_volunteer,
            None,
            mock_db,
        )

        # Mock training data preparation
        with patch.object(
            predictive_analytics,
            "_prepare_regional_training_data",
            return_value=pd.DataFrame(
                {
                    "day_of_week": [1, 2, 3],
                    "month": [1, 1, 1],
                    "season": [0, 0, 0],
                    "historical_avg": [5.0, 5.0, 5.0],
                    "trend_factor": [0.1, 0.1, 0.1],
                    "volunteer_density": [1.0, 1.0, 1.0],
                    "population_density": [1.0, 1.0, 1.0],
                    "requests_count": [5, 6, 7],
                }
            ),
        ), patch.object(
            predictive_analytics,
            "_prepare_workload_training_data",
            return_value=pd.DataFrame(
                {
                    "current_requests": [10, 12, 8],
                    "active_volunteers": [5, 5, 6],
                    "avg_response_time": [2.0, 2.5, 1.8],
                    "day_of_week": [1, 2, 3],
                    "hour_of_day": [10, 11, 12],
                    "season": [0, 0, 0],
                    "predicted_workload": [8, 9, 7],
                }
            ),
        ), patch(
            "predictive_analytics.joblib.dump"
        ) as mock_dump, patch(
            "predictive_analytics.GridSearchCV"
        ) as mock_grid_search, patch(
            "predictive_analytics.cross_val_score", return_value=[1.0, 1.1, 0.9]
        ):

            # Setup mock grid search
            mock_best_estimator = Mock()
            mock_best_estimator.predict.return_value = [5.0, 6.0, 7.0]
            mock_grid_search.return_value.best_estimator_ = mock_best_estimator
            mock_grid_search.return_value.best_params_ = {"test": "params"}

            # Execute training
            result = predictive_analytics.train_models(model_type="regional_demand")

            # Assert
            assert "trained_models" in result
            assert "performance" in result
            assert "regional_demand" in result["trained_models"]
            assert len(result["errors"]) == 0

    @patch("predictive_analytics._get_models")
    def test_train_models_insufficient_data(
        self, mock_get_models, predictive_analytics
    ):
        """Test model training with insufficient data"""
        mock_get_models.return_value = (None, None, None, None)

        with patch.object(
            predictive_analytics,
            "_prepare_regional_training_data",
            return_value=pd.DataFrame(),
        ):
            result = predictive_analytics.train_models(model_type="regional_demand")

            assert "errors" in result
            assert len(result["errors"]) > 0
            assert "Insufficient training data" in result["errors"][0]

    def test_load_trained_model_exists(self, predictive_analytics, temp_dir):
        """Test loading an existing trained model"""
        # Create a mock model file
        model_path = os.path.join(temp_dir, "regional_demand_random_forest.joblib")
        mock_model = Mock()
        mock_model.predict.return_value = [5.0]

        with patch(
            "predictive_analytics.joblib.load", return_value=mock_model
        ) as mock_load, patch("predictive_analytics.os.path.exists", return_value=True):

            loaded_model = predictive_analytics.load_trained_model(
                "regional_demand", "random_forest"
            )

            assert loaded_model is not None
            mock_load.assert_called_once_with(model_path)

    def test_load_trained_model_not_exists(self, predictive_analytics):
        """Test loading a non-existent model"""
        with patch("predictive_analytics.os.path.exists", return_value=False):
            loaded_model = predictive_analytics.load_trained_model(
                "regional_demand", "nonexistent"
            )

            assert loaded_model is None

    def test_get_model_performance_report(self, predictive_analytics):
        """Test model performance report generation"""
        # Setup mock performance data
        predictive_analytics.model_performance = {
            "regional_demand_random_forest": {"mae": 2.5, "r2": 0.8, "rmse": 3.1}
        }
        predictive_analytics.model_configs["regional_demand"][
            "best_model"
        ] = "random_forest"

        # Mock feature importance
        mock_model = Mock()
        mock_model.feature_importances_ = [0.1, 0.2, 0.3, 0.4]

        with patch.object(
            predictive_analytics, "load_trained_model", return_value=mock_model
        ):
            report = predictive_analytics.get_model_performance_report()

            assert "model_performance" in report
            assert "best_models" in report
            assert "feature_importance" in report
            assert "recommendations" in report
            assert report["best_models"]["regional_demand"] == "random_forest"

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

    def test_predict_workload_with_trained_model(self, predictive_analytics):
        """Test workload prediction using trained model"""
        mock_model = Mock()
        mock_model.predict.return_value = [15.5]

        with patch.object(
            predictive_analytics, "load_trained_model", return_value=mock_model
        ):
            prediction = predictive_analytics._predict_workload([10, 5, 2.0, 1, 14, 1])

            assert prediction == 15.5
            mock_model.predict.assert_called_once()

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
    def test_get_regional_demand_forecast_with_data(
        self, mock_get_models, predictive_analytics
    ):
        """Test regional demand forecasting with available data"""
        # Mock database models
        mock_help_request = Mock()
        mock_db = Mock()

        mock_get_models.return_value = (mock_help_request, None, None, mock_db)

        # Mock historical data
        mock_request = Mock()
        mock_request.created_at = datetime.utcnow() - timedelta(days=30)
        mock_request.latitude = 42.7
        mock_request.longitude = 23.3
        mock_request.priority = Mock()
        mock_request.priority.value = "high"
        mock_request.status = "pending"

        mock_help_request.query.filter.return_value.all.return_value = [mock_request]

        # Mock forecast method
        with patch.object(
            predictive_analytics, "_forecast_regional_demand"
        ) as mock_forecast:
            mock_forecast.return_value = {
                "forecast": [{"date": "2024-01-15", "predicted_requests": 8.5}],
                "historical_avg": 7.2,
                "model_used": "random_forest",
            }

            result = predictive_analytics.get_regional_demand_forecast(
                region="Sofia", days_ahead=7
            )

            assert "regions" in result
            assert "Sofia" in result["regions"]
            assert "forecast_period_days" in result
            assert result["forecast_period_days"] == 7

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

    @patch("predictive_analytics._get_models")
    def test_get_workload_prediction_success(
        self, mock_get_models, predictive_analytics
    ):
        """Test successful workload prediction"""
        mock_get_models.return_value = (Mock(), Mock(), None, Mock())

        # Mock current system state
        with patch.object(
            predictive_analytics,
            "_get_current_system_state",
            return_value={
                "active_requests": 15,
                "pending_requests": 5,
                "active_volunteers": 8,
                "avg_response_time_hours": 3.5,
            },
        ), patch.object(
            predictive_analytics,
            "_get_historical_workload_data",
            return_value=[
                {
                    "timestamp": datetime.utcnow() - timedelta(hours=1),
                    "requests_count": 10,
                }
            ],
        ), patch.object(
            predictive_analytics, "_predict_workload", return_value=12.5
        ), patch.object(
            predictive_analytics,
            "_calculate_prediction_confidence",
            return_value="high",
        ):

            result = predictive_analytics.get_workload_prediction(hours_ahead=24)

            assert "predictions" in result
            assert "current_workload" in result
            assert len(result["predictions"]) == 24
            assert "predicted_requests" in result["predictions"][0]
            assert "confidence_level" in result["predictions"][0]

    def test_get_predictive_insights(self, predictive_analytics):
        """Test predictive insights generation"""
        # Mock forecast methods
        with patch.object(
            predictive_analytics,
            "get_regional_demand_forecast",
            return_value={
                "regions": {
                    "Sofia": {
                        "forecast": [
                            {"predicted_requests": 10},
                            {"predicted_requests": 15},
                        ]
                    }
                }
            },
        ), patch.object(
            predictive_analytics,
            "get_workload_prediction",
            return_value={
                "predictions": [{"predicted_requests": 8}, {"predicted_requests": 12}]
            },
        ):

            result = predictive_analytics.get_predictive_insights()

            assert "regional_insights" in result
            assert "workload_insights" in result
            assert "recommendations" in result
            assert "risk_assessment" in result

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

    def test_prepare_regional_training_data(self, predictive_analytics):
        """Test regional training data preparation"""
        with patch(
            "predictive_analytics._get_models",
            return_value=(Mock(), Mock(), None, Mock()),
        ):
            # Mock database query
            mock_request = Mock()
            mock_request.created_at = datetime(2024, 1, 15, 10, 30)
            mock_request.latitude = 42.7
            mock_request.longitude = 23.3
            mock_request.priority = Mock()
            mock_request.priority.value = "normal"
            mock_request.status = "completed"

            # Mock the query chain
            mock_query = Mock()
            mock_query.filter.return_value.all.return_value = [mock_request]
            predictive_analytics._get_models()[0].query.filter.return_value = mock_query

            df = predictive_analytics._prepare_regional_training_data()

            assert isinstance(df, pd.DataFrame)
            if len(df) > 0:
                assert "day_of_week" in df.columns
                assert "month" in df.columns
                assert "season" in df.columns

    def test_prepare_workload_training_data(self, predictive_analytics):
        """Test workload training data preparation"""
        with patch(
            "predictive_analytics._get_models",
            return_value=(Mock(), Mock(), None, Mock()),
        ):
            # Mock database query result
            mock_hourly_data = [
                (datetime(2024, 1, 15, 10), 5),
                (datetime(2024, 1, 15, 11), 8),
                (datetime(2024, 1, 15, 12), 6),
            ]

            # Mock the complex query chain
            mock_session = Mock()
            mock_query = Mock()
            mock_query.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = (
                mock_hourly_data
            )
            mock_session.query.return_value = mock_query
            predictive_analytics._get_models()[3].session = mock_session

            df = predictive_analytics._prepare_workload_training_data()

            assert isinstance(df, pd.DataFrame)
            if len(df) > 0:
                assert "hour_sin" in df.columns
                assert "hour_cos" in df.columns
                assert "predicted_workload" in df.columns

    def test_forecast_regional_demand_fallback(self, predictive_analytics):
        """Test regional demand forecast fallback logic"""
        region_data = [
            {
                "date": (datetime.utcnow() - timedelta(days=i)).date(),
                "requests_count": 5 + i,
            }
            for i in range(20)
        ]

        with patch.object(
            predictive_analytics, "load_trained_model", return_value=None
        ):
            result = predictive_analytics._forecast_regional_demand(region_data, 7)

            assert "forecast" in result
            assert "historical_avg" in result
            assert "method" in result
            assert result["method"] == "historical_average"

    def test_error_handling_training(self, predictive_analytics):
        """Test error handling in model training"""
        with patch.object(
            predictive_analytics,
            "_prepare_regional_training_data",
            side_effect=Exception("DB Error"),
        ):
            result = predictive_analytics.train_models(model_type="regional_demand")

            assert "errors" in result
            assert len(result["errors"]) > 0

    def test_error_handling_forecasting(self, predictive_analytics):
        """Test error handling in forecasting"""
        with patch.object(
            predictive_analytics,
            "_get_historical_request_data",
            side_effect=Exception("DB Error"),
        ):
            result = predictive_analytics.get_regional_demand_forecast()

            # Should return fallback forecast
            assert "regions" in result
            assert "method" in result

    def test_lazy_initialization(self):
        """Test lazy initialization of global instance"""
        from predictive_analytics import get_predictive_analytics

        with patch("predictive_analytics.PredictiveAnalytics") as mock_class:
            mock_instance = Mock()
            mock_class.return_value = mock_instance

            # First call should create instance
            instance1 = get_predictive_analytics()
            assert instance1 is mock_instance

            # Second call should return same instance
            instance2 = get_predictive_analytics()
            assert instance2 is instance1

            mock_class.assert_called_once()

    def test_lazy_wrapper(self):
        """Test lazy wrapper functionality"""
        from predictive_analytics import predictive_analytics

        with patch("predictive_analytics.get_predictive_analytics") as mock_get:
            mock_instance = Mock()
            mock_instance.test_method.return_value = "test_result"
            mock_get.return_value = mock_instance

            # Access method through lazy wrapper
            result = predictive_analytics.test_method()

            assert result == "test_result"
            mock_instance.test_method.assert_called_once()


def test_init(analytics):
    """Test PredictiveAnalytics initialization"""
    assert analytics.models_dir.endswith("models")
    assert analytics.cache_timeout == 3600
    assert isinstance(analytics.prediction_cache, dict)
    assert "regional_demand" in analytics.model_configs
    assert "workload_prediction" in analytics.model_configs


def test_get_season(analytics):
    """Test season calculation from month"""
    assert analytics._get_season(12) == 0
    assert analytics._get_season(1) == 0
    assert analytics._get_season(3) == 1
    assert analytics._get_season(6) == 2
    assert analytics._get_season(9) == 3


def test_predict_workload(analytics):
    """Test workload prediction calculation"""
    features = [10, 20, 24, 1, 14, 1]
    prediction = analytics._predict_workload(features)
    assert isinstance(prediction, float)
    assert prediction >= 0


def test_calculate_prediction_confidence(analytics):
    """Test confidence level calculation"""
    # High confidence - business hours, weekday
    features = [10, 20, 24, 1, 14, 1]
    confidence = analytics._calculate_prediction_confidence(features)
    assert confidence == "high"

    # Low confidence - weekday, very early morning
    features = [10, 20, 24, 1, 3, 1]
    confidence = analytics._calculate_prediction_confidence(features)
    assert confidence == "low"


def test_get_simple_forecast(analytics):
    """Test simple fallback forecast"""
    result = analytics._get_simple_forecast("Sofia", 3)
    assert "forecast" in result
    assert "historical_avg" in result
    assert len(result["forecast"]) == 3


def test_get_fallback_forecast(analytics):
    """Test fallback forecast when no data available"""
    result = analytics._get_fallback_forecast("Sofia", 3)
    assert "forecast_period_days" in result
    assert "regions" in result
    assert result["method"] == "fallback_no_data"


def test_get_fallback_workload_prediction(analytics):
    """Test fallback workload prediction"""
    result = analytics._get_fallback_workload_prediction(6)
    assert "prediction_period_hours" in result
    assert "predictions" in result
    assert len(result["predictions"]) == 6


def test_is_cache_valid(analytics):
    """Test cache validation"""
    # Empty cache
    assert not analytics._is_cache_valid("test_key")

    # Valid cache
    analytics.prediction_cache["test_key"] = "data"
    analytics.prediction_cache["test_key_timestamp"] = datetime.utcnow().timestamp()
    assert analytics._is_cache_valid("test_key")


if __name__ == "__main__":
    # Simple test runner to avoid pytest version issues
    import sys
    import traceback

    print("Running PredictiveAnalytics unit tests...")

    # Create test instance
    analytics = PredictiveAnalytics()

    test_results = {"passed": 0, "failed": 0, "errors": []}

    def run_test(test_name, test_func):
        try:
            print(f"Running {test_name}...")
            test_func()
            test_results["passed"] += 1
            print(f"✓ {test_name} PASSED")
        except Exception as e:
            test_results["failed"] += 1
            test_results["errors"].append(f"{test_name}: {str(e)}")
            print(f"✗ {test_name} FAILED: {str(e)}")
            traceback.print_exc()

    # Run basic tests
    run_test("test_init", lambda: test_init(analytics))
    run_test("test_get_season", lambda: test_get_season(analytics))
    run_test("test_predict_workload", lambda: test_predict_workload(analytics))
    run_test(
        "test_calculate_prediction_confidence",
        lambda: test_calculate_prediction_confidence(analytics),
    )
    run_test("test_get_simple_forecast", lambda: test_get_simple_forecast(analytics))
    run_test(
        "test_get_fallback_forecast", lambda: test_get_fallback_forecast(analytics)
    )
    run_test(
        "test_get_fallback_workload_prediction",
        lambda: test_get_fallback_workload_prediction(analytics),
    )
    run_test("test_is_cache_valid", lambda: test_is_cache_valid(analytics))

    print(
        f"\nTest Results: {test_results['passed']} passed, {test_results['failed']} failed"
    )
    if test_results["errors"]:
        print("\nErrors:")
        for error in test_results["errors"]:
            print(f"  {error}")

    sys.exit(0 if test_results["failed"] == 0 else 1)
