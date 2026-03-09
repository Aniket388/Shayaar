import os
import json
import requests
import textwrap
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip

print("Waking up Shayaar Bot...")

# --- PHASE A & B: LOAD SECRETS & CHECK TELEGRAM ---
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
ADMIN_ID = int(os.environ['TELEGRAM_ADMIN_ID'].strip())
SHEET_ID = os.environ['SHEET_ID'].strip()
CREDS_DICT = json.loads(os.environ['GOOGLE_JSON'])

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(CREDS_DICT, scope)
client = gspread.authorize(creds)
sheet_queue = client.open_by_key(SHEET_ID).worksheet("Queue")

# (We are skipping the Telegram check in this run just to focus on making the video!)

# --- PHASE C: FIND A PENDING JOB ---
print("Checking Queue for work...")
records = sheet_queue.get_all_records()
job_row = None
job_text = ""

# Look for the first row that says PENDING
for index, row in enumerate(records):
    if row.get('Status') == 'PENDING':
        job_row = index + 2  # +2 because row 1 is headers
        job_text = row.get('Text')
        break

if not job_row:
    print("No PENDING jobs found. Sleeping.")
    exit(0)

print(f"Found a Shayari on row {job_row}! Locking it...")
sheet_queue.update_cell(job_row, 2, "PROCESSING")

# --- PHASE D: MEDIA ENGINEERING (THE ARTIST) ---
print("Drawing the text on a canvas...")

# 1. Create a 1080x1920 black image
width, height = 1080, 1920
img = Image.new('RGB', (width, height), color=(0, 0, 0))
draw = ImageDraw.Draw(img)

# 2. Load your font and wrap the text so it fits the screen
font = ImageFont.truetype("assets/fonts/type.ttf", 60)
wrapped_text = "\n".join(textwrap.wrap(job_text, width=30))

# 3. Center the text mathematically
bbox = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align="center")
text_w = bbox[2] - bbox[0]
text_h = bbox[3] - bbox[1]
x = (width - text_w) / 2
y = (height - text_h) / 2

# 4. Draw it!
draw.multiline_text((x, y), wrapped_text, font=font, fill=(255, 255, 255), align="center", spacing=20)
img.save("temp_frame.png")

print("Image created! Now mixing audio and rendering the Reel...")

# 5. Bring in MoviePy to make the video
audio = AudioFileClip("assets/music/Lover.mp3")

# Cut the audio to exactly 12 seconds and add a smooth fadeout
if audio.duration > 12:
    audio = audio.subclip(0, 12)
audio = audio.audio_fadeout(1.5)

# Combine the image and the audio
video = ImageClip("temp_frame.png").set_duration(12)
final_video = video.set_audio(audio)

# Render the final .mp4 file (Using ultrafast to save GitHub's CPU)
final_video.write_videofile("shayaar_reel.mp4", fps=24, codec="libx264", audio_codec="aac", preset="ultrafast")

print("Video rendered successfully!")
sheet_queue.update_cell(job_row, 2, "VIDEO_READY")
print("Going back to sleep.")
