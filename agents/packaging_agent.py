"""
Packaging Agent — Generates titles, thumbnails, and descriptions.

Takes processed clips and creates a complete "posting package":
title options, thumbnail with text overlay, description, hashtags.
"""

import os
import subprocess
import json
import random
from PIL import Image, ImageDraw, ImageFont


# --- Title Generation ---
# Template-based title generation using transcript content and clip signals

TITLE_TEMPLATES = [
    "{hook} — {topic}",
    "{topic} | {name}",
    "When {event}...",
    "{name}: {insight}",
    "The truth about {topic}",
    "{name} breaks down {topic}",
    "What nobody tells you about {topic}",
    "{name} gets real about {topic}",
    "{topic} explained in {duration} seconds",
    "{hook}",
    "Wait until you hear {topic}...",
    "{name}: '{quote}'",
]

QUOTE_TEMPLATES = [
    "'{quote}'",
    '"{quote}" — {name}',
    "{name} drops this: {quote}",
]

HASHTAG_POOL = [
    "#shorts", "#podcast", "#viral", "#fyp", "#foryou", "#explore",
    "#interview", "#mindset", "#motivation", "#business", "#entrepreneur",
    "#truth", "#realtalk", "#wisdom", "#clip", "#mustwatch",
]


def generate_titles(clip, agent_name="Clip Scout"):
    """Generate 5 title options for a clip."""
    text = clip.get("text", "")
    words = text.split()
    
    # Extract key phrases
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 10]
    
    titles = []
    
    # Strategy 1: Use first strong sentence as title
    if sentences:
        first = sentences[0]
        if len(first) <= 80:
            titles.append(first[:80])
        else:
            # Take first few words
            titles.append(" ".join(first.split()[:10]) + "...")
    
    # Strategy 2: Extract a quotable phrase
    if sentences:
        # Find shortest punchy sentence
        short_sents = sorted([s for s in sentences if 15 <= len(s) <= 60], key=len)
        if short_sents:
            titles.append(short_sents[0][:80])
    
    # Strategy 3: Question-based title
    question_sent = None
    for s in sentences:
        if "?" in s:
            question_sent = s
            break
    if question_sent:
        titles.append(question_sent[:80])
    
    # Strategy 4: Topic + curiosity gap
    # Find the most frequent meaningful word
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "its", "our", "their", "this", "that", "these", "those", "what", "which", "who", "whom", "so", "if", "because", "as", "until", "while", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "from", "up", "down", "out", "off", "over", "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", "how", "all", "each", "every", "both", "few", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "than", "too", "very", "just", "also"}
    meaningful_words = [w.lower().strip(".,!?\"'") for w in words if w.lower().strip(".,!?\"'") not in stop_words and len(w) > 3]
    
    if meaningful_words:
        word_freq = Counter(meaningful_words)
        top_word = word_freq.most_common(1)[0][0]
        
        curiosity_titles = [
            f"What nobody tells you about {top_word}",
            f"The {top_word} conversation everyone needs to hear",
            f"This changed how I think about {top_word}",
        ]
        titles.extend(curiosity_titles[:2])
    
    # Deduplicate and limit to 5
    seen = set()
    unique_titles = []
    for t in titles:
        if t.lower() not in seen and len(t) > 5:
            seen.add(t.lower())
            unique_titles.append(t)
    
    # Fill remaining slots with template-based titles
    while len(unique_titles) < 5:
        template = random.choice(TITLE_TEMPLATES)
        topic = meaningful_words[0] if meaningful_words else "this"
        t = template.format(
            hook=sentences[0][:40] if sentences else "Wait for this",
            topic=topic,
            name=agent_name,
            event=topic,
            insight=sentences[0][:30] if sentences else "this changes everything",
            quote=sentences[0][:40] if sentences else "this is important",
            duration=int(clip.get("duration", 60)),
        )
        if t.lower() not in seen:
            seen.add(t.lower())
            unique_titles.append(t)
    
    return unique_titles[:5]


def generate_thumbnail(source_path, clip, job_dir, clip_id):
    """
    Extract the best frame and overlay thumbnail text.
    
    source_path: path to source video
    clip: candidate dict
    job_dir: directory for this job
    clip_id: unique identifier
    
    returns: path to generated thumbnail
    """
    thumb_dir = os.path.join(job_dir, "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)
    
    # Extract a frame near the middle of the clip
    mid_time = (clip["start"] + clip["end"]) / 2
    frame_path = os.path.join(thumb_dir, f"clip_{clip_id}_frame.png")
    
    extract_command = [
        "ffmpeg", "-y",
        "-ss", str(mid_time),
        "-i", source_path,
        "-frames:v", "1",
        "-q:v", "2",
        frame_path,
    ]
    subprocess.run(extract_command, capture_output=True, timeout=30)
    
    if not os.path.exists(frame_path):
        return None
    
    # Create thumbnail with text overlay
    thumbnail_path = os.path.join(thumb_dir, f"clip_{clip_id}.jpg")
    
    try:
        create_thumbnail_with_text(frame_path, thumbnail_path, clip)
    except Exception:
        # Fall back to just the frame
        if os.path.exists(frame_path):
            os.rename(frame_path, thumbnail_path)
    
    # Clean up frame
    if os.path.exists(frame_path) and frame_path != thumbnail_path:
        os.remove(frame_path)
    
    return f"thumbnails/clip_{clip_id}.jpg" if os.path.exists(thumbnail_path) else None


def create_thumbnail_with_text(frame_path, output_path, clip):
    """Create a thumbnail with bold text overlay."""
    img = Image.open(frame_path)
    
    # Resize to 1280x720 (16:9 YouTube standard)
    img = img.resize((1280, 720), Image.LANCZOS)
    
    # Darken the bottom third for text readability
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw_overlay = ImageDraw.Draw(overlay)
    
    # Gradient overlay at bottom
    for y in range(450, 720):
        alpha = int((y - 450) / 270 * 180)
        draw_overlay.rectangle([0, y, 1280, y + 1], fill=(0, 0, 0, alpha))
    
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(img)
    
    # Try to load a bold font
    font_paths = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    
    font_large = None
    font_small = None
    
    for fp in font_paths:
        if os.path.exists(fp):
            font_large = ImageFont.truetype(fp, 48)
            font_small = ImageFont.truetype(fp, 28)
            break
    
    if not font_large:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Generate thumbnail text from clip
    text = clip.get("text", "")
    sentences = [s.strip() for s in text.split(".") if len(s.strip()) > 10]
    
    # Pick the punchiest short phrase
    thumb_text = ""
    if sentences:
        # Find a short, punchy sentence
        short_sents = sorted([s for s in sentences if 10 <= len(s) <= 50], key=len)
        if short_sents:
            thumb_text = short_sents[0].upper()
        else:
            thumb_text = " ".join(sentences[0].split()[:8]).upper() + "..."
    
    if not thumb_text:
        thumb_text = "WAIT FOR THIS"
    
    # Word-wrap the text
    words = thumb_text.split()
    lines = []
    current_line = []
    max_chars = 22
    
    for word in words:
        test_line = " ".join(current_line + [word])
        if len(test_line) <= max_chars:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(" ".join(current_line))
    
    # Draw text with outline
    y = 520
    for line in lines[:3]:  # Max 3 lines
        # Draw outline (shadow)
        for dx in range(-3, 4, 2):
            for dy in range(-3, 4, 2):
                draw.text((640 + dx, y + dy), line, font=font_large, fill=(0, 0, 0, 255), anchor="mm")
        
        # Draw main text
        draw.text((640, y), line, font=font_large, fill=(255, 200, 0, 255), anchor="mm")
        y += 55
    
    # Save as JPEG
    img.convert("RGB").save(output_path, "JPEG", quality=95)


def generate_description(clip):
    """Generate a description with hashtags for the clip."""
    text = clip.get("text", "")
    
    # Extract key words for hashtags
    words = text.split()
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us", "them", "my", "your", "his", "its", "our", "their", "this", "that", "these", "those", "what", "which", "who", "whom", "so", "if", "because", "as", "about", "into", "through", "during", "before", "after", "from", "up", "down", "out", "off", "over", "under", "again", "then", "here", "there", "when", "where", "why", "how", "all", "each", "every", "both", "more", "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "than", "too", "very", "just", "also"}
    
    meaningful = [w.lower().strip(".,!?\"'") for w in words if w.lower().strip(".,!?\"'") not in stop_words and len(w) > 4]
    
    # Pick 3-5 relevant hashtags
    from collections import Counter
    word_freq = Counter(meaningful)
    top_words = [w[0] for w in word_freq.most_common(3)]
    
    # Build hashtag set
    hashtags = ["#shorts", "#podcast", "#viral"]
    for w in top_words:
        hashtags.append(f"#{w}")
    
    # Add a couple random ones
    hashtags.extend(random.sample(HASHTAG_POOL, min(3, len(HASHTAG_POOL))))
    
    # Deduplicate
    seen = set()
    unique_tags = []
    for h in hashtags:
        if h not in seen:
            seen.add(h)
            unique_tags.append(h)
    
    return " ".join(unique_tags[:8])


# Import Counter at module level
from collections import Counter


def generate_text_thumbnail(clip, job_dir, clip_id):
    """
    Generate a thumbnail with text overlay on a gradient background.
    Used in demo mode when no real video frame is available.
    Fast, reliable, always produces a usable thumbnail.
    """
    thumb_dir = os.path.join(job_dir, "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)
    
    thumbnail_path = os.path.join(thumb_dir, f"clip_{clip_id}.jpg")
    
    # Create a 1280x720 thumbnail with gradient background and text
    from PIL import Image, ImageDraw, ImageFont
    
    # Dark gradient background
    img = Image.new("RGB", (1280, 720), (26, 25, 22))
    draw = ImageDraw.Draw(img)
    
    # Draw a gradient effect with rectangles
    for y in range(720):
        r = int(26 + (y / 720) * 20)
        g = int(25 + (y / 720) * 15)
        b = int(22 + (y / 720) * 10)
        draw.rectangle([0, y, 1280, y + 1], fill=(r, g, b))
    
    # Add accent bar at top
    draw.rectangle([0, 0, 1280, 6], fill=(245, 166, 35))
    
    # Load fonts
    font_paths = [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    
    font_large = None
    font_med = None
    font_small = None
    
    for fp in font_paths:
        if os.path.exists(fp):
            font_large = ImageFont.truetype(fp, 52)
            font_med = ImageFont.truetype(fp, 36)
            font_small = ImageFont.truetype(fp, 24)
            break
    
    if not font_large:
        font_large = ImageFont.load_default()
        font_med = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Extract clip text for thumbnail
    text = clip.get("text", "")
    # Split on sentence-ending punctuation, not just periods
    import re
    raw_sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 8]
    
    # Find a punchy short phrase for the thumbnail
    thumb_text = ""
    if sentences:
        # Prefer sentences between 10-50 chars — punchy and readable
        short_sents = [s for s in sentences if 10 <= len(s) <= 50]
        if short_sents:
            # Pick the one with the most impact words
            impact_words = ["never", "always", "secret", "nobody", "wrong", "fail", "best", "worst", "truth", "stop"]
            short_sents.sort(key=lambda s: -sum(1 for w in impact_words if w in s.lower()))
            thumb_text = short_sents[0].upper()
        else:
            # Fall back to first 6 words of first sentence
            first_words = sentences[0].split()[:6]
            thumb_text = " ".join(first_words).upper()
    
    if not thumb_text or len(thumb_text) < 5:
        # Ultimate fallback — use clip number and score
        score = clip.get("consensus_score", 0)
        thumb_text = f"CLIP SCORE {score}"
    
    # Word-wrap the thumbnail text
    words = thumb_text.split()
    lines = []
    current_line = []
    max_chars = 22
    
    for word in words:
        test_line = " ".join(current_line + [word])
        if len(test_line) <= max_chars:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    
    if current_line:
        lines.append(" ".join(current_line))
    
    # Draw text with outline (centered)
    y = 320
    for line in lines[:3]:
        # Shadow/outline
        for dx in range(-3, 4, 2):
            for dy in range(-3, 4, 2):
                draw.text((640 + dx, y + dy), line, font=font_large, fill=(0, 0, 0), anchor="mm")
        # Main text
        draw.text((640, y), line, font=font_large, fill=(245, 166, 35), anchor="mm")
        y += 60
    
    # Add clip metadata at bottom
    meta_text = f"Clip {clip_id + 1}  |  {clip.get('duration', 0):.0f}s  |  Score: {clip.get('consensus_score', 0)}/10"
    draw.text((640, 660), meta_text, font=font_small, fill=(138, 133, 125), anchor="mm")
    
    # Add agent agreement badge
    agreement = clip.get("agreement", 0)
    if agreement >= 4:
        badge_text = f"⭐ {agreement}/5 AGENTS AGREE"
        draw.text((640, 60), badge_text, font=font_med, fill=(125, 192, 74), anchor="mm")
    elif agreement >= 3:
        badge_text = f"{agreement}/5 AGENTS AGREE"
        draw.text((640, 60), badge_text, font=font_med, fill=(245, 166, 35), anchor="mm")
    
    img.save(thumbnail_path, "JPEG", quality=95)
    return f"thumbnails/clip_{clip_id}.jpg"
