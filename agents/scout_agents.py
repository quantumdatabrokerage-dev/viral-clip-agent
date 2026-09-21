"""
Clip Scout Agents — Multi-perspective viral clip identification.

Each agent "watches" the transcript from a different viewpoint,
scoring segments for viral potential. The consensus engine then
finds clips that multiple agents agree on — simulating a panel
of human editors with different tastes.
"""

import json
import re
import math
from collections import Counter

# --- Agent Personas ---
# Each agent has a name, focus, and scoring weights for different signals

AGENTS = [
    {
        "name": "Hook Hunter",
        "icon": "🎯",
        "focus": "Strong openings, attention grabs, pattern interrupts",
        "weights": {
            "hook": 3.0,
            "curiosity": 2.5,
            "surprise": 2.0,
            "emotion": 1.0,
            "quotable": 1.5,
            "standalone": 2.0,
        },
    },
    {
        "name": "Emotion Reader",
        "icon": "🔥",
        "focus": "High emotional intensity, vulnerability, conflict, passion",
        "weights": {
            "hook": 1.0,
            "curiosity": 1.0,
            "surprise": 2.0,
            "emotion": 3.0,
            "quotable": 1.5,
            "standalone": 1.5,
        },
    },
    {
        "name": "Quote Finder",
        "icon": "💎",
        "focus": "Shareable soundbites, quotable moments, memorable lines",
        "weights": {
            "hook": 1.0,
            "curiosity": 1.0,
            "surprise": 1.5,
            "emotion": 1.0,
            "quotable": 3.0,
            "standalone": 2.5,
        },
    },
    {
        "name": "Story Analyst",
        "icon": "📖",
        "focus": "Narrative arcs, tension, resolution, storytelling structure",
        "weights": {
            "hook": 2.0,
            "curiosity": 2.5,
            "surprise": 1.5,
            "emotion": 1.5,
            "quotable": 1.0,
            "standalone": 1.0,
        },
    },
    {
        "name": "Trend Spotter",
        "icon": "📈",
        "focus": "Controversial takes, hot topics, debate-worthy statements",
        "weights": {
            "hook": 1.5,
            "curiosity": 2.0,
            "surprise": 2.5,
            "emotion": 2.0,
            "quotable": 2.0,
            "standalone": 2.5,
        },
    },
]


# --- Signal Detection Patterns ---

# Emotional intensity keywords
EMOTION_WORDS = {
    "anger": ["angry", "furious", "pissed", "hate", "outrageous", "disgusting", "unbelievable", "ridiculous", "insane", "crazy", "absurd", "sick", "tired", "broken"],
    "excitement": ["amazing", "incredible", "love", "awesome", "mind-blowing", "extraordinary", "brilliant", "genius", "perfect", "insane", "wild", "crazy"],
    "surprise": ["wait", "actually", "honestly", "realize", "discovered", "turns out", "never knew", "shocking", "didn't know", "no way", "what", "whoa", "wow"],
    "vulnerability": ["scared", "afraid", "worried", "struggle", "failed", "mistake", "hard", "difficult", "lonely", "depressed", "anxious", "lost", "broken"],
    "passion": ["believe", "matter", "important", "fight", "change", "future", "mission", "purpose", "dedicated", "committed", "never stop"],
}

# Hook / curiosity patterns
HOOK_PATTERNS = [
    r"^(you know|so|here's|let me|I want to|the thing|what if|imagine|think about)",
    r"(nobody talks about|nobody mentions|people don't realize|the real reason|secret)",
    r"(question for you|let me ask|raise your hand|quick question)",
    r"(stop|wait|hold on|listen|look)",
]

# Controversy / debate patterns
CONTROVERSY_WORDS = ["wrong", "stupid", "idiot", "terrible", "worst", "best", "never", "always", "everyone", "nobody", "all", "none", "definitely", "absolutely", "bullshit", "nonsense"]

# Filler / low-value patterns (reduce score)
FILLER_WORDS = ["um", "uh", "like", "you know", "sort of", "kind of", "I mean", "right", "basically", "literally"]


def analyze_transcript(transcript):
    """
    Analyze a timestamped transcript and return scored candidate clips.
    
    transcript: list of {text, start, end} segments
    returns: list of candidate clips with scores from each agent
    """
    if not transcript:
        return []
    
    # Generate overlapping candidate windows (30-90 seconds)
    candidates = generate_candidates(transcript)
    
    # Score each candidate with each agent
    for candidate in candidates:
        candidate["agent_scores"] = []
        candidate["signals"] = analyze_segment(candidate)
        
        for agent in AGENTS:
            score = score_with_agent(candidate["signals"], agent)
            candidate["agent_scores"].append({
                "agent": agent["name"],
                "icon": agent["icon"],
                "score": round(score, 1),
                "rationale": generate_rationale(candidate["signals"], agent),
            })
        
        # Consensus score = average of top 3 agent scores
        sorted_scores = sorted([a["score"] for a in candidate["agent_scores"]], reverse=True)
        candidate["consensus_score"] = round(sum(sorted_scores[:3]) / 3, 1)
        candidate["agreement"] = sum(1 for s in candidate["agent_scores"] if s["score"] >= 6.0)
    
    # Sort by consensus score
    candidates.sort(key=lambda c: c["consensus_score"], reverse=True)
    
    # Remove overlapping clips (keep highest scoring)
    filtered = remove_overlaps(candidates)
    
    return filtered[:5]  # Top 5 clips


def generate_candidates(transcript):
    """Generate overlapping 30-90 second candidate windows from transcript."""
    candidates = []
    
    # Merge transcript into full text with timestamps
    full_segments = transcript
    
    if not full_segments:
        return []
    
    total_duration = full_segments[-1]["end"]
    
    # Generate windows: 30s, 45s, 60s, 75s, 90s lengths
    window_sizes = [30, 45, 60, 75, 90]
    
    for window_size in window_sizes:
        step = max(15, window_size // 3)  # Overlap
        
        start = 0
        while start < total_duration:
            end = start + window_size
            
            # Get segments in this window
            window_segments = [
                s for s in full_segments 
                if s["start"] >= start and s["end"] <= end
            ]
            
            if len(window_segments) < 3:  # Need at least 3 segments
                start += step
                continue
            
            # Merge text
            text = " ".join([s["text"] for s in window_segments])
            
            candidates.append({
                "start": round(start, 1),
                "end": round(min(end, total_duration), 1),
                "duration": round(min(end, total_duration) - start, 1),
                "text": text,
                "segments": window_segments,
            })
            
            start += step
    
    return candidates


def analyze_segment(candidate):
    """Extract viral signals from a transcript segment."""
    text = candidate["text"].lower()
    words = text.split()
    word_count = len(words)
    
    if word_count == 0:
        return {}
    
    signals = {}
    
    # --- Emotion Detection ---
    emotion_hits = {}
    for category, keywords in EMOTION_WORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits > 0:
            emotion_hits[category] = hits
    signals["emotion_categories"] = emotion_hits
    signals["emotion_intensity"] = min(10, sum(emotion_hits.values()) * 1.5)
    
    # --- Hook / Curiosity ---
    hook_hits = 0
    for pattern in HOOK_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            hook_hits += 1
    signals["hook_strength"] = min(10, hook_hits * 3 + (2 if word_count > 20 else 0))
    signals["curiosity"] = min(10, hook_hits * 2.5)
    
    # --- Surprise ---
    surprise_words = EMOTION_WORDS["surprise"]
    surprise_hits = sum(1 for sw in surprise_words if sw in text)
    signals["surprise"] = min(10, surprise_hits * 2.5)
    
    # --- Quotability ---
    # Short, punchy sentences are more quotable
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    
    quotable_score = 0
    for sent in sentences:
        sent_words = sent.split()
        if 5 <= len(sent_words) <= 25:  # Sweet spot for quotes
            quotable_score += 2
        if len(sent_words) <= 15 and len(sent_words) >= 4:
            quotable_score += 1
    
    # Check for quotable patterns (aphorisms, strong statements)
    quotable_patterns = [
        r"the (best|worst|most|greatest|hardest|important) ",
        r"you (can't|should|must|need|have to|never)",
        r"i (believe|think|know|guarantee)",
        r"that('s| is) (why|because|the|what)",
        r"\b(never|always|everyone|nobody)\b",
    ]
    for pattern in quotable_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            quotable_score += 1
    
    signals["quotable"] = min(10, quotable_score)
    
    # --- Standalone Clarity ---
    # Can this clip be understood without the full context?
    context_indicators = [
        "so", "then", "after that", "as I was saying", "like I said",
        "going back", "anyway", "but yeah", "right so",
    ]
    context_dependency = sum(1 for ci in context_indicators if ci in text)
    signals["standalone"] = max(0, 10 - context_dependency * 2)
    
    # --- Controversy ---
    controversy_hits = sum(1 for cw in CONTROVERSY_WORDS if cw in text)
    signals["controversy"] = min(10, controversy_hits * 2)
    
    # --- Filler Penalty ---
    filler_count = sum(1 for fw in FILLER_WORDS if fw in text)
    signals["filler_penalty"] = min(5, filler_count * 0.5)
    
    # --- Speech Pace (variety = more engaging) ---
    if candidate["segments"]:
        avg_pace = word_count / max(candidate["duration"], 1)  # words per second
        signals["pace"] = min(10, avg_pace * 4)  # Normal pace ~2.5-3 wps
    
    # --- Punctuation Intensity ---
    exclamations = text.count("!")
    questions = text.count("?")
    signals["punctuation_intensity"] = min(5, (exclamations + questions) * 1.5)
    
    return signals


def score_with_agent(signals, agent):
    """Score a candidate using an agent's perspective and weights.
    Uses a sigmoid curve so differentiation is meaningful, not linear."""
    base_scores = {
        "hook": signals.get("hook_strength", 0),
        "curiosity": signals.get("curiosity", 0),
        "surprise": signals.get("surprise", 0),
        "emotion": signals.get("emotion_intensity", 0),
        "quotable": signals.get("quotable", 0),
        "standalone": signals.get("standalone", 0),
    }
    
    # Apply agent weights
    weighted_sum = 0
    weight_total = 0
    for signal, score in base_scores.items():
        weight = agent["weights"].get(signal, 1.0)
        weighted_sum += score * weight
        weight_total += weight
    
    # Add bonuses
    controversy_bonus = signals.get("controversy", 0) * 0.5
    punctuation_bonus = signals.get("punctuation_intensity", 0) * 0.3
    
    # Subtract filler penalty
    filler_penalty = signals.get("filler_penalty", 0)
    
    raw_score = (weighted_sum / weight_total) + controversy_bonus + punctuation_bonus - filler_penalty
    
    # Apply sigmoid curve: compresses the 0-10 range so that
    # only truly exceptional clips reach 8-10, good ones land 5-7,
    # and mediocre ones land 2-5. This creates real differentiation.
    sigmoid_score = 10 / (1 + 2.71828 ** (-1.0 * (raw_score - 5)))
    
    return min(10, max(0, round(sigmoid_score, 1)))


def generate_rationale(signals, agent):
    """Generate a human-readable rationale for why this agent scored this clip."""
    reasons = []
    
    if signals.get("hook_strength", 0) >= 5:
        reasons.append("strong hook")
    if signals.get("emotion_intensity", 0) >= 5:
        cats = signals.get("emotion_categories", {})
        if cats:
            top_cat = max(cats, key=cats.get)
            reasons.append(f"high {top_cat}")
    if signals.get("quotable", 0) >= 5:
        reasons.append("quotable")
    if signals.get("surprise", 0) >= 5:
        reasons.append("surprising")
    if signals.get("standalone", 0) >= 7:
        reasons.append("works standalone")
    if signals.get("controversy", 0) >= 5:
        reasons.append("controversial")
    
    if not reasons:
        reasons.append("moderate engagement signals")
    
    return ", ".join(reasons)


def remove_overlaps(candidates, min_gap=10):
    """Remove overlapping clips, keeping the highest-scoring ones."""
    filtered = []
    
    for candidate in candidates:
        overlaps = False
        for kept in filtered:
            # Check if clips overlap
            if (candidate["start"] < kept["end"] + min_gap and 
                candidate["end"] > kept["start"] - min_gap):
                overlaps = True
                break
        
        if not overlaps:
            filtered.append(candidate)
    
    return filtered
