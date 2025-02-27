from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify
import boto3
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import os
import time
import json
import logging
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "http://localhost:3000"}})
CORS(app, supports_credentials=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(os.getcwd(), "database.db")}'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key')
app.config['JWT_EXPIRATION_DELTA'] = timedelta(days=1)

db = SQLAlchemy(app)
jwt = JWTManager(app)

# User model
class User(db.Model):
    id = db.Column(db.String, primary_key=True)
    remaining_chars = db.Column(db.Integer, default=100)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# AWS setup
try:
    region = os.environ['AWS_REGION']
except KeyError:
    raise ValueError("AWS_REGION environment variable is not set")

try:
    s3 = boto3.client('s3', region_name=region)
    polly = boto3.client('polly', region_name=region)
except Exception as e:
    raise ValueError(f"Failed to create Boto3 clients: {e}")

# Function to generate signed URLs
def generate_presigned_url(bucket, key, expiration=3600):
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': bucket, 'Key': key},
                                    ExpiresIn=expiration)
    return url

# Single bucket for both storage and logging
bucket_name = 'tts-neural-reader-data'

def setup_bucket():
    # Check if the bucket exists, create it if it doesn't
    try:
        s3.head_bucket(Bucket=bucket_name)
    except s3.exceptions.ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            s3.create_bucket(Bucket=bucket_name)
            # Secure the bucket
            s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True,
                    'RestrictPublicBuckets': True
                }
            )
            # Enable versioning
            s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            # Configure CORS
            cors_configuration = {
                'CORSRules': [
                    {
                        'AllowedHeaders': ['Authorization'],
                        'AllowedMethods': ['GET', 'HEAD', 'PUT', 'POST', 'DELETE'],
                        'AllowedOrigins': ['http://localhost:3000'],
                        'ExposeHeaders': ['ETag'],
                        'MaxAgeSeconds': 3000
                    }
                ]
            }
            s3.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors_configuration)

    # Configure server-side logging within the same bucket
    s3.put_bucket_logging(
        Bucket=bucket_name,
        BucketLoggingStatus={
            'LoggingEnabled': {
                'TargetBucket': bucket_name,
                'TargetPrefix': 'logs/'
            }
        }
    )

# Initialize the bucket
setup_bucket()

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    user_id = data['user_id']
    password = data['password']
    
    if User.query.get(user_id):
        return jsonify({'error': 'User already exists'}), 400
    
    user = User(id=user_id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user_id = data['user_id']
    password = data['password']
    
    user = User.query.get(user_id)
    if user and user.check_password(password):
        access_token = create_access_token(identity=user_id)
        # Log login event
        log_user_data(user_id, 'login')
        return jsonify({'token': access_token}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/synthesize', methods=['POST'])
@jwt_required()
def synthesize():
    user_id = get_jwt_identity()
    data = request.get_json()
    text_to_speech = data['text_to_speech']
    voice_id = data.get('voice_id', 'Danielle')
    text_length = len(text_to_speech)

    user = User.query.get(user_id)
    if user is None:
        return jsonify({'error': 'User not found'}), 404

    if text_length > user.remaining_chars:
        return jsonify({'message': 'User has exceeded their character limit'}), 403

    try:
        audio_file_key = f'users/{user_id}/audio/speech.mp3'
        speech_marks_file_key = f'users/{user_id}/speech_marks/speech_marks.json'

        # Synthesize audio
        audio_response = polly.synthesize_speech(
            Text=text_to_speech,
            OutputFormat='mp3',
            VoiceId=voice_id,
            Engine='neural'
        )
        audio_stream = audio_response['AudioStream'].read()
        s3.put_object(Bucket=bucket_name, Key=audio_file_key, Body=audio_stream)

        # Synthesize speech marks
        speech_marks_response = polly.synthesize_speech(
            Text=text_to_speech,
            OutputFormat='json',
            VoiceId=voice_id,
            SpeechMarkTypes=['word'],
            Engine='neural'
        )
        speech_marks = speech_marks_response['AudioStream'].read()
        s3.put_object(Bucket=bucket_name, Key=speech_marks_file_key, Body=speech_marks)

        # Generate signed URLs
        audio_url = generate_presigned_url(bucket_name, audio_file_key)
        speech_marks_url = generate_presigned_url(bucket_name, speech_marks_file_key)

        # Update user data
        user.remaining_chars -= text_length
        db.session.commit()

        # Log synthesis usage
        log_user_data(user_id, 'synthesize', {
            'text_length': text_length,
            'remaining_chars': user.remaining_chars,
            'charge': 0.00  # Placeholder; adjust based on pricing logic
        })

        return jsonify({'audio_url': audio_url, 'speech_marks_url': speech_marks_url}), 200
    except Exception as e:
        # Log error
        log_user_data(user_id, 'error', {'error': str(e)})
        return jsonify({'error': str(e)}), 500

@app.route('/usage', methods=['GET'])
@jwt_required()
def get_usage():
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if user is None:
        return jsonify({'error': 'User not found'}), 404
    
    # Log usage check
    log_user_data(user_id, 'usage_check', {'remaining_chars': user.remaining_chars})
    return jsonify({'remaining_chars': user.remaining_chars}), 200

def log_user_data(user_id, event_type, additional_data=None):
    log_key = f'logs/users/{user_id}/{event_type}_{int(time.time())}.json'
    log_data = {
        'user_id': user_id,
        'event_type': event_type,
        'timestamp': int(time.time()),
        **(additional_data or {})
    }
    s3.put_object(Bucket=bucket_name, Key=log_key, Body=json.dumps(log_data))
    logger.info(f"Logged {event_type} event for user {user_id}")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)