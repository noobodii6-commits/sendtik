
import tkinter as tk
from tkinter import messagebox
import threading
import os
import yt_dlp
import glob
import time
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload



class TikTokToYouTubeApp:
    def upload_downloaded_videos(self):
        self.status_label.config(text="Uploading all downloaded videos to YouTube (private)...")
        self.root.update()
        out_dir = "downloads"
        video_files = [f for f in os.listdir(out_dir) if f.endswith(".mp4") and not f.endswith(".mp4.part")]
        if not video_files:
            self.status_label.config(text="No downloaded videos found.")
            return
        # Authenticate YouTube API
        creds = None
        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        client_secret_file = os.path.join("client_secret", "autoclient.json")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
            youtube = build('youtube', 'v3', credentials=creds)
        except Exception as e:
            self.status_label.config(text="YouTube authentication failed.")
            messagebox.showerror("YouTube Auth Error", str(e))
            self.start_button.config(state=tk.NORMAL)
            return
        uploaded_count = 0
        for idx, filename in enumerate(video_files, 1):
            video_path = os.path.join(out_dir, filename)
            title = f"TikTok Video {filename.split('.')[0]}"
            description = ''
            tags = ['TikTok']
            body = {
                'snippet': {
                    'title': title,
                    'description': description,
                    'tags': tags,
                    'categoryId': '22',
                },
                'status': {
                    'privacyStatus': 'private',
                    'selfDeclaredMadeForKids': False
                }
            }
            self.status_label.config(text=f"Uploading {filename} ({idx}/{len(video_files)})...")
            self.root.update()
            try:
                media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
                request = youtube.videos().insert(
                    part='snippet,status',
                    body=body,
                    media_body=media
                )
                response = None
                while response is None:
                    status, response = request.next_chunk()
                uploaded_count += 1
            except Exception as e:
                print(f"Failed to upload {video_path}: {e}")
                continue

        self.status_label.config(text=f"Done! {uploaded_count} videos uploaded as private.")
        messagebox.showinfo("Done", f"Uploaded {uploaded_count} videos to YouTube as private.")
        self.start_button.config(state=tk.NORMAL)

    def __init__(self, root):
        self.root = root
        self.root.title("TikTok to YouTube Uploader")
        self.urls = []
        self.create_widgets()

    def create_widgets(self):
        self.label = tk.Label(self.root, text="TikTok to YouTube Uploader")
        self.label.pack(pady=10)

        self.start_button = tk.Button(self.root, text="Start Processing (Download + Upload)", command=self.start_processing)
        self.start_button.pack(pady=5)
        self.upload_button = tk.Button(self.root, text="Upload Downloaded Videos Only", command=self.start_upload_only)
        self.upload_button.pack(pady=5)

        self.status_label = tk.Label(self.root, text="Status: Ready.")
        self.status_label.pack(pady=10)

    def start_upload_only(self):
        self.start_button.config(state=tk.DISABLED)
        self.upload_button.config(state=tk.DISABLED)
        threading.Thread(target=self.upload_downloaded_videos).start()


    def read_urls(self):
        url_file = os.path.join("urls", "video_urls.txt")
        if not os.path.exists(url_file):
            messagebox.showerror("Error", f"URL file not found: {url_file}")
            return []
        with open(url_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]
        # Remove duplicate URLs
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                unique_urls.append(url)
                seen.add(url)
        return unique_urls


    def start_processing(self):
        self.start_button.config(state=tk.DISABLED)
        threading.Thread(target=self.process_videos).start()


    def process_videos(self):
        self.status_label.config(text="Reading URLs...")
        urls = self.read_urls()
        if not urls:
            self.status_label.config(text="No URLs found.")
            self.start_button.config(state=tk.NORMAL)
            return
        self.status_label.config(text=f"Found {len(urls)} URLs. Downloading...")
        self.root.update()

        # Download TikTok videos without watermark, skip already processed
        out_dir = "downloads"
        os.makedirs(out_dir, exist_ok=True)
        processed_file = os.path.join(out_dir, "processed_ids.txt")
        processed_ids = set()
        if os.path.exists(processed_file):
            with open(processed_file, 'r') as pf:
                processed_ids = set(line.strip() for line in pf if line.strip())
        downloaded_files = []
        url_id_pairs = []
        for idx, url in enumerate(urls, 1):
            try:
                self.status_label.after(0, lambda n=idx: self.status_label.config(text=f"Downloading video {n}/{len(urls)}..."))
                self.root.update()
                ydl_opts = {
                    'outtmpl': os.path.join(out_dir, '%(id)s.%(ext)s'),
                    'format': 'mp4',
                    'noplaylist': True,
                    'quiet': True,
                    'merge_output_format': 'mp4',
                    'postprocessors': [{
                        'key': 'FFmpegVideoRemuxer',
                        'preferedformat': 'mp4',
                    }],
                    'extractor_args': {'tiktok': ['nowatermark']},
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    video_id = info.get('id')
                    if video_id in processed_ids:
                        print(f"Skipping duplicate video: {video_id}")
                        continue
                    filename = ydl.prepare_filename(info)
                    if os.path.exists(filename):
                        downloaded_files.append(filename)
                        url_id_pairs.append((url, video_id))
            except Exception as e:
                print(f"Failed to download {url}: {e}")
                self.status_label.after(0, lambda u=url: self.status_label.config(text=f"Failed to download: {u}"))
                self.root.update()
                continue

        self.status_label.config(text=f"Downloaded {len(downloaded_files)} videos. Uploading to YouTube...")
        self.root.update()

        # Authenticate YouTube API
        creds = None
        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
        client_secret_file = os.path.join("client_secret", "autoclient.json")
        try:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
            youtube = build('youtube', 'v3', credentials=creds)
        except Exception as e:
            self.status_label.config(text="YouTube authentication failed.")
            messagebox.showerror("YouTube Auth Error", str(e))
            self.start_button.config(state=tk.NORMAL)
            return

        uploaded_count = 0
        # Store TikTok metadata for each video
        tiktok_infos = []
        for url, video_id in url_id_pairs:
            try:
                ydl_opts = {
                    'skip_download': True,
                    'quiet': True,
                    'extractor_args': {'tiktok': ['nowatermark']},
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    tiktok_infos.append(info)
            except Exception as e:
                tiktok_infos.append(None)

        for idx, ((video_path, (url, video_id)), info) in enumerate(zip(zip(downloaded_files, url_id_pairs), tiktok_infos), 1):
            self.status_label.config(text=f"Uploading video {idx}/{len(downloaded_files)} to YouTube (private)...")
            self.root.update()
            try:
                description = ''
                tags = ['TikTok']
                title = f'TikTok Video {idx}'
                if info:
                    title = info.get('title', title)
                    description = info.get('description', '')
                    tags = [tag for tag in description.split() if tag.startswith('#')]
                    if not tags:
                        tags = ['TikTok']
                body = {
                    'snippet': {
                        'title': title,
                        'description': description,
                        'tags': tags,
                        'categoryId': '22',
                    },
                    'status': {
                        'privacyStatus': 'private',
                        'selfDeclaredMadeForKids': False
                    }
                }
                media = MediaFileUpload(video_path, mimetype='video/mp4', resumable=True)
                request = youtube.videos().insert(
                    part='snippet,status',
                    body=body,
                    media_body=media
                )
                response = None
                while response is None:
                    status, response = request.next_chunk()
                uploaded_count += 1
                # Mark video as processed
                with open(processed_file, 'a') as pf:
                    pf.write(f"{video_id}\n")
            except Exception as e:
                print(f"Failed to upload {video_path}: {e}")
                continue

        self.status_label.config(text=f"Done! {uploaded_count} videos uploaded as private.")
        messagebox.showinfo("Done", f"Processed {len(urls)} videos. {uploaded_count} uploaded to YouTube as private.")
        self.start_button.config(state=tk.NORMAL)
if __name__ == "__main__":
    print("Launching TikTok to YouTube GUI...")
    print(
        """
IMPORTANT: TikTok downloading with yt-dlp now requires browser impersonation.
To enable this, follow these steps:
1. Visit: https://github.com/yt-dlp/yt-dlp#impersonation
2. Download the required browser binary (e.g., Chrome or Chromium).
3. Use yt-dlp with the --cookies or --use-binary-location and --user-agent options, or export your browser cookies.
4. You may need to run yt-dlp manually with these options to test TikTok downloads.
5. Once you confirm downloads work, you can add the necessary options to the ydl_opts in this script.
If you need help with these steps, let me know!
        """
    )
    root = tk.Tk()
    print("GUI window should now be visible. If not, check for errors or try running this script outside VS Code.")
    app = TikTokToYouTubeApp(root)
    root.mainloop()


# (Removed duplicate and stray code outside the class. All logic is now inside process_videos.)


if __name__ == "__main__":
    root = tk.Tk()
    app = TikTokToYouTubeApp(root)
    root.mainloop()
