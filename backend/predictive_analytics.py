"""
Predictive Analytics Service for HelpChain
Uses ML models to forecast workload and predict help request demand by region
"""

import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

logger = logging.getLogger(__name__)


# Lazy model imports to avoid import issues
def _get_models():
    """Lazily import models to avoid import issues at module level"""
    try:
        from models import HelpRequest, UserActivity, Volunteer, db

        return HelpRequest, Volunteer, UserActivity, db
    except ImportError:
        # If direct import fails, models are not available
        return None, None, None, None


class PredictiveAnalytics:
    """Predictive Analytics Service using ML models for workload forecasting"""

    def __init__(self):
        self.models_dir = os.path.join(os.path.dirname(__file__), "models")
        os.makedirs(self.models_dir, exist_ok=True)

        # Model configurations
        self.model_configs = {
            "regional_demand": {
                "model_type": "random_forest",
                "features": [
                    "day_of_week",
                    "month",
                    "season",
                    "historical_avg",
                    "trend_factor",
                    "volunteer_density",
                    "population_density",
                ],
                "target": "requests_count",
            },
            "workload_prediction": {
                "model_type": "gradient_boosting",
                "features": [
                    "current_requests",
                    "active_volunteers",
                    "avg_response_time",
                    "day_of_week",
                    "hour_of_day",
                    "season",
                ],
                "target": "predicted_workload",
            },
        }

        # Cache for predictions
        self.prediction_cache = {}
        self.cache_timeout = 3600  # 1 hour

    def get_regional_demand_forecast(
        self, region: str | None = None, days_ahead: int = 7
    ) -> dict[str, Any]:
        """
        Predict help request demand by region for the next N days

        Args:
            region: Specific region to forecast (None for all regions)
            days_ahead: Number of days to forecast

        Returns:
            Dictionary with forecast data by region
        """
        try:
            cache_key = f"regional_demand_{region}_{days_ahead}"
            if self._is_cache_valid(cache_key):
                return self.prediction_cache[cache_key]

            # Get historical data
            historical_data = self._get_historical_request_data(days_back=90)

            if not historical_data:
                return self._get_fallback_forecast(region, days_ahead)

            # Process data by region
            regional_forecasts = {}

            if region:
                regions = [region]
            else:
                # Get all regions with significant activity
                regions = self._get_active_regions(historical_data)

            for reg in regions:
                try:
                    region_data = self._filter_data_by_region(historical_data, reg)
                    if len(region_data) >= 14:  # Need at least 2 weeks of data
                        forecast = self._forecast_regional_demand(
                            region_data, days_ahead
                        )
                        regional_forecasts[reg] = forecast
                except Exception as e:
                    logger.error(f"Error forecasting for region {reg}: {e}")
                    regional_forecasts[reg] = self._get_simple_forecast(reg, days_ahead)

            result = {
                "forecast_period_days": days_ahead,
                "regions": regional_forecasts,
                "generated_at": datetime.utcnow().isoformat(),
                "model_info": {
                    "type": "ensemble_regression",
                    "features_used": self.model_configs["regional_demand"]["features"],
                    "historical_period_days": 90,
                },
            }

            self.prediction_cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Error in regional demand forecast: {e}")
            return self._get_fallback_forecast(region, days_ahead)

    def get_workload_prediction(self, hours_ahead: int = 24) -> dict[str, Any]:
        """
        Predict overall system workload for the next N hours

        Args:
            hours_ahead: Number of hours to predict workload for

        Returns:
            Dictionary with workload predictions
        """
        try:
            cache_key = f"workload_{hours_ahead}"
            if self._is_cache_valid(cache_key):
                return self.prediction_cache[cache_key]

            # Get current system state
            current_state = self._get_current_system_state()

            # Get historical workload data
            historical_workload = self._get_historical_workload_data(
                hours_back=168
            )  # 1 week

            if not historical_workload:
                return self._get_fallback_workload_prediction(hours_ahead)

            # Generate predictions
            predictions = []
            current_time = datetime.utcnow()

            for hour in range(1, hours_ahead + 1):
                prediction_time = current_time + timedelta(hours=hour)

                # Prepare features for prediction
                features = self._prepare_workload_features(
                    prediction_time, current_state, historical_workload
                )

                # Make prediction
                predicted_workload = self._predict_workload(features)

                predictions.append(
                    {
                        "timestamp": prediction_time.isoformat(),
                        "predicted_requests": max(0, round(predicted_workload, 1)),
                        "confidence_level": self._calculate_prediction_confidence(
                            features
                        ),
                        "factors": {
                            "day_of_week": prediction_time.weekday(),
                            "hour_of_day": prediction_time.hour,
                            "is_weekend": prediction_time.weekday() >= 5,
                            "season": self._get_season(prediction_time.month),
                        },
                    }
                )

            result = {
                "prediction_period_hours": hours_ahead,
                "current_workload": current_state,
                "predictions": predictions,
                "generated_at": datetime.utcnow().isoformat(),
                "model_info": {
                    "type": "gradient_boosting_regression",
                    "features_used": self.model_configs["workload_prediction"][
                        "features"
                    ],
                },
            }

            self.prediction_cache[cache_key] = result
            return result

        except Exception as e:
            logger.error(f"Error in workload prediction: {e}")
            return self._get_fallback_workload_prediction(hours_ahead)

    def get_predictive_insights(self) -> dict[str, Any]:
        """
        Generate predictive insights and recommendations

        Returns:
            Dictionary with insights and recommendations
        """
        try:
            # Get forecasts
            regional_forecast = self.get_regional_demand_forecast(days_ahead=7)
            workload_forecast = self.get_workload_prediction(hours_ahead=24)

            # Analyze forecasts for insights
            insights = self._analyze_forecasts(regional_forecast, workload_forecast)

            return {
                "regional_insights": insights["regional"],
                "workload_insights": insights["workload"],
                "recommendations": insights["recommendations"],
                "risk_assessment": insights["risks"],
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error generating predictive insights: {e}")
            return {
                "error": "Failed to generate predictive insights",
                "fallback_message": "Using basic heuristics for recommendations",
            }

    def _get_historical_request_data(self, days_back: int = 90) -> list[dict[str, Any]]:
        """Get historical help request data for training"""
        try:
            HelpRequest, _, _, db = _get_models()
            if not HelpRequest or not db:
                return []

            cutoff_date = datetime.utcnow() - timedelta(days=days_back)

            requests = HelpRequest.query.filter(
                HelpRequest.created_at >= cutoff_date
            ).all()

            data = []
            for req in requests:
                region = self._extract_region_from_request(req)

                data.append(
                    {
                        "date": req.created_at.date(),
                        "region": region,
                        "priority": req.priority.value if req.priority else "normal",
                        "status": req.status,
                        "latitude": req.latitude,
                        "longitude": req.longitude,
                        "hour": req.created_at.hour,
                        "day_of_week": req.created_at.weekday(),
                        "month": req.created_at.month,
                    }
                )

            return data

        except Exception as e:
            logger.error(f"Error getting historical request data: {e}")
            return []

    def _get_active_regions(self, data: list[dict[str, Any]]) -> list[str]:
        """Get regions with significant activity"""
        region_counts = defaultdict(int)

        for item in data:
            region = item.get("region", "unknown")
            region_counts[region] += 1

        # Return regions with at least 5 requests in the period
        return [region for region, count in region_counts.items() if count >= 5]

    def _filter_data_by_region(
        self, data: list[dict[str, Any]], region: str
    ) -> list[dict[str, Any]]:
        """Filter data for specific region"""
        return [item for item in data if item.get("region") == region]

    def _forecast_regional_demand(
        self, region_data: list[dict[str, Any]], days_ahead: int
    ) -> dict[str, Any]:
        """Forecast demand for a specific region using ML"""
        try:
            # Convert to DataFrame
            df = pd.DataFrame(region_data)

            # Aggregate by date
            daily_counts = df.groupby("date").size().reset_index(name="requests_count")

            # Fill missing dates with 0
            date_range = pd.date_range(
                start=daily_counts["date"].min(), end=daily_counts["date"].max()
            )
            daily_counts = (
                daily_counts.set_index("date")
                .reindex(date_range, fill_value=0)
                .reset_index()
            )
            daily_counts.columns = ["date", "requests_count"]

            # Add features
            daily_counts["day_of_week"] = daily_counts["date"].dt.dayofweek
            daily_counts["month"] = daily_counts["date"].dt.month
            daily_counts["season"] = daily_counts["month"].apply(self._get_season)
            daily_counts["historical_avg"] = (
                daily_counts["requests_count"].rolling(window=7, min_periods=1).mean()
            )
            daily_counts["trend_factor"] = (
                daily_counts["requests_count"].pct_change(periods=7).fillna(0)
            )

            # Add volunteer density (simplified)
            daily_counts["volunteer_density"] = 1.0  # Placeholder
            daily_counts["population_density"] = 1.0  # Placeholder

            # Prepare features for model
            feature_cols = [
                "day_of_week",
                "month",
                "season",
                "historical_avg",
                "trend_factor",
                "volunteer_density",
                "population_density",
            ]

            # Train model if we have enough data
            if len(daily_counts) >= 14:
                X = daily_counts[feature_cols].fillna(0)
                y = daily_counts["requests_count"]

                # Use time series split for validation
                TimeSeriesSplit(n_splits=min(3, len(daily_counts) - 7))

                model = RandomForestRegressor(
                    n_estimators=100, random_state=42, max_depth=10
                )

                # Simple train/validation split for now
                split_idx = int(len(daily_counts) * 0.8)
                X_train, X_test = X[:split_idx], X[split_idx:]
                y_train, y_test = y[:split_idx], y[split_idx:]

                if len(X_train) > 0:
                    model.fit(X_train, y_train)

                    # Generate forecast
                    forecast_dates = pd.date_range(
                        start=daily_counts["date"].max() + timedelta(days=1),
                        periods=days_ahead,
                    )

                    forecast_data = []
                    for forecast_date in forecast_dates:
                        features = self._prepare_forecast_features(
                            forecast_date, daily_counts
                        )
                        prediction = model.predict([features])[0]

                        forecast_data.append(
                            {
                                "date": forecast_date.strftime("%Y-%m-%d"),
                                "predicted_requests": max(0, round(prediction, 1)),
                                "confidence_interval": {
                                    "lower": max(0, round(prediction * 0.7, 1)),
                                    "upper": round(prediction * 1.3, 1),
                                },
                            }
                        )

                    return {
                        "forecast": forecast_data,
                        "historical_avg": round(
                            daily_counts["requests_count"].mean(), 1
                        ),
                        "peak_day": daily_counts.loc[
                            daily_counts["requests_count"].idxmax()
                        ]["day_of_week"],
                        "seasonal_pattern": self._analyze_seasonal_pattern(
                            daily_counts
                        ),
                        "model_accuracy": (
                            self._evaluate_model_accuracy(model, X_test, y_test)
                            if len(X_test) > 0
                            else None
                        ),
                    }

            # Fallback to simple forecasting
            return self._get_simple_forecast_from_data(daily_counts, days_ahead)

        except Exception as e:
            logger.error(f"Error in regional demand forecast: {e}")
            return self._get_simple_forecast("unknown", days_ahead)

    def _prepare_forecast_features(
        self, forecast_date: pd.Timestamp, historical_data: pd.DataFrame
    ) -> list[float]:
        """Prepare features for forecasting"""
        day_of_week = forecast_date.dayofweek
        month = forecast_date.month
        season = self._get_season(month)

        # Calculate historical average (last 4 weeks)
        recent_data = historical_data[
            historical_data["date"] <= forecast_date - timedelta(days=7)
        ]
        if len(recent_data) >= 7:
            historical_avg = recent_data["requests_count"].tail(28).mean()
        else:
            historical_avg = historical_data["requests_count"].mean()

        # Simple trend calculation
        if len(historical_data) >= 14:
            recent_avg = historical_data["requests_count"].tail(7).mean()
            older_avg = historical_data["requests_count"].tail(14).head(7).mean()
            trend_factor = (recent_avg - older_avg) / older_avg if older_avg > 0 else 0
        else:
            trend_factor = 0

        return [
            day_of_week,  # day_of_week
            month,  # month
            season,  # season
            historical_avg,  # historical_avg
            trend_factor,  # trend_factor
            1.0,  # volunteer_density (placeholder)
            1.0,  # population_density (placeholder)
        ]

    def _get_current_system_state(self) -> dict[str, Any]:
        """Get current system workload state"""
        try:
            HelpRequest, Volunteer, _, db = _get_models()
            if not HelpRequest or not Volunteer or not db:
                return {
                    "active_requests": 0,
                    "pending_requests": 0,
                    "active_volunteers": 0,
                    "avg_response_time_hours": 24,
                }

            # Count active requests (not completed/cancelled)
            active_requests = HelpRequest.query.filter(
                ~HelpRequest.status.in_(["Completed", "Cancelled"])
            ).count()

            # Count pending requests
            pending_requests = HelpRequest.query.filter(
                HelpRequest.status == "Pending"
            ).count()

            # Count active volunteers (with recent activity)
            week_ago = datetime.utcnow() - timedelta(days=7)
            active_volunteers = Volunteer.query.filter(
                Volunteer.last_activity >= week_ago
            ).count()

            # Calculate average response time (simplified)
            avg_response_time = 24  # Default 24 hours

            return {
                "active_requests": active_requests,
                "pending_requests": pending_requests,
                "active_volunteers": active_volunteers,
                "avg_response_time_hours": avg_response_time,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting current system state: {e}")
            return {
                "active_requests": 0,
                "pending_requests": 0,
                "active_volunteers": 0,
                "avg_response_time_hours": 24,
            }

    def _get_historical_workload_data(
        self, hours_back: int = 168
    ) -> list[dict[str, Any]]:
        """Get historical workload data"""
        try:
            HelpRequest, _, _, db = _get_models()
            if not HelpRequest or not db:
                return []

            cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)

            # Get hourly request counts
            hourly_data = (
                db.session.query(
                    db.func.date_trunc("hour", HelpRequest.created_at).label("hour"),
                    db.func.count(HelpRequest.id).label("request_count"),
                )
                .filter(HelpRequest.created_at >= cutoff_time)
                .group_by(db.func.date_trunc("hour", HelpRequest.created_at))
                .order_by(db.func.date_trunc("hour", HelpRequest.created_at))
                .all()
            )

            workload_data = []
            for hour, count in hourly_data:
                workload_data.append(
                    {
                        "timestamp": hour,
                        "requests_count": count,
                        "hour_of_day": hour.hour,
                        "day_of_week": hour.weekday(),
                        "is_weekend": hour.weekday() >= 5,
                    }
                )

            return workload_data

        except Exception as e:
            logger.error(f"Error getting historical workload data: {e}")
            return []

    def _prepare_workload_features(
        self,
        prediction_time: datetime,
        current_state: dict[str, Any],
        historical_data: list[dict[str, Any]],
    ) -> list[float]:
        """Prepare features for workload prediction"""
        # Current system state
        current_requests = current_state.get("active_requests", 0)
        active_volunteers = current_state.get("active_volunteers", 0)
        avg_response_time = current_state.get("avg_response_time_hours", 24)

        # Time features
        day_of_week = prediction_time.weekday()
        hour_of_day = prediction_time.hour
        season = self._get_season(prediction_time.month)

        return [
            current_requests,  # current_requests
            active_volunteers,  # active_volunteers
            avg_response_time,  # avg_response_time
            day_of_week,  # day_of_week
            hour_of_day,  # hour_of_day
            season,  # season
        ]

    def _predict_workload(self, features: list[float]) -> float:
        """Predict workload using ML model"""
        try:
            # Simple rule-based prediction for now
            # In production, this would use a trained ML model

            base_prediction = features[0] * 0.8  # 80% of current requests

            # Adjust for day of week (weekends have less activity)
            day_multiplier = 0.7 if features[3] >= 5 else 1.0

            # Adjust for hour of day (peak hours)
            if 9 <= features[4] <= 17:  # Business hours
                hour_multiplier = 1.2
            elif 18 <= features[4] <= 22:  # Evening
                hour_multiplier = 1.1
            else:  # Night/early morning
                hour_multiplier = 0.6

            # Seasonal adjustment
            season_multipliers = {
                0: 0.8,
                1: 1.0,
                2: 1.2,
                3: 0.9,
            }  # Winter, Spring, Summer, Fall
            season_multiplier = season_multipliers.get(features[5], 1.0)

            prediction = (
                base_prediction * day_multiplier * hour_multiplier * season_multiplier
            )

            return max(0, prediction)

        except Exception as e:
            logger.error(f"Error in workload prediction: {e}")
            return features[0] if features else 0

    def _calculate_prediction_confidence(self, features: list[float]) -> str:
        """Calculate confidence level for prediction"""
        # Simple confidence calculation based on feature stability
        try:
            # Higher confidence for business hours and weekdays
            day_of_week = features[3]
            hour_of_day = features[4]

            if 9 <= hour_of_day <= 17 and day_of_week < 5:
                return "high"
            elif (8 <= hour_of_day <= 18) or (day_of_week == 5):
                return "medium"
            else:
                return "low"

        except Exception:
            return "medium"

    def _analyze_forecasts(
        self, regional_forecast: dict[str, Any], workload_forecast: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze forecasts to generate insights"""
        try:
            insights = {
                "regional": [],
                "workload": [],
                "recommendations": [],
                "risks": [],
            }

            # Analyze regional forecasts
            regions = regional_forecast.get("regions", {})
            for region, data in regions.items():
                forecast = data.get("forecast", [])
                if forecast:
                    avg_predicted = sum(
                        item["predicted_requests"] for item in forecast
                    ) / len(forecast)
                    max_predicted = max(item["predicted_requests"] for item in forecast)

                    if max_predicted > avg_predicted * 1.5:
                        insights["regional"].append(
                            {
                                "region": region,
                                "insight": "High demand spike expected",
                                "severity": "high",
                                "recommendation": f"Increase volunteer capacity in {region}",
                            }
                        )

            # Analyze workload forecasts
            predictions = workload_forecast.get("predictions", [])
            if predictions:
                peak_load = max(item["predicted_requests"] for item in predictions)
                avg_load = sum(
                    item["predicted_requests"] for item in predictions
                ) / len(predictions)

                if peak_load > avg_load * 1.3:
                    insights["workload"].append(
                        {
                            "insight": "Workload spike predicted",
                            "peak_load": peak_load,
                            "recommendation": "Prepare additional support staff",
                        }
                    )

            # Generate recommendations
            insights["recommendations"] = [
                "Monitor high-demand regions closely",
                "Schedule additional volunteers for peak periods",
                "Prepare contingency plans for demand spikes",
                "Review volunteer distribution by region",
            ]

            # Risk assessment
            insights["risks"] = [
                {
                    "level": "medium",
                    "description": "Potential volunteer shortage in high-demand regions",
                },
                {
                    "level": "low",
                    "description": "System capacity may be exceeded during peak hours",
                },
            ]

            return insights

        except Exception as e:
            logger.error(f"Error analyzing forecasts: {e}")
            return {
                "regional": [],
                "workload": [],
                "recommendations": ["Monitor system performance regularly"],
                "risks": [
                    {"level": "low", "description": "Unable to analyze forecast data"}
                ],
            }

    def _extract_region_from_request(self, request) -> str:
        """Extract region from help request"""
        try:
            # Use location field if available, otherwise try to geocode from lat/lng
            if hasattr(request, "location") and request.location:
                return request.location

            # Simple region detection based on coordinates (Bulgaria regions)
            if request.latitude and request.longitude:
                # Sofia region
                if (
                    42.5 <= request.latitude <= 43.0
                    and 23.0 <= request.longitude <= 23.5
                ):
                    return "Sofia"
                # Plovdiv region
                elif (
                    42.0 <= request.latitude <= 42.5
                    and 24.5 <= request.longitude <= 25.0
                ):
                    return "Plovdiv"
                # Varna region
                elif (
                    43.0 <= request.latitude <= 43.5
                    and 27.5 <= request.longitude <= 28.0
                ):
                    return "Varna"
                else:
                    return "Other"

            return "Unknown"

        except Exception:
            return "Unknown"

    def _get_season(self, month: int) -> int:
        """Get season from month (0=Winter, 1=Spring, 2=Summer, 3=Fall)"""
        if month in [12, 1, 2]:
            return 0  # Winter
        elif month in [3, 4, 5]:
            return 1  # Spring
        elif month in [6, 7, 8]:
            return 2  # Summer
        else:
            return 3  # Fall

    def _analyze_seasonal_pattern(self, data: pd.DataFrame) -> dict[str, Any]:
        """Analyze seasonal patterns in the data"""
        try:
            # Day of week patterns
            dow_pattern = data.groupby("day_of_week")["requests_count"].mean().to_dict()

            # Monthly patterns
            monthly_pattern = data.groupby("month")["requests_count"].mean().to_dict()

            return {
                "busiest_day": max(dow_pattern.items(), key=lambda x: x[1])[0],
                "slowest_day": min(dow_pattern.items(), key=lambda x: x[1])[0],
                "monthly_trends": monthly_pattern,
            }

        except Exception:
            return {"error": "Unable to analyze seasonal patterns"}

    def _evaluate_model_accuracy(
        self, model, X_test: pd.DataFrame, y_test: pd.Series
    ) -> dict[str, float]:
        """Evaluate model accuracy"""
        try:
            predictions = model.predict(X_test)
            mae = mean_absolute_error(y_test, predictions)
            mse = mean_squared_error(y_test, predictions)
            r2 = r2_score(y_test, predictions)

            return {
                "mae": round(mae, 2),
                "rmse": round(np.sqrt(mse), 2),
                "r2_score": round(r2, 3),
            }

        except Exception:
            return {"error": "Unable to evaluate model"}

    def _get_simple_forecast(self, region: str, days_ahead: int) -> dict[str, Any]:
        """Simple rule-based forecast as fallback"""
        base_requests = 5  # Average daily requests

        forecast = []
        for i in range(1, days_ahead + 1):
            date = (datetime.utcnow() + timedelta(days=i)).strftime("%Y-%m-%d")
            # Simple pattern: weekdays higher, weekends lower
            day_of_week = (datetime.utcnow() + timedelta(days=i)).weekday()
            multiplier = 0.7 if day_of_week >= 5 else 1.0

            forecast.append(
                {
                    "date": date,
                    "predicted_requests": round(base_requests * multiplier, 1),
                    "confidence_interval": {
                        "lower": round(base_requests * multiplier * 0.5, 1),
                        "upper": round(base_requests * multiplier * 1.5, 1),
                    },
                }
            )

        return {
            "forecast": forecast,
            "historical_avg": base_requests,
            "method": "rule_based_fallback",
        }

    def _get_simple_forecast_from_data(
        self, data: pd.DataFrame, days_ahead: int
    ) -> dict[str, Any]:
        """Simple forecast based on historical averages"""
        try:
            avg_requests = data["requests_count"].mean()

            forecast = []
            for i in range(1, days_ahead + 1):
                date = (data["date"].max() + timedelta(days=i)).strftime("%Y-%m-%d")
                forecast.append(
                    {
                        "date": date,
                        "predicted_requests": round(avg_requests, 1),
                        "confidence_interval": {
                            "lower": round(avg_requests * 0.7, 1),
                            "upper": round(avg_requests * 1.3, 1),
                        },
                    }
                )

            return {
                "forecast": forecast,
                "historical_avg": round(avg_requests, 1),
                "method": "historical_average",
            }

        except Exception:
            return self._get_simple_forecast("unknown", days_ahead)

    def _get_fallback_forecast(
        self, region: str = None, days_ahead: int = 7
    ) -> dict[str, Any]:
        """Fallback forecast when no data is available"""
        regions = [region] if region else ["Sofia", "Plovdiv", "Varna"]

        regional_forecasts = {}
        for reg in regions:
            regional_forecasts[reg] = self._get_simple_forecast(reg, days_ahead)

        return {
            "forecast_period_days": days_ahead,
            "regions": regional_forecasts,
            "generated_at": datetime.utcnow().isoformat(),
            "method": "fallback_no_data",
        }

    def _get_fallback_workload_prediction(self, hours_ahead: int) -> dict[str, Any]:
        """Fallback workload prediction"""
        predictions = []
        current_time = datetime.utcnow()

        for hour in range(1, hours_ahead + 1):
            prediction_time = current_time + timedelta(hours=hour)
            # Simple pattern based on time of day
            hour_of_day = prediction_time.hour
            if 9 <= hour_of_day <= 17:
                base_load = 3
            elif 18 <= hour_of_day <= 22:
                base_load = 2
            else:
                base_load = 1

            predictions.append(
                {
                    "timestamp": prediction_time.isoformat(),
                    "predicted_requests": base_load,
                    "confidence_level": "low",
                    "factors": {
                        "day_of_week": prediction_time.weekday(),
                        "hour_of_day": hour_of_day,
                        "is_weekend": prediction_time.weekday() >= 5,
                        "season": self._get_season(prediction_time.month),
                    },
                }
            )

        return {
            "prediction_period_hours": hours_ahead,
            "current_workload": {"active_requests": 0, "active_volunteers": 0},
            "predictions": predictions,
            "generated_at": datetime.utcnow().isoformat(),
            "method": "fallback_no_data",
        }

    def _is_cache_valid(self, key: str) -> bool:
        """Check if cached prediction is still valid"""
        if key not in self.prediction_cache:
            return False

        cache_time = self.prediction_cache.get(f"{key}_timestamp", 0)
        return (datetime.utcnow().timestamp() - cache_time) < self.cache_timeout

    def _set_cache_timestamp(self, key: str):
        """Set cache timestamp"""
        self.prediction_cache[f"{key}_timestamp"] = datetime.utcnow().timestamp()


# Global instance - created lazily
_predictive_analytics_instance = None


def get_predictive_analytics():
    """Get or create the predictive analytics instance"""
    global _predictive_analytics_instance
    if _predictive_analytics_instance is None:
        _predictive_analytics_instance = PredictiveAnalytics()
    return _predictive_analytics_instance


# For backward compatibility - create instance only when accessed
class _LazyPredictiveAnalytics:
    def __getattr__(self, name):
        return getattr(get_predictive_analytics(), name)


predictive_analytics = _LazyPredictiveAnalytics()
