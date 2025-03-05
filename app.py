from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt,
    get_jwt_identity
)
from werkzeug.security import generate_password_hash, check_password_hash
import boto3
import os
import time
import json
import logging
from flask_cors import CORS
from typing import Optional
import io
from pydub import AudioSegment

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# CORS configuration for frontend (e.g., localhost:3000 for development)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:3000"]}}, supports_credentials=True)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(os.getcwd(), "database.db")}'
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'strong-secret-key-change-this-in-prod')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 24 * 60 * 60  # 1 day (24 hours) for access tokens
app.config['JWT_REFRESH_TOKEN_EXPIRES'] = 24 * 60 * 60  # 1 day (24 hours) for refresh tokens

# Initialize SQLAlchemy and JWT
db = SQLAlchemy(app)
jwt = JWTManager(app)

# User model with added preferences fields
class User(db.Model):
    id = db.Column(db.String, primary_key=True)
    remaining_chars = db.Column(db.Integer, default=100)
    password_hash = db.Column(db.String(128))
    engine = db.Column(db.String, default='standard')  # New field for engine preference
    voice_id = db.Column(db.String, default='Joey')    # New field for voice preference

    def set_password(self, password: str) -> None:
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Check if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

# AWS setup
def get_aws_clients() -> tuple[boto3.client, boto3.client]:
    """Initialize and return AWS S3 and Polly clients with error handling."""
    try:
        region = os.environ['AWS_REGION']
    except KeyError:
        raise ValueError("AWS_REGION environment variable is not set")

    try:
        s3 = boto3.client('s3', region_name=region)
        polly = boto3.client('polly', region_name=region)
        return s3, polly
    except Exception as e:
        raise ValueError(f"Failed to create AWS clients: {str(e)}")

s3, polly = get_aws_clients()

# Function to generate signed URLs
def generate_presigned_url(bucket: str, key: str, expiration: int = 3600) -> str:
    """Generate a presigned URL for an S3 object."""
    try:
        url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': key},
            ExpiresIn=expiration
        )
        return url
    except Exception as e:
        logging.error(f"Failed to generate presigned URL: {str(e)}")
        raise

# S3 bucket configuration
bucket_name = 'tts-neural-reader-data'

def setup_bucket() -> None:
    """Set up and configure the S3 bucket with security and logging."""
    try:
        s3.head_bucket(Bucket=bucket_name)
    except s3.exceptions.ClientError as e:
        if int(e.response['Error']['Code']) == 404:
            s3.create_bucket(Bucket=bucket_name)
            s3.put_public_access_block(
                Bucket=bucket_name,
                PublicAccessBlockConfiguration={
                    'BlockPublicAcls': True,
                    'IgnorePublicAcls': True,
                    'BlockPublicPolicy': True,
                    'RestrictPublicBuckets': True
                }
            )
            s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            cors_configuration = {
                'CORSRules': [
                    {
                        'AllowedHeaders': ['*'],
                        'AllowedMethods': ['GET', 'HEAD'],
                        'AllowedOrigins': ['*'],
                        'ExposeHeaders': ['ETag'],
                        'MaxAgeSeconds': 3000
                    }
                ]
            }
            s3.put_bucket_cors(Bucket=bucket_name, CORSConfiguration=cors_configuration)

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

# Maximum text length per chunk for AWS Polly
MAX_TEXT_LENGTH = 5900

def split_text(text, chunk_size):
    """Split text into chunks of specified size, ensuring splits occur at word boundaries."""
    words = text.split()
    chunks = []
    current_chunk = []
    for word in words:
        if current_chunk:
            potential_chunk = ' '.join(current_chunk + [word])
            if len(potential_chunk) > chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
            else:
                current_chunk.append(word)
        else:
            if len(word) > chunk_size:
                chunks.append(word)
            else:
                current_chunk.append(word)
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    return chunks

@app.route('/api/register', methods=['POST'])
def register() -> tuple[dict, int]:
    """Register a new user."""
    data = request.get_json()
    user_id = data.get('user_id')
    password = data.get('password')
    if not user_id or not password:
        return jsonify({'error': 'User ID and password are required'}), 400
    if User.query.get(user_id):
        return jsonify({'error': 'User already exists'}), 400
    user = User(id=user_id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    logger.info(f"User {user_id} registered successfully")
    return jsonify({'message': 'User registered successfully'}), 201

@app.route('/api/login', methods=['POST'])
def login() -> tuple[dict, int]:
    """Authenticate a user and return access and refresh tokens."""
    data = request.get_json()
    user_id = data.get('user_id')
    password = data.get('password')
    if not user_id or not password:
        return jsonify({'error': 'User ID and password are required'}), 400
    user = User.query.get(user_id)
    if user and user.check_password(password):
        access_token = create_access_token(identity=user_id)
        refresh_token = create_refresh_token(identity=user_id)
        log_user_data(user_id, 'login')
        return jsonify({
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
    return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/refresh', methods=['POST'])
@jwt_required()
def refresh() -> tuple[dict, int]:
    """Refresh an access token using a valid refresh token."""
    current_user = get_jwt_identity()
    token_data = get_jwt()
    if token_data.get('type') != 'refresh':
        return jsonify({'error': 'Refresh token required'}), 401
    new_access_token = create_access_token(identity=current_user)
    logger.info(f"Refreshed access token for user {current_user}")
    return jsonify({'access_token': new_access_token}), 200

@app.route('/api/logout', methods=['POST'])
@jwt_required()
def logout() -> tuple[dict, int]:
    """Handle user logout by logging the event (client clears tokens)."""
    user_id = get_jwt_identity()
    log_user_data(user_id, 'logout')
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/api/synthesize', methods=['POST'])
@jwt_required()
def synthesize() -> tuple[dict, int]:
    """Synthesize text to speech using Amazon Polly and return audio/speech marks URLs."""
    user_id = get_jwt_identity()
    data = request.get_json()
    text_to_speech = data.get('text_to_speech', '')
    voice_id = data.get('voice_id', 'Joey')
    engine = data.get('engine', 'standard')

    if engine not in ['standard', 'neural']:
        return jsonify({'error': 'Invalid engine type. Use "standard" or "neural".'}), 400

    if not text_to_speech.strip():
        return jsonify({'error': 'No text to synthesize'}), 400

    text_length = len(text_to_speech)
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if text_length > user.remaining_chars:
        return jsonify({'message': 'User has exceeded their character limit'}), 403

    try:
        chunks = split_text(text_to_speech, MAX_TEXT_LENGTH)
        audio_segments = []
        speech_marks_list = []
        cumulative_time = 0

        for chunk in chunks:
            audio_response = polly.synthesize_speech(
                Text=chunk,
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine=engine
            )
            audio_stream = audio_response['AudioStream'].read()
            audio_segment = AudioSegment.from_file(io.BytesIO(audio_stream), format='mp3')
            audio_segments.append(audio_segment)

            speech_marks_response = polly.synthesize_speech(
                Text=chunk,
                OutputFormat='json',
                VoiceId=voice_id,
                SpeechMarkTypes=['word'],
                Engine=engine
            )
            speech_marks_text = speech_marks_response['AudioStream'].read().decode('utf-8')
            chunk_marks = [json.loads(line) for line in speech_marks_text.splitlines() if line]
            for mark in chunk_marks:
                mark['time'] += cumulative_time
            speech_marks_list.extend(chunk_marks)
            cumulative_time += len(audio_segment)

        combined_audio = AudioSegment.empty()
        for segment in audio_segments:
            combined_audio += segment

        f = io.BytesIO()
        combined_audio.export(f, format='mp3')
        audio_bytes = f.getvalue()

        audio_file_key = f'users/{user_id}/audio/speech.mp3'
        s3.put_object(Bucket=bucket_name, Key=audio_file_key, Body=audio_bytes)
        audio_url = generate_presigned_url(bucket_name, audio_file_key)

        speech_marks_text = '\n'.join([json.dumps(mark) for mark in speech_marks_list])
        speech_marks_file_key = f'users/{user_id}/speech_marks/speech_marks.json'
        s3.put_object(Bucket=bucket_name, Key=speech_marks_file_key, Body=speech_marks_text)
        speech_marks_url = generate_presigned_url(bucket_name, speech_marks_file_key)

        charge = calculate_charge(text_length, engine)
        user.remaining_chars -= text_length
        db.session.commit()

        log_user_data(user_id, 'synthesize', {
            'text_length': text_length,
            'remaining_chars': user.remaining_chars,
            'charge': charge,
            'engine': engine
        })

        return jsonify({'audio_url': audio_url, 'speech_marks_url': speech_marks_url}), 200

    except Exception as e:
        logger.error(f"Synthesis error for user {user_id}: {str(e)}", exc_info=True)
        return jsonify({'error': f'Synthesis failed: {str(e)}'}), 500

@app.route('/api/usage', methods=['GET'])
@jwt_required()
def get_usage() -> tuple[dict, int]:
    """Retrieve the user's remaining character limit."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    log_user_data(user_id, 'usage_check', {'remaining_chars': user.remaining_chars})
    return jsonify({'remaining_chars': user.remaining_chars}), 200

@app.route('/api/admin/set_free_chars', methods=['POST'])
@jwt_required()
def set_free_chars() -> tuple[dict, int]:
    """Admin or self endpoint to set a user's free character limit."""
    user_id = get_jwt_identity()
    data = request.get_json()
    target_user_id = data.get('target_user_id')
    new_chars = data.get('remaining_chars', 100)
    if not target_user_id:
        return jsonify({'error': 'Target user ID is required'}), 400
    user = User.query.get(user_id)
    target_user = User.query.get(target_user_id)
    if not user or not target_user:
        return jsonify({'error': 'User not found'}), 404
    if user.id != 'Petticoat' and user.id != target_user_id:
        return jsonify({'error': 'Unauthorized'}), 403
    target_user.remaining_chars = new_chars
    db.session.commit()
    log_user_data(user_id, 'admin_set_free_chars', {
        'target_user_id': target_user_id,
        'new_remaining_chars': new_chars
    })
    return jsonify({'message': f'Free characters for {target_user_id} set to {new_chars}'}), 200

# New endpoint to get preferences
@app.route('/api/preferences', methods=['GET'])
@jwt_required()
def get_preferences():
    """Retrieve the user's current engine and voice preferences."""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    preferences = {
        'engine': user.engine,
        'voice_id': user.voice_id
    }
    return jsonify(preferences), 200

# New endpoint to set preferences
@app.route('/api/preferences', methods=['POST'])
@jwt_required()
def set_preferences():
    """Set the user's engine and voice preferences."""
    user_id = get_jwt_identity()
    data = request.get_json()
    engine = data.get('engine')
    voice_id = data.get('voice_id')
    if engine not in ['standard', 'neural']:
        return jsonify({'error': 'Invalid engine type. Use "standard" or "neural".'}), 400
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    user.engine = engine
    user.voice_id = voice_id
    db.session.commit()
    return jsonify({'message': 'Preferences updated successfully'}), 200

# New endpoint to get voices
@app.route('/api/voices', methods=['GET'])
def get_voices():
    """Retrieve the list of voices for a given engine type."""
    engine = request.args.get('engine', 'standard')
    if engine not in ['standard', 'neural']:
        return jsonify({'error': 'Invalid engine type. Use "standard" or "neural".'}), 400
    try:
        response = polly.describe_voices(Engine=engine)
        voices = response['Voices']
        return jsonify(voices), 200
    except Exception as e:
        logger.error(f"Failed to fetch voices: {str(e)}")
        return jsonify({'error': f'Failed to fetch voices: {str(e)}'}), 500

def log_user_data(user_id: str, event_type: str, additional_data: Optional[dict] = None) -> None:
    """Log user activity to S3 bucket."""
    log_key = f'logs/users/{user_id}/{event_type}_{int(time.time())}.json'
    log_data = {
        'user_id': user_id,
        'event_type': event_type,
        'timestamp': int(time.time()),
        **(additional_data or {})
    }
    try:
        s3.put_object(Bucket=bucket_name, Key=log_key, Body=json.dumps(log_data))
        logger.info(f"Logged {event_type} event for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to log data for user {user_id}: {str(e)}")

def calculate_charge(text_length: int, engine: str) -> float:
    """Calculate charge based on text length and engine type."""
    if text_length <= 100:
        return 0.00
    excess_chars = text_length - 100
    if engine == 'standard':
        charge_per_char = 0.000006
    elif engine == 'neural':
        charge_per_char = 0.000024
    else:
        raise ValueError("Invalid engine type")
    total_charge = excess_chars * charge_per_char
    if total_charge < 0.01:
        total_charge = 0.01
    return round(total_charge, 2)

if __name__ == '__main__':
    with app.app_context():
        db.drop_all()  # Drop existing tables to apply new schema
        db.create_all()  # Create tables with updated schema
    app.run(debug=True, host='0.0.0.0', port=5000)