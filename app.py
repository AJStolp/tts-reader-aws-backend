from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify
import boto3
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////home/ec2-user/tts-reader-aws_backend/database.db'
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'default-secret-key')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1) 
db = SQLAlchemy(app)
jwt = JWTManager(app)

class User(db.Model):
    id = db.Column(db.String, primary_key=True)
    remaining_chars = db.Column(db.Integer, default=100)
    password_hash = db.Column(db.String(128))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

try:
    region = os.environ['AWS_REGION']
except KeyError:
    raise ValueError("AWS_REGION environment variable is not set")

try:
    s3 = boto3.client('s3', region_name=region)
    polly = boto3.client('polly', region_name=region)
except Exception as e:
    raise ValueError(f"Failed to create Boto3 clients: {e}")

def generate_presigned_url(bucket, key, expiration=3600):
    url = s3.generate_presigned_url('get_object',
                                    Params={'Bucket': bucket, 'Key': key},
                                    expires_in=expiration)
    return url

main_bucket_name = 'my-app-bucket'
logging_bucket_name = 'my-app-logging-bucket'

def setup_bucket():
    try:
        s3.head_bucket(Bucket=main_bucket_name)
    except s3.exceptions.ClientError as e:
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            s3.create_bucket(Bucket=main_bucket_name)
            s3.put_public_access_block(
                Bucket=main_bucket_name,
                PublicAccessBlockConfiguration={'BlockPublicAcls': True, 'IgnorePublicAcls': True, 'BlockPublicPolicy': True, 'RestrictPublicBuckets': True}
            )
            s3.put_bucket_versioning(
                Bucket=main_bucket_name,
                VersioningConfiguration={'Status': 'Enabled'}
            )
            cors_configuration = {
                'CORSRules': [
                    {
                        'AllowedHeaders': ['Authorization'],
                        'AllowedMethods': ['GET', 'HEAD', 'PUT', 'POST', 'DELETE'],
                        'AllowedOrigins': ['*'],
                        'ExposeHeaders': ['ETag'],
                        'MaxAgeSeconds': 3000
                    }
                ]
            }
            s3.put_bucket_cors(Bucket=main_bucket_name, CORSConfiguration=cors_configuration)
            
            # Ensure logging bucket exists
            try:
                s3.head_bucket(Bucket=logging_bucket_name)
            except s3.exceptions.ClientError as e:
                error_code = int(e.response['Error']['Code'])
                if error_code == 404:
                    s3.create_bucket(Bucket=logging_bucket_name)
            
            s3.put_bucket_logging(
                Bucket=main_bucket_name,
                BucketLoggingStatus={'LoggingEnabled': {'TargetBucket': logging_bucket_name, 'TargetPrefix': ''}}
            )

setup_bucket()

# Registration endpoint
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

# Login endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    user_id = data['user_id']
    password = data['password']
    
    user = User.query.get(user_id)
    if user and user.check_password(password):
        access_token = create_access_token(identity=user_id)
        return jsonify({'token': access_token}), 200
    return jsonify({'error': 'Invalid credentials'}), 401

# Synthesize endpoint
@app.route('/synthesize', methods=['POST'])
@jwt_required()
def synthesize():
    user_id = get_jwt_identity()
    data = request.get_json()
    text_to_speech = data['text_to_speech']
    voice_id = data.get('voice_id', 'Ivy')
    text_length = len(text_to_speech)

    user = User.query.get(user_id)
    if user is None:
        return jsonify({'error': 'User not found'}), 404

    if text_length > user.remaining_chars:
        return jsonify({'message': 'User has exceeded their character limit'}), 403

    try:
        audio_file_key = f'users/{user_id}/audio/speech.mp3'
        speech_marks_file_key = f'users/{user_id}/speech_marks/speech_marks.json'

        audio_response = polly.synthesize_speech(
            Text=text_to_speech,
            OutputFormat='mp3',
            VoiceId=voice_id,
            Engine='neural'
        )
        audio_stream = audio_response['AudioStream'].read()
        s3.put_object(Bucket=main_bucket_name, Key=audio_file_key, Body=audio_stream)

        speech_marks_response = polly.synthesize_speech(
            Text=text_to_speech,
            OutputFormat='json',
            VoiceId=voice_id,
            SpeechMarkTypes=['word'],
            Engine='neural'
        )
        speech_marks = speech_marks_response['AudioStream'].read()
        s3.put_object(Bucket=main_bucket_name, Key=speech_marks_file_key, Body=speech_marks)

        audio_url = generate_presigned_url(main_bucket_name, audio_file_key)
        speech_marks_url = generate_presigned_url(main_bucket_name, speech_marks_file_key)

        user.remaining_chars -= text_length
        db.session.commit()

        return jsonify({'audio_url': audio_url, 'speech_marks_url': speech_marks_url}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)