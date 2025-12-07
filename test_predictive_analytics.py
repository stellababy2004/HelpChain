#!/usr/bin/env python3
"""
Test script for predictive analytics functionality
"""

import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))


def test_predictive_analytics():
    """Test the predictive analytics functionality"""
    try:
        print("Testing predictive analytics import...")
        from predictive_analytics import predictive_analytics

        print("✓ Successfully imported predictive_analytics")

        print("\nTesting regional demand forecast...")
        forecast = predictive_analytics.get_regional_demand_forecast(days_ahead=7)
        print(f"✓ Regional forecast generated: {len(forecast.get('forecast', []))} regions")

        print("\nTesting workload prediction...")
        workload = predictive_analytics.get_workload_prediction(hours_ahead=24)
        print(f"✓ Workload prediction generated: {len(workload.get('predictions', []))} hours")

        print("\nTesting predictive insights...")
        insights = predictive_analytics.get_predictive_insights()
        print(f"✓ Insights generated: {len(insights.get('insights', []))} insights")

        print("\n🎉 All predictive analytics tests passed!")

        # Print sample data
        if forecast.get("forecast"):
            sample_region = forecast["forecast"][0]
            print(f"\nSample regional forecast for {sample_region.get('region', 'Unknown')}:")
            print(f"  - Predicted requests: {sample_region.get('predicted_requests', 0)}")
            print(f"  - Confidence: {sample_region.get('confidence', 0):.2f}")

        if workload.get("predictions"):
            sample_hour = workload["predictions"][0]
            print("\nSample workload prediction:")
            print(f"  - Hour: {sample_hour.get('hour', 'Unknown')}")
            print(f"  - Predicted load: {sample_hour.get('predicted_load', 0):.2f}")

    except Exception as e:
        print(f"❌ Error testing predictive analytics: {e}")
        import traceback

        traceback.print_exc()
        return False

    return True


if __name__ == "__main__":
    success = test_predictive_analytics()
    sys.exit(0 if success else 1)
