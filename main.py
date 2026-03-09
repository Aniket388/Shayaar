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
sheet_config = client.open_by_key(SHEET_ID).worksheet("Config")

# --- PHASE B: TELEGRAM INGESTION ---
print("Checking Telegram for new Shayaris...")
try:
    cell = sheet_config.find("last_telegram_offset")
    last_offset = sheet_config.cell(cell.row, cell.col + 1).value
    last_offset = int(last_offset) if last_offset else 0
except:
    last_offset = 0

url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates?offset={last_offset + 1}&timeout=10"
response = requests.get(url).json()
updates = response.get("result", [])

if updates:
    highest_offset = last_offset
    for update in updates:
        highest_offset = max(highest_offset, update['update_id'])
        if 'message' in update and 'text' in update['message']:
            user_id = update['message']['from']['id']
            text = update['message']['text']
            if user_id == ADMIN_ID:
                print(f"Authorized! Adding to sheet: {text[:20]}...")
                sheet_queue.append_row([text, "PENDING", ""])
            else:
                print(f"Ignored message from ID: {user_id}")
    
    if highest_offset > last_offset:
        try:
            sheet_config.update_cell(cell.row, cell.col + 1, highest_offset)
        except:
            sheet_config.append_row(["last_telegram_offset", highest_offset])
        print("Updated the Config sheet with new Telegram offset.")
else:
    print("No new messages from Telegram.")

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
img = Image.new('RGBA', (width, height), color=(0, 0, 0, 120))
draw = ImageDraw.Draw(img)

# FIX 1: The Golden Ratio for Vertical Reels (Wrap at 28 chars so it never hits the edges)
raw_lines = job_text.split('\n')
formatted_lines = []
for line in raw_lines:
    if len(line) > 28:  
        formatted_lines.extend(textwrap.wrap(line, width=28))
    else:
        formatted_lines.append(line)
final_text = "\n".join(formatted_lines)

font_size = 100
font_path = "assets/fonts/Lora-VariableFont_wght.ttf"
dynamic_spacing = 20 

# FIX 2: Bulletproof Shrink-to-Fit (Allow it to shrink as small as size 15 if necessary)
while font_size > 15:
    font = ImageFont.truetype(font_path, font_size)
    dynamic_spacing = max(10, int(font_size * 0.3)) 
    
    bbox = draw.multiline_textbbox((0, 0), final_text, font=font, align="center", spacing=dynamic_spacing)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # Must fit safely inside the screen margins
    if text_w < (width - 280) and text_h < (height - 600):
        break
    font_size -= 2

x = (width - text_w) / 2
y = ((height - text_h) / 2) - 150  

shadow_offset = max(3, int(font_size * 0.06))  
draw.multiline_text((x + shadow_offset, y + shadow_offset), final_text, font=font, fill=(0, 0, 0, 255), align="center", spacing=dynamic_spacing)
draw.multiline_text((x, y), final_text, font=font, fill=(245, 245, 245, 255), align="center", spacing=dynamic_spacing)

img.save("text_layer.png")
print("Text layer ready! Mixing video, audio, and elegant fades...")

target_duration = 30
bg_dir = "assets/backgrounds/"
try:
    bg_files = [f for f in os.listdir(bg_dir) if f.endswith(('.mp4', '.mov'))]
except:
    bg_files = []

if bg_files:
    random_bg = random.choice(bg_files)
    print(f"Using animated background: {random_bg}")
    bg_clip = VideoFileClip(os.path.join(bg_dir, random_bg))
    if bg_clip.duration < target_duration:
        from moviepy.video.fx.all import loop
        bg_clip = bg_clip.fx(loop, duration=target_duration)
    else:
        bg_clip = bg_clip.subclip(0, target_duration)
    bg_clip = bg_clip.resize(newsize=(1080, 1920))
else:
    print("No background video found. Using classy dark solid color.")
    bg_clip = ColorClip(size=(1080, 1920), color=[15, 15, 18], duration=target_duration)

text_clip = ImageClip("text_layer.png").set_duration(target_duration).crossfadein(3.0)
final_video = CompositeVideoClip([bg_clip, text_clip])

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

final_video = final_video.fadein(1.0).fadeout(2.0)
final_video.write_videofile("shayaar_reel.mp4", fps=24, codec="libx264", audio_codec="aac", preset="ultrafast")

print("Masterpiece rendered successfully!")
sheet_queue.update_cell(job_row, 2, "VIDEO_READY")
print("Going back to sleep.")
