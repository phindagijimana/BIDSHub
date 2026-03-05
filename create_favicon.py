#!/usr/bin/env python3
"""Create a favicon for BIDSHub."""

from PIL import Image, ImageDraw, ImageFont

# Create a 64x64 image with navy blue background
img = Image.new('RGB', (64, 64), color='#002d72')  # Navy blue
draw = ImageDraw.Draw(img)

# Try to use a built-in font, fallback to default if not available
try:
    # Try to load a truetype font
    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
except:
    # Fallback to default font
    font = ImageFont.load_default()

# Draw "BH" in white centered
text = "BH"
# Get text bounding box
bbox = draw.textbbox((0, 0), text, font=font)
text_width = bbox[2] - bbox[0]
text_height = bbox[3] - bbox[1]

# Calculate position to center the text
x = (64 - text_width) // 2
y = (64 - text_height) // 2 - 2  # Adjust slightly up

# Draw white text
draw.text((x, y), text, fill='white', font=font)

# Save as PNG (Streamlit can use PNG as favicon)
img.save('favicon.png', 'PNG')
print("Created favicon.png")

# Also create an ICO file for browsers
img_ico = img.resize((32, 32), Image.Resampling.LANCZOS)
img_ico.save('favicon.ico', format='ICO')
print("Created favicon.ico")
