"""
Pipeline orchestrator — runs the full multi-agent clip discovery pipeline.

Stages:
1. Ingest: Extract audio, probe video metadata
2. Transcribe: Generate timestamped transcript
3. Clip Scout: Multi-agent candidate scoring
4. Edit Agent: Trim, caption, normalize
5. Packaging Agent: Titles, thumbnails, descriptions
"""

import os
import json
import subprocess
import time
import uuid

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.scout_agents import analyze_transcript, AGENTS
from agents.edit_agent import process_clip
from agents.packaging_agent import generate_titles, generate_thumbnail, generate_description, generate_text_thumbnail


def get_video_duration(source_path):
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", source_path],
            capture_output=True, text=True, timeout=10
        )
        info = json.loads(result.stdout)
        return float(info["format"]["duration"])
    except Exception:
        return 0


def extract_audio(source_path, output_path):
    """Extract audio from video file as WAV."""
    try:
        command = [
            "ffmpeg", "-y", "-i", source_path,
            "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1",
            output_path,
        ]
        subprocess.run(command, capture_output=True, timeout=60)
        return os.path.exists(output_path)
    except Exception:
        return False


def create_sample_video(output_path, duration=30):
    """
    Create a short sample video with a colored gradient background.
    Fast to generate, small file size, works for clip extraction.
    """
    try:
        command = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"color=c=0x1a1916:s=1280x720:r=24:d={duration}",
            "-f", "lavfi", "-i", f"anullsrc=channel_layout=mono:sample_rate=16000:d={duration}",
            "-shortest",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "35",
            "-c:a", "aac", "-b:a", "32k",
            output_path,
        ]
        subprocess.run(command, capture_output=True, timeout=30)
        return os.path.exists(output_path)
    except Exception:
        return False


def generate_sample_transcript(duration=300):
    """
    Generate a realistic sample podcast transcript for testing/demo.
    Includes strong clips, boring filler, and everything in between
    so the multi-agent system has to actually differentiate.
    """
    sample_segments = [
        # Cold open — strong hook
        {"text": "So nobody talks about this, but the real reason most businesses fail isn't money.", "start": 0.0, "end": 5.5},
        {"text": "It's because the founder gets bored.", "start": 5.5, "end": 8.0},
        {"text": "I'm serious. I've looked at the data, and it's insane.", "start": 8.0, "end": 12.0},
        
        # Intro / filler — low value
        {"text": "Welcome back to the show. Today we're diving deep into something that I think is going to be interesting.", "start": 12.0, "end": 19.0},
        {"text": "Before we get into it, quick shout out to today's sponsor. They've been great supporters of the show.", "start": 19.0, "end": 26.0},
        {"text": "Okay so like I was saying, we have a conversation about focus, about why people quit.", "start": 26.0, "end": 33.0},
        
        # Story arc — vulnerability (strong)
        {"text": "Let me tell you a story. Three years ago, I was broke. I mean really broke.", "start": 33.0, "end": 40.0},
        {"text": "I had started four businesses. All four failed. And I remember sitting in my car, crying, thinking I was the biggest failure in the world.", "start": 40.0, "end": 51.0},
        {"text": "My mom called me and said, maybe you should just get a real job. And honestly? I almost did.", "start": 51.0, "end": 59.0},
        
        # Transition / filler
        {"text": "But yeah, anyway, um, I was at this coffee shop, and I was just kind of sitting there, you know.", "start": 59.0, "end": 67.0},
        {"text": "Sort of just thinking about stuff, like where my life was going, that kind of thing.", "start": 67.0, "end": 73.0},
        
        # Turn — surprise (strong)
        {"text": "But then something happened that changed everything. I met this guy at a coffee shop.", "start": 73.0, "end": 80.0},
        {"text": "He was wearing a t-shirt and jeans. Looked like nobody special. Turns out he was worth nine figures.", "start": 80.0, "end": 88.0},
        {"text": "And he told me something I'll never forget. He said, the problem isn't that you're failing.", "start": 88.0, "end": 96.0},
        {"text": "The problem is you're failing at the wrong things.", "start": 96.0, "end": 100.0},
        
        # Insight — quotable (strong)
        {"text": "Think about that for a second. Failing at the wrong things.", "start": 100.0, "end": 105.0},
        {"text": "What he meant was, I was starting businesses I didn't actually care about.", "start": 105.0, "end": 111.0},
        {"text": "I was chasing money instead of chasing mastery. And that's the difference.", "start": 111.0, "end": 117.0},
        
        # Filler / tangent
        {"text": "And you know, I think about that a lot, especially when I, you know, I talk to other entrepreneurs.", "start": 117.0, "end": 125.0},
        {"text": "Like, I had this conversation last week with a guy, and he was basically saying the same thing.", "start": 125.0, "end": 133.0},
        {"text": "It's like, yeah, I mean, it's pretty much what everyone goes through, right?", "start": 133.0, "end": 140.0},
        
        # Controversy (strong)
        {"text": "Here's the controversial take. Most entrepreneurs are lazy. Not in terms of hours worked.", "start": 140.0, "end": 148.0},
        {"text": "I know people who work 80 hours a week and get nothing done. That's not hard work, that's avoidance.", "start": 148.0, "end": 156.0},
        {"text": "Real hard work is sitting with the uncomfortable truth that maybe your idea sucks.", "start": 156.0, "end": 163.0},
        
        # Emotional peak (strong)
        {"text": "And I know that's hard to hear. Believe me, I know.", "start": 163.0, "end": 168.0},
        {"text": "Because when that guy told me I was failing at the wrong things, I wanted to punch him.", "start": 168.0, "end": 175.0},
        {"text": "I was angry. I was defensive. I was wrong. And being wrong is the most valuable thing that ever happened to me.", "start": 175.0, "end": 185.0},
        
        # Practical advice (moderate)
        {"text": "So here's what I want you to do. Today. Not tomorrow. Today.", "start": 185.0, "end": 192.0},
        {"text": "Write down the three things you're spending the most time on.", "start": 192.0, "end": 197.0},
        {"text": "Then ask yourself, are these the things that actually matter? Or are you just busy?", "start": 197.0, "end": 205.0},
        {"text": "Because I guarantee you, 90 percent of what you do every day doesn't matter.", "start": 205.0, "end": 212.0},
        
        # Climax — quotable (strong)
        {"text": "The most successful people I know aren't the ones who work the hardest. They're the ones who quit the fastest.", "start": 212.0, "end": 221.0},
        {"text": "They quit the things that don't matter so they can focus on the things that do.", "start": 221.0, "end": 228.0},
        {"text": "That's the secret. That's the whole game. Stop doing stupid shit that doesn't matter.", "start": 228.0, "end": 236.0},
        
        # Reflection (moderate)
        {"text": "I wish someone had told me that ten years ago. Would have saved me a lot of pain.", "start": 236.0, "end": 243.0},
        {"text": "But honestly? The pain was necessary. I needed to fail.", "start": 243.0, "end": 249.0},
        {"text": "Failure is just feedback. It's data. It's the universe telling you to try something different.", "start": 249.0, "end": 258.0},
        
        # Wrap up / CTA (moderate)
        {"text": "So let me ask you this. What are you going to quit today?", "start": 258.0, "end": 264.0},
        {"text": "Drop it in the comments. I read every single one.", "start": 264.0, "end": 269.0},
        {"text": "And if this hit different, share it with someone who needs to hear it.", "start": 269.0, "end": 275.0},
        {"text": "Because the right message at the right time can change someone's entire life.", "start": 275.0, "end": 282.0},
        {"text": "I know, because it happened to me.", "start": 282.0, "end": 286.0},
    ]
    
    return sample_segments


def run_pipeline(source_path, job_id, use_sample=True, is_demo=False):
    """
    Run the full clip discovery pipeline.
    
    source_path: path to source video/audio file (may not exist in demo mode)
    job_id: unique job identifier
    use_sample: if True, use sample transcript instead of real transcription
    is_demo: if True, skip heavy video processing, use text-based thumbnails
    
    returns: dict with all results
    """
    job_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    results = {
        "job_id": job_id,
        "status": "processing",
        "stages": [],
        "clips": [],
        "transcript": None,
        "duration": 0,
        "is_demo": is_demo,
    }
    
    def stage(name, status, detail=""):
        results["stages"].append({
            "name": name,
            "status": status,
            "detail": detail,
            "timestamp": time.time(),
        })
    
    # --- Stage 1: Ingest ---
    stage("Ingest", "running", "Setting up source media")
    
    has_real_video = os.path.exists(source_path) and os.path.getsize(source_path) > 1000
    
    if has_real_video:
        duration = get_video_duration(source_path)
        results["duration"] = duration
        audio_path = os.path.join(job_dir, "audio.wav")
        extract_audio(source_path, audio_path)
        stage("Ingest", "complete", f"Duration: {duration:.1f}s, audio extracted")
    elif is_demo:
        # Create a sample video matching transcript duration for clip extraction
        sample_video = os.path.join(job_dir, "source.mp4")
        # Use 300s to match the sample transcript duration
        create_sample_video(sample_video, duration=300)
        source_path = sample_video
        duration = 300
        results["duration"] = duration
        stage("Ingest", "complete", f"Sample video created (demo mode, {duration}s)")
    else:
        duration = 300
        results["duration"] = duration
        stage("Ingest", "complete", "No source video — running transcript-only mode")
    
    # --- Stage 2: Transcribe ---
    stage("Transcription", "running", "Generating timestamped transcript")
    
    transcript = None
    
    if not use_sample and has_real_video:
        audio_path = os.path.join(job_dir, "audio.wav")
        if os.path.exists(audio_path):
            transcript = transcribe_audio(audio_path)
    
    if transcript is None:
        transcript = generate_sample_transcript(duration if duration > 0 else 300)
        stage("Transcription", "complete", f"Sample transcript: {len(transcript)} segments (demo mode)")
    else:
        stage("Transcription", "complete", f"Transcribed: {len(transcript)} segments")
    
    results["transcript"] = transcript
    
    # --- Stage 3: Clip Scout (Multi-Agent) ---
    stage("Clip Scout", "running", f"Deploying {len(AGENTS)} viewer agents")
    
    candidates = analyze_transcript(transcript)
    
    agent_summary = ", ".join([
        f"{a['icon']} {a['name']}" for a in AGENTS
    ])
    stage("Clip Scout", "complete", f"{len(candidates)} clips identified by {agent_summary}")
    
    # --- Stage 4: Edit Agent ---
    stage("Edit Agent", "running", f"Processing {len(candidates)} clips")
    
    processed_clips = []
    for i, clip in enumerate(candidates):
        clip_result = process_clip(source_path, clip, job_dir, i, skip_heavy=is_demo)
        clip_result["agent_scores"] = clip.get("agent_scores", [])
        clip_result["consensus_score"] = clip.get("consensus_score", 0)
        clip_result["agreement"] = clip.get("agreement", 0)
        clip_result["signals"] = clip.get("signals", {})
        clip_result["text"] = clip.get("text", "")
        clip_result["start"] = clip.get("start", 0)
        clip_result["end"] = clip.get("end", 0)
        processed_clips.append(clip_result)
    
    stage("Edit Agent", "complete", f"Trimmed and processed {len(processed_clips)} clips")
    
    # --- Stage 5: Packaging Agent ---
    stage("Packaging Agent", "running", "Generating titles, thumbnails, descriptions")
    
    for i, clip in enumerate(processed_clips):
        # Generate titles
        clip["titles"] = generate_titles(clip)
        
        # Generate thumbnail
        if is_demo or not has_real_video:
            # Text-based thumbnail (fast, no video needed)
            thumb_path = generate_text_thumbnail(clip, job_dir, i)
            clip["thumbnail"] = thumb_path
        else:
            # Frame-based thumbnail from video
            thumb_path = generate_thumbnail(source_path, clip, job_dir, i)
            clip["thumbnail"] = thumb_path
        
        # Generate description
        clip["description"] = generate_description(clip)
    
    stage("Packaging Agent", "complete", f"Generated {len(processed_clips)} posting packages")
    
    # --- Finalize ---
    results["clips"] = processed_clips
    results["status"] = "complete"
    
    # Save results
    results_path = os.path.join(job_dir, "results.json")
    serializable = json.loads(json.dumps(results, default=str))
    with open(results_path, "w") as f:
        json.dump(serializable, f, indent=2)
    
    return results


def transcribe_audio(audio_path):
    """Transcribe audio using OpenAI Whisper API if available."""
    try:
        from openai import OpenAI
        client = OpenAI()
        
        with open(audio_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
        
        segments = []
        for seg in result.segments:
            segments.append({
                "text": seg.text,
                "start": round(seg.start, 2),
                "end": round(seg.end, 2),
            })
        
        return segments
    except Exception:
        return None
