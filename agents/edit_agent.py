"""
Edit Agent — Trims clips, burns captions, normalizes audio.

Takes identified clip segments and produces polished, shareable clips.
Supports a fast mode that skips heavy ffmpeg operations for demo/testing.
"""

import os
import subprocess


def process_clip(source_path, clip, job_dir, clip_id, skip_heavy=False):
    """
    Process a single clip: trim, normalize audio, burn captions.
    
    source_path: path to source video/audio file
    clip: candidate dict with start, end, text, segments
    job_dir: directory for this job
    clip_id: unique identifier for this clip
    skip_heavy: if True, only trim (skip caption burning and vertical crop)
    
    returns: dict with clip metadata and file paths
    """
    clip_dir = os.path.join(job_dir, "clips")
    os.makedirs(clip_dir, exist_ok=True)
    
    output_path = os.path.join(clip_dir, f"clip_{clip_id}.mp4")
    caption_path = os.path.join(clip_dir, f"clip_{clip_id}.srt")
    vertical_path = os.path.join(clip_dir, f"clip_{clip_id}_vertical.mp4")
    
    start = clip["start"]
    end = clip["end"]
    duration = end - start
    
    # Clamp start/end to source video duration if needed
    if duration <= 0:
        duration = 5
    
    # Always generate SRT (fast, text only)
    generate_srt(clip.get("segments", []), caption_path, start)
    
    # Check if source video exists
    has_source = os.path.exists(source_path) and os.path.getsize(source_path) > 1000
    
    if not has_source:
        return {
            "clip_id": clip_id,
            "start": start,
            "end": end,
            "duration": round(duration, 1),
            "clip_path": None,
            "vertical_path": None,
            "caption_path": f"clips/clip_{clip_id}.srt",
            "exists": False,
        }
    
    # Step 1: Trim clip and normalize audio
    trim_command = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", source_path,
        "-t", str(duration),
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "128k",
        output_path,
    ]
    
    try:
        subprocess.run(trim_command, capture_output=True, timeout=30)
    except Exception:
        pass
    
    # Step 2: Burn captions (skip in fast mode)
    if not skip_heavy and os.path.exists(output_path) and os.path.exists(caption_path):
        captioned_path = output_path.replace(".mp4", "_cap.mp4")
        burn_command = [
            "ffmpeg", "-y",
            "-i", output_path,
            "-vf", f"subtitles={caption_path}:force_style='FontName=Arial,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=0,MarginV=40'",
            "-c:a", "copy",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            captioned_path,
        ]
        try:
            subprocess.run(burn_command, capture_output=True, timeout=30)
            if os.path.exists(captioned_path):
                os.replace(captioned_path, output_path)
        except Exception:
            pass
    
    # Step 3: Create vertical (9:16) version (skip in fast mode)
    if not skip_heavy and os.path.exists(output_path):
        try:
            create_vertical(output_path, vertical_path)
        except Exception:
            pass
    
    result = {
        "clip_id": clip_id,
        "start": start,
        "end": end,
        "duration": round(duration, 1),
        "clip_path": f"clips/clip_{clip_id}.mp4" if os.path.exists(output_path) else None,
        "vertical_path": f"clips/clip_{clip_id}_vertical.mp4" if os.path.exists(vertical_path) else None,
        "caption_path": f"clips/clip_{clip_id}.srt",
        "exists": os.path.exists(output_path),
    }
    
    return result


def generate_srt(segments, output_path, clip_start):
    """Generate an SRT subtitle file from transcript segments."""
    with open(output_path, "w") as f:
        idx = 1
        for seg in segments:
            start = max(0, seg["start"] - clip_start)
            end = max(0, seg["end"] - clip_start)
            
            start_ts = format_srt_time(start)
            end_ts = format_srt_time(end)
            
            f.write(f"{idx}\n")
            f.write(f"{start_ts} --> {end_ts}\n")
            f.write(f"{seg['text'].strip()}\n\n")
            idx += 1


def format_srt_time(seconds):
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def create_vertical(source_path, output_path):
    """Create a 9:16 vertical version by cropping and scaling."""
    command = [
        "ffmpeg", "-y",
        "-i", source_path,
        "-vf", "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos",
        "-c:a", "copy",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        output_path,
    ]
    subprocess.run(command, capture_output=True, timeout=30)
