"""
Mock AWS Services for Load Testing

Use this to test your application logic, database, auth, and rate limiting
WITHOUT hitting AWS Polly/S3/Textract and getting charged.

Set environment variable: LOAD_TEST_MODE=true
"""

import io
import json
import random
import time
import uuid
from typing import Dict, List


class MockPolly:
    """Mock AWS Polly client that returns fake audio data"""

    def synthesize_speech(self, **kwargs):
        """Mock Polly synthesize_speech - returns fake MP3 data"""
        text = kwargs.get("Text", "")
        output_format = kwargs.get("OutputFormat", "mp3")
        voice_id = kwargs.get("VoiceId", "Joanna")

        # Simulate Polly processing time (50-200ms per 100 chars)
        char_count = len(text)
        processing_time = (char_count / 100) * random.uniform(0.05, 0.2)
        time.sleep(processing_time)

        if output_format == "mp3":
            # Return fake MP3 data (silence)
            # This is a minimal valid MP3 header + frame
            fake_mp3 = b'\xff\xfb\x90\x00' + b'\x00' * 1024  # ~1KB fake audio
            return {
                'AudioStream': io.BytesIO(fake_mp3),
                'RequestCharacters': str(char_count)
            }

        elif output_format == "json":
            # Return fake speech marks
            speech_marks = []
            words = text.split()
            time_ms = 0

            for word in words:
                speech_marks.append({
                    "time": time_ms,
                    "type": "word",
                    "start": 0,
                    "end": len(word),
                    "value": word
                })
                time_ms += random.randint(200, 500)

            marks_json = '\n'.join(json.dumps(mark) for mark in speech_marks)
            return {
                'AudioStream': io.BytesIO(marks_json.encode('utf-8')),
                'RequestCharacters': str(char_count)
            }

    def describe_voices(self, **kwargs):
        """Mock describe_voices - returns all 24 standard English voices"""
        return {
            "Voices": [
                # US English (8 voices)
                {"Id": "Joanna", "Name": "Joanna", "Gender": "Female", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Ivy", "Name": "Ivy", "Gender": "Female", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Kendra", "Name": "Kendra", "Gender": "Female", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Kimberly", "Name": "Kimberly", "Gender": "Female", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Salli", "Name": "Salli", "Gender": "Female", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Matthew", "Name": "Matthew", "Gender": "Male", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Justin", "Name": "Justin", "Gender": "Male", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Joey", "Name": "Joey", "Gender": "Male", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},

                # British English (4 voices)
                {"Id": "Amy", "Name": "Amy", "Gender": "Female", "LanguageName": "British English", "LanguageCode": "en-GB", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Emma", "Name": "Emma", "Gender": "Female", "LanguageName": "British English", "LanguageCode": "en-GB", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Brian", "Name": "Brian", "Gender": "Male", "LanguageName": "British English", "LanguageCode": "en-GB", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Arthur", "Name": "Arthur", "Gender": "Male", "LanguageName": "British English", "LanguageCode": "en-GB", "SupportedEngines": ["standard", "neural"]},

                # Australian English (3 voices)
                {"Id": "Nicole", "Name": "Nicole", "Gender": "Female", "LanguageName": "Australian English", "LanguageCode": "en-AU", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Olivia", "Name": "Olivia", "Gender": "Female", "LanguageName": "Australian English", "LanguageCode": "en-AU", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Russell", "Name": "Russell", "Gender": "Male", "LanguageName": "Australian English", "LanguageCode": "en-AU", "SupportedEngines": ["standard", "neural"]},

                # Indian English (2 voices)
                {"Id": "Aditi", "Name": "Aditi", "Gender": "Female", "LanguageName": "Indian English", "LanguageCode": "en-IN", "SupportedEngines": ["standard"]},
                {"Id": "Raveena", "Name": "Raveena", "Gender": "Female", "LanguageName": "Indian English", "LanguageCode": "en-IN", "SupportedEngines": ["standard"]},

                # Welsh English (1 voice)
                {"Id": "Geraint", "Name": "Geraint", "Gender": "Male", "LanguageName": "Welsh English", "LanguageCode": "en-GB-WLS", "SupportedEngines": ["standard"]},

                # Additional voices
                {"Id": "Kevin", "Name": "Kevin", "Gender": "Male", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Stephen", "Name": "Stephen", "Gender": "Male", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Ruth", "Name": "Ruth", "Gender": "Female", "LanguageName": "US English", "LanguageCode": "en-US", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Aria", "Name": "Aria", "Gender": "Female", "LanguageName": "New Zealand English", "LanguageCode": "en-NZ", "SupportedEngines": ["standard", "neural"]},
                {"Id": "Ayanda", "Name": "Ayanda", "Gender": "Female", "LanguageName": "South African English", "LanguageCode": "en-ZA", "SupportedEngines": ["standard", "neural"]},
            ]
        }


class MockS3:
    """Mock AWS S3 client that simulates storage without actual uploads"""

    def __init__(self):
        self.storage: Dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body, **kwargs):
        """Mock S3 put_object - stores in memory"""
        # Simulate S3 upload time (10-50ms)
        time.sleep(random.uniform(0.01, 0.05))

        if isinstance(Body, bytes):
            self.storage[Key] = Body
        else:
            self.storage[Key] = Body.read()

        return {
            'ETag': f'"{uuid.uuid4()}"',
            'ServerSideEncryption': 'AES256'
        }

    def get_object(self, Bucket, Key):
        """Mock S3 get_object - retrieves from memory"""
        if Key in self.storage:
            return {
                'Body': io.BytesIO(self.storage[Key]),
                'ContentType': 'audio/mpeg'
            }
        raise Exception(f"Key {Key} not found")

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        """Mock presigned URL - returns fake URL"""
        key = Params.get("Key", "audio.mp3")
        return f"https://mock-s3-bucket.s3.amazonaws.com/{key}?expires={ExpiresIn}"

    def head_bucket(self, Bucket):
        """Mock head_bucket - always succeeds"""
        time.sleep(0.01)
        return {'ResponseMetadata': {'HTTPStatusCode': 200}}

    def list_buckets(self):
        """Mock list_buckets - returns fake bucket list"""
        return {
            'Buckets': [
                {'Name': 'mock-tts-bucket', 'CreationDate': '2024-01-01'}
            ]
        }


class MockTextract:
    """Mock AWS Textract for content extraction"""

    def extract_text(self, content):
        """Mock text extraction - returns input as-is or generates fake content"""
        if content:
            return content

        # Generate fake extracted text
        return """
        This is mock extracted content for load testing.
        The actual extraction would use AWS Textract, which we're bypassing
        to avoid charges during load tests.

        This text is sufficient to test database writes, character counting,
        credit deductions, and API response formatting without hitting AWS.
        """


def get_mock_aws_service():
    """Returns a mock AWS service for load testing"""
    from .services import AWSService
    import os

    # Create a real AWS service instance but replace clients with mocks
    class MockAWSService(AWSService):
        def _initialize_aws(self):
            """Override to use mock clients"""
            # Don't call parent's _initialize_aws to avoid AWS credential checks
            self.session = None  # No real session needed
            self.s3 = MockS3()
            self.polly = MockPolly()
            self.bucket_name = os.getenv("S3_BUCKET_NAME", "mock-tts-bucket")

            # Skip AWS credential validation
            print("🧪 LOAD TEST MODE: Using mock AWS services (no charges)")

    return MockAWSService()


def should_use_mock_services() -> bool:
    """Check if we should use mock services based on environment"""
    import os
    load_test_mode = os.getenv("LOAD_TEST_MODE", "false").lower() == "true"

    if load_test_mode:
        print("=" * 80)
        print("🧪 LOAD TEST MODE ENABLED")
        print("   - AWS Polly calls will be mocked (no charges)")
        print("   - S3 uploads will be simulated (no storage costs)")
        print("   - Textract will return mock data")
        print("   - All application logic, database, auth will work normally")
        print("=" * 80)

    return load_test_mode
