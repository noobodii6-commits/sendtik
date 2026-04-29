from flask import Flask, render_template_string, request, redirect, url_for, flash, session
import zipfile
from werkzeug.utils import secure_filename
import os
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Change this in production

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
CLIENT_SECRET_FILE = os.path.join('client_secret', 'autoclient.json')
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

HTML_FORM = '''
<!doctype html>
<title>YouTube Uploader</title>
<h2>Upload Videos to YouTube (Private, Scheduled)</h2>
<form method="post" enctype="multipart/form-data">
    <label>Select video files (multiple allowed) or a ZIP archive:</label><br>
    <input type="file" name="videos" multiple><br>
    <input type="file" name="zipfile"><br><br>
    <button type="submit">Upload and Schedule</button>
</form>
<p>{{ message }}</p>
'''


import pathlib
import datetime
import json
from urllib.parse import urlparse, urljoin

def get_redirect_uri():
    # Render sets the public URL as RENDER_EXTERNAL_URL
    import os
    base_url = os.environ.get('RENDER_EXTERNAL_URL')
    if not base_url:
        # fallback for local dev
        base_url = 'http://localhost:5000'
    return urljoin(base_url, '/oauth2callback')

def is_logged_in():
    return 'credentials' in session

def get_youtube_service():
    creds = Credentials(**session['credentials'])
    return build('youtube', 'v3', credentials=creds)

@app.route('/authorize')
def authorize():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=get_redirect_uri()
    )
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )
    session['state'] = state
    return redirect(authorization_url)

@app.route('/oauth2callback')
def oauth2callback():
    flow = Flow.from_client_secrets_file(
        CLIENT_SECRET_FILE,
        scopes=SCOPES,
        redirect_uri=get_redirect_uri()
    )
    flow.fetch_token(authorization_response=request.url)
    creds = flow.credentials
    session['credentials'] = {
        'token': creds.token,
        'refresh_token': creds.refresh_token,
        'token_uri': creds.token_uri,
        'client_id': creds.client_id,
        'client_secret': creds.client_secret,
        'scopes': creds.scopes
    }
    return redirect(url_for('upload_videos'))

@app.route('/', methods=['GET', 'POST'])
def upload_videos():
    message = ''
    if request.method == 'POST':
        saved_files = []
        # Handle individual video files
        if 'videos' in request.files:
            files = request.files.getlist('videos')
            for file in files:
                if file and file.filename.lower().endswith('.mp4'):
                    filename = secure_filename(file.filename)
                    save_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(save_path)
                    saved_files.append(save_path)
        # Handle ZIP file
        if 'zipfile' in request.files:
            zfile = request.files['zipfile']
            if zfile and zfile.filename.lower().endswith('.zip'):
                zip_path = os.path.join(UPLOAD_FOLDER, secure_filename(zfile.filename))
                zfile.save(zip_path)
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    for member in zip_ref.namelist():
                        if member.lower().endswith('.mp4'):
                            extracted_path = zip_ref.extract(member, UPLOAD_FOLDER)
                            saved_files.append(extracted_path)
                os.remove(zip_path)
        if not saved_files:
            message = 'No valid video files uploaded.'
            return render_template_string(HTML_FORM, message=message)

        # --- OAuth for web server ---
        if not is_logged_in():
            return redirect(url_for('authorize'))
        try:
            youtube = get_youtube_service()
        except Exception as e:
            message = f'YouTube authentication failed: {e}'
            return render_template_string(HTML_FORM, message=message)

        uploaded_count = 0
        now = datetime.datetime.utcnow()
        schedule_time = now + datetime.timedelta(minutes=1)  # Start 1 minute from now for first video
        for idx, video_path in enumerate(saved_files):
            title = f"Uploaded Video {idx+1}"
            body = {
                'snippet': {
                    'title': title,
                    'description': '',
                    'tags': ['TikTok'],
                    'categoryId': '22',
                },
                'status': {
                    'privacyStatus': 'private',
                    'selfDeclaredMadeForKids': False,
                    'publishAt': (schedule_time + datetime.timedelta(hours=idx)).isoformat("T") + "Z"
                }
            }
            try:
                media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
                request_youtube = youtube.videos().insert(
                    part='snippet,status',
                    body=body,
                    media_body=media
                )
                response = None
                while response is None:
                    status, response = request_youtube.next_chunk()
                uploaded_count += 1
            except Exception as e:
                print(f"Failed to upload {video_path}: {e}")
                continue
        message = f"Done! {uploaded_count} videos uploaded and scheduled 1 hour apart."
    return render_template_string(HTML_FORM, message=message)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
