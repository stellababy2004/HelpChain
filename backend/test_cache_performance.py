"""
Test Cache Performance - Comprehensive Cache System Testing
===========================================================

Този скрипт тества новата Simple Cache система за performance подобрения.
"""

import time
from datetime import datetime

import requests


class CachePerformanceTester:
    def __init__(self, base_url="http://localhost:5000"):
        self.base_url = base_url
        self.results = []

    def test_api_performance(self, runs=5):
        """Тестване на API performance с и без cache"""
        print(f"\n🧪 Тестване на API Performance ({runs} runs)")
        print("=" * 60)

        # Тест 1: Първи заявки (празен cache)
        print("\n📊 Тест 1: Първи заявки (празен cache)")
        cold_times = []

        for i in range(runs):
            start_time = time.time()
            try:
                response = requests.get(f"{self.base_url}/api/analytics-data?v={i}")
                end_time = time.time()

                if response.status_code == 200:
                    response_time = end_time - start_time
                    cold_times.append(response_time)

                    data = response.json()
                    cache_info = data.get("metadata", {}).get("cache_stats", {})

                    print(
                        f"  Run {i + 1}: {response_time:.3f}s - Cache hits: {cache_info.get('hits', 0)}"
                    )
                else:
                    print(f"  Run {i + 1}: ERROR - Status {response.status_code}")

            except Exception as e:
                print(f"  Run {i + 1}: ERROR - {e}")

            time.sleep(0.1)  # Малка пауза

        # Тест 2: Повторни заявки (warm cache)
        print("\n🔥 Тест 2: Повторни заявки (warm cache)")
        hot_times = []

        for i in range(runs):
            start_time = time.time()
            try:
                response = requests.get(
                    f"{self.base_url}/api/analytics-data"
                )  # Същия endpoint
                end_time = time.time()

                if response.status_code == 200:
                    response_time = end_time - start_time
                    hot_times.append(response_time)

                    data = response.json()
                    cache_info = data.get("metadata", {}).get("cache_stats", {})

                    print(
                        f"  Run {i + 1}: {response_time:.3f}s - Cache hits: {cache_info.get('hits', 0)}"
                    )
                else:
                    print(f"  Run {i + 1}: ERROR - Status {response.status_code}")

            except Exception as e:
                print(f"  Run {i + 1}: ERROR - {e}")

            time.sleep(0.1)

        # Анализ на резултатите
        self.analyze_performance(cold_times, hot_times)

    def analyze_performance(self, cold_times, hot_times):
        """Анализиране на performance резултатите"""
        if not cold_times or not hot_times:
            print("❌ Недостатъчно данни за анализ")
            return

        avg_cold = sum(cold_times) / len(cold_times)
        avg_hot = sum(hot_times) / len(hot_times)

        improvement = ((avg_cold - avg_hot) / avg_cold) * 100 if avg_cold > 0 else 0

        print("\n📈 РЕЗУЛТАТИ ОТ PERFORMANCE ТЕСТОВЕТЕ")
        print("=" * 60)
        print(f"🥶 Средно време без cache: {avg_cold:.3f}s")
        print(f"🔥 Средно време с cache:   {avg_hot:.3f}s")
        print(f"🚀 Подобрение:            {improvement:.1f}%")

        if improvement > 50:
            print("✅ ОТЛИЧЕН РЕЗУЛТАТ! Cache работи перфектно")
        elif improvement > 20:
            print("✅ ДОБЪР РЕЗУЛТАТ! Cache дава видимо подобрение")
        elif improvement > 0:
            print("⚠️  УМЕРЕН РЕЗУЛТАТ! Cache работи частично")
        else:
            print("❌ ПРОБЛЕМ! Cache не дава подобрение")

        # Детайлни статистики
        print("\n📊 Детайлни статистики:")
        print(f"  Cold times: min={min(cold_times):.3f}s, max={max(cold_times):.3f}s")
        print(f"  Hot times:  min={min(hot_times):.3f}s, max={max(hot_times):.3f}s")

    def test_cache_stats(self):
        """Тестване на cache статистики API"""
        print("\n🔍 Тестване на Cache Stats API")
        print("=" * 40)

        try:
            response = requests.get(f"{self.base_url}/api/cache-stats")

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    stats = data.get("stats", {})
                    performance = data.get("performance", {})

                    print("✅ Cache Stats API работи")
                    print(f"  Cache enabled: {data.get('cache_enabled')}")
                    print(f"  Total requests: {stats.get('total_requests', 0)}")
                    print(f"  Cache hits: {stats.get('hits', 0)}")
                    print(f"  Hit rate: {stats.get('hit_rate', 0):.1f}%")
                    print(
                        f"  Average response time: {performance.get('avg_response_time', 0):.3f}s"
                    )

                else:
                    print(f"❌ Cache Stats API error: {data.get('error', 'Unknown')}")

            else:
                print(f"❌ HTTP Error: {response.status_code}")

        except Exception as e:
            print(f"❌ Connection error: {e}")

    def test_cache_clear(self):
        """Тестване на cache clear функционалност"""
        print("\n🧹 Тестване на Cache Clear")
        print("=" * 30)

        try:
            response = requests.post(f"{self.base_url}/api/cache-clear")

            if response.status_code == 200:
                data = response.json()

                if data.get("success"):
                    print("✅ Cache успешно изчистен")
                    print(f"  Message: {data.get('message')}")
                else:
                    print(f"❌ Cache clear error: {data.get('error', 'Unknown')}")

            else:
                print(f"❌ HTTP Error: {response.status_code}")

        except Exception as e:
            print(f"❌ Connection error: {e}")

    def run_comprehensive_test(self):
        """Пълен тест на cache системата"""
        print("🚀 COMPREHENSIVE CACHE PERFORMANCE TEST")
        print("=" * 80)
        print(f"Тестване на: {self.base_url}")
        print(f"Време: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 1. Изчистваме cache за чист тест
        self.test_cache_clear()

        # 2. Тестваме performance
        self.test_api_performance(runs=3)

        # 3. Проверяваме статистики
        self.test_cache_stats()

        print(f"\n🎉 ТЕСТ ЗАВЪРШЕН - {datetime.now().strftime('%H:%M:%S')}")


if __name__ == "__main__":
    tester = CachePerformanceTester()
    tester.run_comprehensive_test()
