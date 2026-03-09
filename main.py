import os
import json
import requests
import textwrap
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip

print("Waking up Shayaar Bot...")

# --- PHASE A: LOAD SECRETS ---
TELEGRAM_TOKEN = os.environ['TELEGRAM_TOKEN'].strip()
ADMIN_ID = int(os.environ['TELEGRAM_ADMIN_ID'].strip())
SHEET_ID = os.environ['SHEET_ID'].strip()
CREDS_DICT = json.loads(os.environ['GOOGLE_JSON'])

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(CREDS_DICT, scope)
client = gspread.authorize(creds)
sheet_queue = client.open_by_key(SHEET_ID).worksheet("Queue")

# --- PHASE C: FIND A PENDING JOB ---
print("Checking Queue for work...")
records = sheet_queue.get_all_records()
job_row = None
job_text = ""

for index, row in enumerate(records):
    if row.get('Status') == 'PENDING':
        job_row = index + 2
        job_text = row.get('Text')
        break

if not job_row:
    print("No PENDING jobs found. Sleeping.")
    exit(0)

print(f"Found a Shayari on row {job_row}! Locking it...")
sheet_queue.update_cell(job_row, 2, "PROCESSING")

# --- PHASE D: MEDIA ENGINEERING (THE CINEMATIC ARTIST) ---
print("Drawing the beautiful text on a canvas...")

# 1. Canvas (Cinematic rich dark background, not plain black)
width, height = 1080, 1920
img = Image.new('RGB', (width, height), color=(12, 12, 15))
draw = ImageDraw.Draw(img)

# 2. Smart Text Wrapping
raw_lines = job_text.split('\n')
formatted_lines = []
for line in raw_lines:
    if len(line) > 30:
        formatted_lines.extend(textwrap.wrap(line, width=30))
    else:
        formatted_lines.append(line)

final_text = "\n".join(formatted_lines)

# 3. Dynamic Font Scaling (Shrink-to-fit)
font_size = 90
font_path = "assets/fonts/Lora-VariableFont_wght.ttf"

while font_size > 30:
    font = ImageFont.truetype(font_path, font_size)
    bbox = draw.multiline_textbbox((0, 0), final_text, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # Keep it safely away from the edges (200px padding on left/right)
    if text_w < (width - 200) and text_h < (height - 500):
        break
    font_size -= 4

x = (width - text_w) / 2
y = (height - text_h) / 2

# 4. Cinematic Drop Shadow
shadow_offset = 5
draw.multiline_text((x + shadow_offset, y + shadow_offset), final_text, font=font, fill=(0, 0, 0), align="center", spacing=45)

# 5. Crisp Off-White Text
draw.multiline_text((x, y), final_text, font=font, fill=(240, 240, 240), align="center", spacing=45)

# 6. Subtle Watermark at the bottom
try:
    watermark_font = ImageFont.truetype(font_path, 35)
    wm_text = "Shayaar"
    wm_bbox = draw.textbbox((0, 0), wm_text, font=watermark_font)
    wm_w = wm_bbox[2] - wm_bbox[0]
    draw.text(((width - wm_w) / 2, height - 150), wm_text, font=watermark_font, fill=(100, 100, 100))
except:
    pass

img.save("temp_frame.png")
print("Image created! Now mixing audio and rendering the Reel...")

# --- NEW AUDIO LOGIC ---
music_dir = "assets/music/"
all_music = [f for f in os.listdir(music_dir) if f.endswith('.mp3')]

if not all_music:
    print("ERROR: No .mp3 files found!")
    exit(1)

# Pick a random song
random_track = random.choice(all_music)
print(f"Selected Track: {random_track}")
audio = AudioFileClip(os.path.join(music_dir, random_track))

# Set exact duration to 30 seconds
target_duration = 30

if audio.duration > target_duration:
    # Pick a random starting point in the song!
    max_start = audio.duration - target_duration
    random_start = random.uniform(0, max_start)
    audio = audio.subclip(random_start, random_start + target_duration)
else:
    # If the song is shorter than 30s, use whatever length it is
    target_duration = audio.duration

# Smooth fade in and fade out
audio = audio.audio_fadein(1.0).audio_fadeout(2.0)

# Merge video and audio
video = ImageClip("temp_frame.png").set_duration(target_duration)
final_video = video.set_audio(audio)

final_video.write_videofile("shayaar_reel.mp4", fps=24, codec="libx264", audio_codec="aac", preset="ultrafast")

print("Video rendered successfully!")
sheet_queue.update_cell(job_row, 2, "VIDEO_READY")
print("Going back to sleep.")
