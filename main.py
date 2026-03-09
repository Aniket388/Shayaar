import os
import json
import requests
import textwrap
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

# --- PHASE D: MEDIA ENGINEERING (THE PREMIUM ARTIST) ---
print("Drawing the beautiful text on a canvas...")

# 1. Create a 1080x1920 canvas (Slightly dark aesthetic gray instead of harsh pitch black)
width, height = 1080, 1920
img = Image.new('RGB', (width, height), color=(15, 15, 18))
draw = ImageDraw.Draw(img)

# 2. Smart Text Wrapping (Respects your original Telegram line breaks!)
raw_lines = job_text.split('\n')
formatted_lines = []
for line in raw_lines:
    # Only wrap a line if it is insanely long, otherwise leave it exactly as you wrote it
    if len(line) > 35:
        formatted_lines.extend(textwrap.wrap(line, width=35))
    else:
        formatted_lines.append(line)

final_text = "\n".join(formatted_lines)

# 3. Dynamic Font Scaling (Shrink-to-fit algorithm)
font_size = 85
font_path = "assets/fonts/Lora-VariableFont_wght.ttf"

# Keep shrinking the font until it fits comfortably inside the screen
while font_size > 30:
    font = ImageFont.truetype(font_path, font_size)
    bbox = draw.multiline_textbbox((0, 0), final_text, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    # If it fits within our safe margins (150px padding on the sides), stop shrinking!
    if text_w < (width - 300) and text_h < (height - 400):
        break
    font_size -= 4

# Calculate exact dead-center coordinates
x = (width - text_w) / 2
y = (height - text_h) / 2

# 4. Draw a subtle Drop Shadow for a premium feel
shadow_offset = 4
draw.multiline_text((x + shadow_offset, y + shadow_offset), final_text, font=font, fill=(0, 0, 0), align="center", spacing=40)

# 5. Draw the actual crisp text in off-white
draw.multiline_text((x, y), final_text, font=font, fill=(245, 245, 245), align="center", spacing=40)

img.save("temp_frame.png")

print("Image created! Now mixing audio and rendering the Reel...")

# 6. Bring in MoviePy to make the video
audio = AudioFileClip("assets/music/Lover.mp3")

if audio.duration > 12:
    audio = audio.subclip(0, 12)
audio = audio.audio_fadeout(1.5)

video = ImageClip("temp_frame.png").set_duration(12)
final_video = video.set_audio(audio)

final_video.write_videofile("shayaar_reel.mp4", fps=24, codec="libx264", audio_codec="aac", preset="ultrafast")

print("Video rendered successfully!")
sheet_queue.update_cell(job_row, 2, "VIDEO_READY")
print("Going back to sleep.")
