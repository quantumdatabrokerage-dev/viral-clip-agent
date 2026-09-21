"""
Flask backend for the Viral Clip Agent.

Serves the dashboard and API endpoints for the multi-agent clip pipeline.
"""

import os
import json
import uuid
import threading

from flask import Flask, request, jsonify, send_from_directory, redirect

# Add parent to path
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import run_pipeline

app = Flask(__name__, static_folder="static", static_url_path="")

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Job status tracking
jobs = {}


@app.route("/")
def index():
    return app.send_static_file("index.html")


@app.route("/api/agents")
def get_agents():
    """Return the list of scout agent personas."""
    from agents.scout_agents import AGENTS
    return jsonify(AGENTS)


@app.route("/api/upload", methods=["POST"])
def upload():
    """Handle video file upload and start processing pipeline."""
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400
    
    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    # Save uploaded file
    filename = "source.mp4"
    source_path = os.path.join(job_dir, filename)
    file.save(source_path)
    
    # Check if using sample transcript
    use_sample = request.form.get("sample", "true").lower() == "true"
    
    # Start processing in background thread
    def process():
        try:
            jobs[job_id] = {"status": "processing", "progress": 0}
            result = run_pipeline(source_path, job_id, use_sample=use_sample)
            jobs[job_id] = {"status": "complete", "result": result}
        except Exception as e:
            import traceback
            traceback.print_exc()
            jobs[job_id] = {"status": "error", "error": str(e)}
    
    thread = threading.Thread(target=process)
    thread.daemon = True
    thread.start()
    
    return jsonify({"job_id": job_id, "status": "processing"})


@app.route("/api/demo", methods=["POST"])
def demo():
    """Run the pipeline with a sample transcript (no upload needed)."""
    job_id = str(uuid.uuid4())[:8]
    job_dir = os.path.join(UPLOAD_DIR, job_id)
    os.makedirs(job_dir, exist_ok=True)
    
    # Create a short sample video (30s, fast to generate)
    # The pipeline's create_sample_video will handle this
    source_path = os.path.join(job_dir, "source.mp4")
    # Don't pre-create — the pipeline will create it in demo mode
    
    # Start processing
    def process():
        try:
            jobs[job_id] = {"status": "processing", "progress": 0}
            result = run_pipeline(source_path, job_id, use_sample=True, is_demo=True)
            jobs[job_id] = {"status": "complete", "result": result}
        except Exception as e:
            import traceback
            traceback.print_exc()
            jobs[job_id] = {"status": "error", "error": str(e)}
    
    thread = threading.Thread(target=process)
    thread.daemon = True
    thread.start()
    
    return jsonify({"job_id": job_id, "status": "processing"})


@app.route("/api/job/<job_id>")
def get_job(job_id):
    """Get job status and results."""
    if job_id not in jobs:
        return jsonify({"error": "Job not found"}), 404
    
    job = jobs[job_id]
    return jsonify(job)


@app.route("/api/job/<job_id>/clips/<path:filename>")
def serve_clip(job_id, filename):
    """Serve clip files."""
    clip_dir = os.path.join(UPLOAD_DIR, job_id, "clips")
    return send_from_directory(clip_dir, filename)


@app.route("/api/job/<job_id>/thumbnails/<path:filename>")
def serve_thumbnail(job_id, filename):
    """Serve thumbnail files."""
    thumb_dir = os.path.join(UPLOAD_DIR, job_id, "thumbnails")
    return send_from_directory(thumb_dir, filename)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
