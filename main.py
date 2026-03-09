import os
import json
import requests
import textwrap
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, VideoFileClip, CompositeVideoClip, ColorClip

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

# --- PHASE D: MEDIA ENGINEERING (THE CINEMATIC COMPOSITOR) ---
print("Designing the transparent text layer...")
width, height = 1080, 1920

# 1. Create a transparent canvas, but fill it with a 40% dark overlay.
# This makes any background video underneath look moody and helps the white text pop!
img = Image.new('RGBA', (width, height), color=(0, 0, 0, 120))
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

# 3. Dynamic Font Scaling
font_size = 90
font_path = "assets/fonts/Lora-VariableFont_wght.ttf"

while font_size > 30:
    font = ImageFont.truetype(font_path, font_size)
    bbox = draw.multiline_textbbox((0, 0), final_text, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    if text_w < (width - 200) and text_h < (height - 500):
        break
    font_size -= 4

x = (width - text_w) / 2
y = (height - text_h) / 2

# 4. Draw Drop Shadow & Text
shadow_offset = 5
draw.multiline_text((x + shadow_offset, y + shadow_offset), final_text, font=font, fill=(0, 0, 0, 255), align="center", spacing=45)
draw.multiline_text((x, y), final_text, font=font, fill=(245, 245, 245, 255), align="center", spacing=45)

# 5. Watermark
try:
    watermark_font = ImageFont.truetype(font_path, 35)
    wm_text = "Shayaar"
    wm_w = draw.textbbox((0, 0), wm_text, font=watermark_font)[2]
    draw.text(((width - wm_w) / 2, height - 150), wm_text, font=watermark_font, fill=(150, 150, 150, 200))
except:
    pass

img.save("text_layer.png")
print("Text layer ready! Mixing video, audio, and elegant fades...")

# --- VIDEO BACKGROUND LOGIC ---
target_duration = 30
bg_dir = "assets/backgrounds/"

# Check if you uploaded any videos
try:
    bg_files = [f for f in os.listdir(bg_dir) if f.endswith(('.mp4', '.mov'))]
except:
    bg_files = []

if bg_files:
    random_bg = random.choice(bg_files)
    print(f"Using animated background: {random_bg}")
    bg_clip = VideoFileClip(os.path.join(bg_dir, random_bg))
    
    # Loop it if it's too short, or cut it if it's too long
    if bg_clip.duration < target_duration:
        from moviepy.video.fx.all import loop
        bg_clip = bg_clip.fx(loop, duration=target_duration)
    else:
        bg_clip = bg_clip.subclip(0, target_duration)
    
    # Force it to fit Instagram's 1080x1920 size just in case it's the wrong shape
    bg_clip = bg_clip.resize(newsize=(1080, 1920))
else:
    print("No background video found. Using classy dark solid color.")
    bg_clip = ColorClip(size=(1080, 1920), color=[15, 15, 18], duration=target_duration)

# --- APPLY ANIMATION (ELEGANT TEXT FADE-IN) ---
# The text will slowly fade into existence over 3 seconds
text_clip = ImageClip("text_layer.png").set_duration(target_duration).crossfadein(3.0)

# Merge the background and the animated text
final_video = CompositeVideoClip([bg_clip, text_clip])

# --- AUDIO LOGIC ---
music_dir = "assets/music/"
all_music = [f for f in os.listdir(music_dir) if f.endswith('.mp3')]

if all_music:
    random_track = random.choice(all_music)
    audio = AudioFileClip(os.path.join(music_dir, random_track))
    
    if audio.duration > target_duration:
        max_start = audio.duration - target_duration
        random_start = random.uniform(0, max_start)
        audio = audio.subclip(random_start, random_start + target_duration)
    
    audio = audio.audio_fadein(2.0).audio_fadeout(3.0)
    final_video = final_video.set_audio(audio)

# Fade the entire video in and out beautifully
final_video = final_video.fadein(1.0).fadeout(2.0)

# Render the masterpiece
final_video.write_videofile("shayaar_reel.mp4", fps=24, codec="libx264", audio_codec="aac", preset="ultrafast")

print("Masterpiece rendered successfully!")
sheet_queue.update_cell(job_row, 2, "VIDEO_READY")
print("Going back to sleep.")
