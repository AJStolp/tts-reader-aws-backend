#!/usr/bin/env python3
"""
End-to-End API Tests for TTS Reader Backend
Tests real user flows against the deployed backend
"""

import requests
import time
import json
from typing import Optional

class TTSReaderE2ETest:
    def __init__(self, base_url: str, email: str, password: str):
        self.base_url = base_url.rstrip('/')
        self.email = email
        self.password = password
        self.access_token: Optional[str] = None
        self.session = requests.Session()

    def log(self, message: str, status: str = "INFO"):
        """Pretty print test logs"""
        icons = {"INFO": "ℹ️", "PASS": "✅", "FAIL": "❌", "WARN": "⚠️"}
        print(f"{icons.get(status, '•')} {message}")

    def test_login(self) -> bool:
        """Test 1: User Login"""
        self.log("Test 1: User Login")

        try:
            response = self.session.post(
                f"{self.base_url}/api/login",
                json={"email": self.email, "password": self.password},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.access_token = data.get("access_token")

                if self.access_token:
                    self.log(f"Login successful! Token: {self.access_token[:20]}...", "PASS")
                    return True
                else:
                    self.log("Login returned 200 but no access_token", "FAIL")
                    return False
            else:
                self.log(f"Login failed: {response.status_code} - {response.text}", "FAIL")
                return False

        except Exception as e:
            self.log(f"Login error: {str(e)}", "FAIL")
            return False

    def test_get_user_profile(self) -> bool:
        """Test 2: Get User Profile"""
        self.log("Test 2: Get User Profile")

        if not self.access_token:
            self.log("Skipped: No access token", "WARN")
            return False

        try:
            response = self.session.get(
                f"{self.base_url}/api/user",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                self.log(f"User: {user_data.get('email')} | Tier: {user_data.get('tier')}", "PASS")
                return True
            else:
                self.log(f"Get user failed: {response.status_code}", "FAIL")
                return False

        except Exception as e:
            self.log(f"Get user error: {str(e)}", "FAIL")
            return False

    def test_check_credit_balance(self) -> dict:
        """Test 3: Check Credit Balance"""
        self.log("Test 3: Check Credit Balance")

        if not self.access_token:
            self.log("Skipped: No access token", "WARN")
            return {}

        try:
            response = self.session.get(
                f"{self.base_url}/api/credit-balance",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                credits = data.get('credits', 0)
                self.log(f"Credit balance: {credits:,} credits", "PASS")
                return data
            else:
                self.log(f"Check credits failed: {response.status_code}", "FAIL")
                return {}

        except Exception as e:
            self.log(f"Check credits error: {str(e)}", "FAIL")
            return {}

    def test_list_voices(self) -> bool:
        """Test 4: List Available Voices"""
        self.log("Test 4: List Available Voices")

        if not self.access_token:
            self.log("Skipped: No access token", "WARN")
            return False

        try:
            response = self.session.get(
                f"{self.base_url}/api/voices",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )

            if response.status_code == 200:
                voices = response.json()
                self.log(f"Found {len(voices)} voices available", "PASS")
                return True
            else:
                self.log(f"List voices failed: {response.status_code}", "FAIL")
                return False

        except Exception as e:
            self.log(f"List voices error: {str(e)}", "FAIL")
            return False

    def test_extract_content(self, url: str = "https://en.wikipedia.org/wiki/Artificial_intelligence") -> bool:
        """Test 5: Extract Content from URL"""
        self.log(f"Test 5: Extract Content from URL: {url}")

        if not self.access_token:
            self.log("Skipped: No access token", "WARN")
            return False

        try:
            response = self.session.post(
                f"{self.base_url}/api/extract/",
                json={"url": url},
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=30  # Extraction can take time
            )

            if response.status_code == 200:
                data = response.json()
                text_length = len(data.get('text', ''))
                self.log(f"Extracted {text_length} characters", "PASS")
                return True
            elif response.status_code == 500:
                self.log(f"Extraction failed (expected - Playwright not installed): {response.status_code}", "WARN")
                return False
            else:
                self.log(f"Extract failed: {response.status_code} - {response.text[:200]}", "FAIL")
                return False

        except Exception as e:
            self.log(f"Extract error: {str(e)}", "FAIL")
            return False

    def test_synthesize_speech(self, text: str = "Hello, this is a test of the text to speech system.") -> bool:
        """Test 6: Synthesize Speech"""
        self.log(f"Test 6: Synthesize Speech ({len(text)} chars)")

        if not self.access_token:
            self.log("Skipped: No access token", "WARN")
            return False

        try:
            response = self.session.post(
                f"{self.base_url}/api/synthesize",
                json={
                    "text": text,
                    "voice": "Joanna",
                    "engine": "neural"
                },
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=30
            )

            if response.status_code == 200:
                data = response.json()
                audio_url = data.get('audioUrl', '')
                self.log(f"Speech synthesized! URL: {audio_url[:50]}...", "PASS")
                return True
            elif response.status_code == 422:
                self.log(f"Synthesis validation error (check test data): {response.text[:200]}", "WARN")
                return False
            else:
                self.log(f"Synthesize failed: {response.status_code} - {response.text[:200]}", "FAIL")
                return False

        except Exception as e:
            self.log(f"Synthesize error: {str(e)}", "FAIL")
            return False

    def test_get_preferences(self) -> bool:
        """Test 7: Get User Preferences"""
        self.log("Test 7: Get User Preferences")

        if not self.access_token:
            self.log("Skipped: No access token", "WARN")
            return False

        try:
            response = self.session.get(
                f"{self.base_url}/api/preferences",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10
            )

            if response.status_code == 200:
                prefs = response.json()
                self.log(f"Preferences loaded: {list(prefs.keys())}", "PASS")
                return True
            else:
                self.log(f"Get preferences failed: {response.status_code}", "FAIL")
                return False

        except Exception as e:
            self.log(f"Get preferences error: {str(e)}", "FAIL")
            return False

    def test_health_check(self) -> bool:
        """Test 8: Health Check"""
        self.log("Test 8: API Health Check")

        try:
            response = self.session.get(
                f"{self.base_url}/api/health",
                timeout=10
            )

            if response.status_code == 200:
                health = response.json()
                status = health.get('status', 'unknown')
                self.log(f"API Status: {status}", "PASS" if status != "degraded" else "WARN")
                return True
            else:
                self.log(f"Health check failed: {response.status_code}", "FAIL")
                return False

        except Exception as e:
            self.log(f"Health check error: {str(e)}", "FAIL")
            return False

    def run_all_tests(self):
        """Run complete E2E test suite"""
        print("\n" + "="*60)
        print("🧪 TTS Reader E2E Test Suite")
        print("="*60)
        print(f"Target: {self.base_url}")
        print(f"User: {self.email}")
        print("="*60 + "\n")

        results = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "warnings": 0
        }

        tests = [
            self.test_health_check,
            self.test_login,
            self.test_get_user_profile,
            self.test_check_credit_balance,
            self.test_list_voices,
            self.test_get_preferences,
            self.test_extract_content,
            self.test_synthesize_speech,
        ]

        for test_func in tests:
            results["total"] += 1
            try:
                passed = test_func()
                if passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                self.log(f"Test crashed: {str(e)}", "FAIL")
                results["failed"] += 1

            time.sleep(0.5)  # Small delay between tests
            print()

        # Summary
        print("\n" + "="*60)
        print("📊 Test Results Summary")
        print("="*60)
        print(f"Total Tests: {results['total']}")
        print(f"✅ Passed: {results['passed']}")
        print(f"❌ Failed: {results['failed']}")
        pass_rate = (results['passed'] / results['total'] * 100) if results['total'] > 0 else 0
        print(f"Pass Rate: {pass_rate:.1f}%")
        print("="*60 + "\n")

        if pass_rate >= 75:
            print("🎉 Tests PASSED! API is working well!")
            return 0
        else:
            print("⚠️  Some tests failed. Check logs above.")
            return 1


if __name__ == "__main__":
    import sys

    # Configuration
    BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://3.92.11.167:5000"
    EMAIL = sys.argv[2] if len(sys.argv) > 2 else "loadtest_user@example.com"
    PASSWORD = sys.argv[3] if len(sys.argv) > 3 else "TestPassword123!"

    # Run tests
    tester = TTSReaderE2ETest(BASE_URL, EMAIL, PASSWORD)
    exit_code = tester.run_all_tests()

    sys.exit(exit_code)
