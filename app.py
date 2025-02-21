from flask import Flask, request, jsonify
import boto3
import json

app = Flask(__name__)

@app.route('/synthesize', methods=['POST'])
def synthesize():
    data = request.get_json()
    user_id = data['user_id']
    text_to_speech = data['text_to_speech']

    polly = boto3.client('polly')
    s3 = boto3.client('s3')

    bucket_name = f'user-bucket-{user_id}'
    audio_file_name = 'audio/speech.mp3'
    speech_marks_file_name = 'speech_marks/speech_marks.json'
    logging_bucket = f'tts-neural-reader-logs-{user_id}'

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

    bucket_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": "*",
                "Action": ["s3:GetObject"],
                "Resource": f"arn:aws:s3:::{bucket_name}/*"
            }
        ]
    }

    try:
        s3.create_bucket(Bucket=bucket_name)
        s3.put_public_access_block(
            Bucket=bucket_name,
            PublicAccessBlockConfiguration={
                'BlockPublicAcls': False,
                'IgnorePublicAcls': False,
                'BlockPublicPolicy': False,
                'RestrictPublicBuckets': False
            }
        )
        s3.put_bucket_versioning(
            Bucket=bucket_name,
            VersioningConfiguration={
                'Status': 'Enabled'
            }
        )
        s3.put_bucket_cors(
            Bucket=bucket_name,
            CORSConfiguration=cors_configuration
        )
        s3.put_bucket_policy(
            Bucket=bucket_name,
            Policy=json.dumps(bucket_policy)
        )

        audio_response = polly.synthesize_speech(
            Text=text_to_speech,
            OutputFormat='mp3',
            VoiceId='Joanna'
        )
        audio_stream = audio_response['AudioStream'].read()
        s3.put_object(Bucket=bucket_name, Key=audio_file_name, Body=audio_stream)

        speech_marks_response = polly.synthesize_speech(
            Text=text_to_speech,
            OutputFormat='json',
            VoiceId='Joanna',
            SpeechMarkTypes=['word']
        )
        speech_marks = speech_marks_response['AudioStream'].read()
        s3.put_object(Bucket=bucket_name, Key=speech_marks_file_name, Body=speech_marks)

        try:
            s3.head_bucket(Bucket=logging_bucket)
        except s3.exceptions.ClientError as e:
            error_code = int(e.response['Error']['Code'])
            if error_code == 404:
                s3.create_bucket(Bucket=logging_bucket)

        s3.put_bucket_logging(
            Bucket=bucket_name,
            BucketLoggingStatus={
                'LoggingEnabled': {
                    'TargetBucket': logging_bucket,
                    'TargetPrefix': f'{bucket_name}/'
                }
            }
        )
        s3.put_bucket_tagging(
            Bucket=bucket_name,
            Tagging={
                'TagSet': [
                    {
                        'Key': 'UserID',
                        'Value': user_id
                    }
                ]
            }
        )

        return jsonify({'message': 'Files successfully uploaded and bucket created!'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)