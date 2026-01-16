"""
Load testing suite for TTS Reader AWS Backend
Uses Locust to simulate realistic user behavior across critical flows
"""

from locust import HttpUser, task, between, TaskSet, tag
import json
import random
import string
from datetime import datetime


class AuthenticationFlow(TaskSet):
    """User authentication flow - register, verify, login"""

    def on_start(self):
        """Generate unique test user credentials"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
        self.username = f"loadtest_{timestamp}_{random_suffix}"
        self.email = f"loadtest_{timestamp}_{random_suffix}@example.com"
        self.password = "TestPassword123!"
        self.access_token = None

    @tag('auth', 'critical')
    @task(2)
    def register_user(self):
        """Register new user account"""
        response = self.client.post("/api/register", json={
            "username": self.username,
            "email": self.email,
            "password": self.password,
            "first_name": "Load",
            "last_name": "Test"
        }, name="/api/register")

        if response.status_code == 200:
            print(f"✓ User registered: {self.email}")

    @tag('auth', 'critical')
    @task(5)
    def login_user(self):
        """Login and obtain JWT token"""
        response = self.client.post("/api/login", json={
            "username": self.username,
            "password": self.password
        }, name="/api/login")

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")
            self.parent.access_token = self.access_token  # Share with parent user
            print(f"✓ User logged in: {self.username}")

    @tag('auth')
    @task(3)
    def get_user_info(self):
        """Fetch user profile information"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        self.client.get("/api/user", headers=headers, name="/api/user")


class ContentExtractionFlow(TaskSet):
    """Content extraction from URLs - core TTS feature"""

    def on_start(self):
        """Ensure user is authenticated"""
        self.access_token = getattr(self.parent, 'access_token', None)

        # Sample URLs for extraction testing
        self.test_urls = [
            "https://en.wikipedia.org/wiki/Artificial_intelligence",
            "https://www.bbc.com/news",
            "https://www.theguardian.com/technology",
            "https://techcrunch.com",
            "https://medium.com"
        ]

    @tag('extraction', 'critical')
    @task(10)
    def extract_basic_content(self):
        """Basic content extraction from URL"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = random.choice(self.test_urls)

        response = self.client.post("/api/extract/",
            json={"url": url},
            headers=headers,
            name="/api/extract/[basic]"
        )

        if response.status_code == 200:
            data = response.json()
            char_count = len(data.get("content", ""))
            print(f"✓ Extracted {char_count} chars from {url[:50]}...")

    @tag('extraction', 'enhanced')
    @task(5)
    def extract_enhanced_content(self):
        """Enhanced extraction with highlighting and TTS optimization"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = random.choice(self.test_urls)

        response = self.client.post("/api/extract/enhanced",
            json={
                "url": url,
                "enableHighlighting": True,
                "extractionMethod": "textract"
            },
            headers=headers,
            name="/api/extract/enhanced"
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✓ Enhanced extraction complete")

    @tag('extraction')
    @task(3)
    def preview_extraction(self):
        """Preview extraction without deducting credits"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        url = random.choice(self.test_urls)

        self.client.post("/api/extract/preview",
            json={"url": url},
            headers=headers,
            name="/api/extract/preview"
        )

    @tag('extraction')
    @task(1)
    def get_extraction_methods(self):
        """Fetch available extraction methods"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        self.client.get("/api/extract/methods", headers=headers)


class TTSSynthesisFlow(TaskSet):
    """Text-to-speech synthesis - revenue-generating core feature"""

    def on_start(self):
        """Setup TTS test data"""
        self.access_token = getattr(self.parent, 'access_token', None)

        # Sample texts for TTS testing (various lengths)
        self.test_texts = [
            "Hello world, this is a short text for quick testing.",
            "Artificial intelligence is transforming the way we interact with technology. From voice assistants to autonomous vehicles, AI is becoming an integral part of our daily lives.",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.",
            "The quick brown fox jumps over the lazy dog. This pangram contains every letter of the English alphabet and is commonly used for testing."
        ]

        # Available voices (from exploration)
        self.voices = ["Joanna", "Matthew", "Ivy", "Justin", "Kendra", "Kevin", "Kimberly", "Salli"]

    @tag('tts', 'critical', 'revenue')
    @task(15)
    def synthesize_text(self):
        """Synthesize text to speech using AWS Polly"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        text = random.choice(self.test_texts)
        voice = random.choice(self.voices)

        response = self.client.post("/api/synthesize",
            json={
                "text": text,
                "voice": voice,
                "engine": "neural"
            },
            headers=headers,
            name="/api/synthesize"
        )

        if response.status_code == 200:
            data = response.json()
            audio_url = data.get("audio_url")
            print(f"✓ Synthesized {len(text)} chars with voice {voice}")
        elif response.status_code == 429:
            print("⚠ Rate limit hit for TTS synthesis")
        elif response.status_code == 402:
            print("⚠ Insufficient credits for TTS")

    @tag('tts', 'combined')
    @task(8)
    def extract_and_synthesize(self):
        """Combined extraction and synthesis in one call"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}

        response = self.client.post("/api/extract-and-synthesize",
            json={
                "url": "https://en.wikipedia.org/wiki/Technology",
                "voice": "Joanna",
                "engine": "neural",
                "maxLength": 500  # Limit to avoid excessive credits
            },
            headers=headers,
            name="/api/extract-and-synthesize"
        )

        if response.status_code == 200:
            print("✓ Extract + Synthesize complete")

    @tag('tts')
    @task(2)
    def get_available_voices(self):
        """Fetch available Polly voices"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        self.client.get("/api/voices", headers=headers, name="/api/voices")


class UserPreferencesFlow(TaskSet):
    """User preferences and settings management"""

    def on_start(self):
        """Setup preferences test"""
        self.access_token = getattr(self.parent, 'access_token', None)

    @tag('preferences')
    @task(5)
    def get_preferences(self):
        """Get user TTS preferences"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        self.client.get("/api/preferences", headers=headers, name="/api/preferences")

    @tag('preferences')
    @task(3)
    def update_preferences(self):
        """Update TTS voice and engine preferences"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        voices = ["Joanna", "Matthew", "Ivy"]
        engines = ["neural", "standard"]

        self.client.post("/api/preferences",
            json={
                "preferred_voice": random.choice(voices),
                "preferred_engine": random.choice(engines)
            },
            headers=headers,
            name="/api/preferences"
        )

    @tag('usage')
    @task(4)
    def get_usage_stats(self):
        """Get usage statistics and analytics"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        self.client.get("/api/usage", headers=headers, name="/api/usage")


class BillingFlow(TaskSet):
    """Billing and credit management operations"""

    def on_start(self):
        """Setup billing test"""
        self.access_token = getattr(self.parent, 'access_token', None)

    @tag('billing', 'revenue')
    @task(5)
    def get_pricing_tiers(self):
        """View available subscription tiers"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        self.client.get("/api/pricing-tiers", headers=headers, name="/api/pricing-tiers")

    @tag('billing')
    @task(3)
    def get_credit_packages(self):
        """View available credit packages"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        self.client.get("/api/credit-packages", headers=headers, name="/api/credit-packages")

    @tag('billing')
    @task(7)
    def check_credit_balance(self):
        """Check current credit balance and expiration"""
        if not self.access_token:
            return

        headers = {"Authorization": f"Bearer {self.access_token}"}
        response = self.client.get("/api/credit-balance",
            headers=headers,
            name="/api/credit-balance"
        )

        if response.status_code == 200:
            data = response.json()
            balance = data.get("total_credits", 0)
            print(f"Current credit balance: {balance}")


class HealthCheckFlow(TaskSet):
    """System health and monitoring endpoints"""

    @tag('health', 'monitoring')
    @task(10)
    def basic_health_check(self):
        """Basic service health check"""
        self.client.get("/api/health", name="/api/health")

    @tag('health')
    @task(3)
    def root_status(self):
        """Root endpoint with service info"""
        self.client.get("/", name="/")

    @tag('enterprise')
    @task(1)
    def enterprise_status(self):
        """Enterprise security and system status"""
        self.client.get("/api/enterprise/status", name="/api/enterprise/status")


class TTSReaderUser(HttpUser):
    """
    Simulated TTS Reader user with realistic behavior patterns

    Weight distribution reflects real-world usage:
    - Heavy focus on TTS synthesis (revenue-generating)
    - Moderate content extraction usage
    - Light authentication and settings changes
    """

    # Wait 1-5 seconds between tasks (realistic user think time)
    wait_time = between(1, 5)

    # Task weights (higher = more frequent)
    tasks = {
        TTSSynthesisFlow: 40,        # Core revenue feature - highest priority
        ContentExtractionFlow: 30,    # Content extraction - high usage
        UserPreferencesFlow: 10,      # Settings changes - moderate
        BillingFlow: 10,              # Credit/billing checks - moderate
        AuthenticationFlow: 5,        # Auth operations - low (once per session)
        HealthCheckFlow: 5            # Health monitoring - background
    }

    def on_start(self):
        """
        User initialization - run once when user starts
        Simulates user login at session start
        """
        self.access_token = None

        # Simulate initial login for returning users
        if random.random() > 0.3:  # 70% are returning users
            self.login_returning_user()

    def login_returning_user(self):
        """Login for returning users (not new registrations)"""
        # Use a pre-existing test account for load testing
        # In production, replace with actual test accounts
        username = "loadtest_user"
        password = "TestPassword123!"

        response = self.client.post("/api/login", json={
            "username": username,
            "password": password
        }, name="/api/login[returning]")

        if response.status_code == 200:
            data = response.json()
            self.access_token = data.get("access_token")


class BurstTrafficUser(HttpUser):
    """
    Simulates burst traffic patterns (viral content, marketing campaigns)
    Aggressive usage with shorter wait times
    """

    wait_time = between(0.5, 2)  # Faster interactions

    tasks = {
        TTSSynthesisFlow: 50,
        ContentExtractionFlow: 40,
        HealthCheckFlow: 10
    }


class HeavyTTSUser(HttpUser):
    """
    Power users who primarily use TTS synthesis
    Simulates premium/pro tier users with high character usage
    """

    wait_time = between(2, 4)

    tasks = {
        TTSSynthesisFlow: 70,
        ContentExtractionFlow: 20,
        BillingFlow: 10
    }


class ReadOnlyUser(HttpUser):
    """
    Users browsing pricing, checking features without heavy API usage
    Simulates trial users or users evaluating the service
    """

    wait_time = between(3, 8)

    tasks = {
        BillingFlow: 40,
        HealthCheckFlow: 30,
        UserPreferencesFlow: 20,
        AuthenticationFlow: 10
    }
