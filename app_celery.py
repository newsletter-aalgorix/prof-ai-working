"""
ProfAI - Production API Server with Celery
Uses distributed task queue for scalability

This is the PRODUCTION version that uses Celery workers.
For simple testing, use app.py (ThreadPoolExecutor version).
"""

import logging
import asyncio
import sys
import os
import json
import time
import base64
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import config
from models.schemas import CourseLMS, TTSRequest, QuizRequest, QuizSubmission, QuizDisplay
from celery_app import celery_app
from tasks.pdf_processing import process_pdf_and_generate_course

# Import WebSocket server
from websocket_server import run_websocket_server_in_thread

# Import services
try:
    from services.chat_service import ChatService
    from services.audio_service import AudioService
    from services.teaching_service import TeachingService
    from services.quiz_service import QuizService
    SERVICES_AVAILABLE = True
    print("✅ All services loaded successfully")
except ImportError as e:
    print(f"⚠️ Some services not available: {e}")
    SERVICES_AVAILABLE = False

# Initialize FastAPI app
app = FastAPI(
    title="ProfAI API (Production)",
    description="AI-powered multilingual educational assistant with distributed processing.",
    version="2.0.0-production"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Mount static files
web_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.exists(web_dir):
    app.mount("/static", StaticFiles(directory=web_dir), name="static")

# Initialize services
chat_service = None
audio_service = None
teaching_service = None
quiz_service = None

if SERVICES_AVAILABLE:
    MAX_RETRIES = 3
    RETRY_DELAY = 5
    for attempt in range(MAX_RETRIES):
        try:
            logging.info(f"Attempting to initialize services (Attempt {attempt + 1}/{MAX_RETRIES})...")
            chat_service = ChatService()
            audio_service = AudioService()
            teaching_service = TeachingService()
            quiz_service = QuizService()
            logging.info("✅ All services initialized successfully")
            break
        except Exception as e:
            logging.warning(f"⚠️ Failed to initialize services on attempt {attempt + 1}: {e}")
            if attempt < MAX_RETRIES - 1:
                logging.info(f"Retrying in {RETRY_DELAY} seconds...")
                time.sleep(RETRY_DELAY)
            else:
                logging.error("❌ All retries failed. Some services will be unavailable.")
                SERVICES_AVAILABLE = False

# ===== COURSE MANAGEMENT ENDPOINTS =====

@app.post("/api/upload-pdfs")
async def upload_and_process_pdfs(
    files: List[UploadFile] = File(...),
    course_title: str = Form(None),
    priority: int = Form(5)
):
    """
    Upload PDF files and generate course content using Celery workers.
    Returns immediately with a task_id. Check status with /api/jobs/{task_id}
    
    Args:
        files: PDF files to upload
        course_title: Optional course title
        priority: Task priority (1-10, higher = more important)
    """
    try:
        logging.info(f"Received {len(files)} PDF files for course: {course_title}")
        
        # Generate job ID
        import uuid
        job_id = str(uuid.uuid4())
        
        # Read and encode files as base64 (for Celery serialization)
        pdf_files_data = []
        for file in files:
            content = await file.read()
            pdf_files_data.append({
                'filename': file.filename,
                'content': base64.b64encode(content).decode('utf-8')
            })
        
        # Submit task to Celery
        task = process_pdf_and_generate_course.apply_async(
            args=[job_id, pdf_files_data, course_title],
            priority=priority,
            queue='pdf_processing'
        )
        
        logging.info(f"Created Celery task {task.id} for job {job_id}")
        
        return {
            "message": "PDF processing started",
            "job_id": job_id,
            "task_id": task.id,
            "status": "pending",
            "status_url": f"/api/jobs/{task.id}"
        }
        
    except Exception as e:
        logging.error(f"Error starting PDF processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/jobs/{task_id}")
async def get_job_status(task_id: str):
    """
    Get status of a Celery task.
    
    Status values:
    - PENDING: Task is waiting in queue
    - STARTED: Task is being processed
    - SUCCESS: Task completed successfully
    - FAILURE: Task failed
    - RETRY: Task is being retried
    """
    try:
        # Get task result from Celery
        task_result = celery_app.AsyncResult(task_id)
        
        response = {
            "task_id": task_id,
            "status": task_result.state,
        }
        
        if task_result.state == 'PENDING':
            response.update({
                "progress": 0,
                "message": "Task is waiting in queue..."
            })
        elif task_result.state == 'STARTED':
            # Get progress from task meta
            info = task_result.info or {}
            response.update({
                "progress": info.get('progress', 0),
                "message": info.get('message', 'Processing...')
            })
        elif task_result.state == 'SUCCESS':
            result = task_result.result
            response.update({
                "progress": 100,
                "message": "Task completed successfully",
                "result": result.get('result') if isinstance(result, dict) else result
            })
        elif task_result.state == 'FAILURE':
            response.update({
                "progress": 0,
                "message": "Task failed",
                "error": str(task_result.info)
            })
        elif task_result.state == 'RETRY':
            response.update({
                "progress": 0,
                "message": "Task is being retried..."
            })
        
        return response
        
    except Exception as e:
        logging.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/worker-stats")
async def get_worker_stats():
    """
    Get statistics about Celery workers.
    Useful for monitoring and debugging.
    """
    try:
        inspector = celery_app.control.inspect()
        
        stats = {
            "active_workers": inspector.active(),
            "scheduled_tasks": inspector.scheduled(),
            "active_tasks": inspector.active(),
            "reserved_tasks": inspector.reserved(),
        }
        
        return stats
    except Exception as e:
        logging.error(f"Error getting worker stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== COURSE CONTENT ENDPOINTS =====

@app.get("/api/course/{course_id}")
async def get_course_content(course_id: str):
    """Get specific course content."""
    try:
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            raise HTTPException(status_code=404, detail="Course content not found")
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both single course and multi-course formats
        if isinstance(data, dict) and 'course_title' in data:
            # Single course format
            if str(data.get("course_id", 1)) == str(course_id):
                return data
            else:
                raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
        elif isinstance(data, list):
            # Multi-course format - find the specific course
            for course in data:
                if str(course.get("course_id", "")) == str(course_id):
                    return course
            raise HTTPException(status_code=404, detail=f"Course {course_id} not found")
        else:
            raise HTTPException(status_code=500, detail="Invalid course data format")
            
        raise HTTPException(status_code=404, detail="No courses found")
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error loading course {course_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/courses")
async def get_courses():
    """Get list of available courses."""
    try:
        if os.path.exists(config.OUTPUT_JSON_PATH):
            with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict) and 'course_title' in data:
                return [{
                    "course_id": data.get("course_id", 1),
                    "course_title": data.get("course_title", "Generated Course"),
                    "modules": len(data.get("modules", []))
                }]
            elif isinstance(data, list):
                return [{
                    "course_id": course.get("course_id", i+1),
                    "course_title": course.get("course_title", f"Course {i+1}"),
                    "modules": len(course.get("modules", []))
                } for i, course in enumerate(data)]
        return []
    except Exception as e:
        logging.error(f"Error loading courses: {e}")
        return []


# ===== QUIZ ENDPOINTS =====

@app.post("/api/quiz/generate-module")
async def generate_module_quiz(request: QuizRequest):
    """Generate a 20-question MCQ quiz for a specific module."""
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        # Load course content
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            raise HTTPException(status_code=404, detail="Course content not found")
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both single course and multi-course formats
        course_content = None
        if isinstance(data, dict) and 'course_title' in data:
            if str(data.get("course_id", 1)) == str(request.course_id):
                course_content = data
        elif isinstance(data, list):
            for course in data:
                if str(course.get("course_id", "")) == str(request.course_id):
                    course_content = course
                    break
        
        if not course_content:
            raise HTTPException(status_code=404, detail=f"Course {request.course_id} not found")
        
        logging.info(f"Generating module quiz for week {request.module_week}")
        quiz = await quiz_service.generate_module_quiz(request.module_week, course_content)
        
        quiz_display = quiz_service.get_quiz_without_answers(quiz.quiz_id)
        if not quiz_display:
            raise HTTPException(status_code=500, detail="Failed to prepare quiz for display")
        
        return {
            "message": "Module quiz generated successfully",
            "quiz": quiz_display.dict()
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error generating module quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quiz/generate-course")
async def generate_course_quiz(request: QuizRequest):
    """Generate a 40-question MCQ quiz covering the entire course."""
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            raise HTTPException(status_code=404, detail="Course content not found")
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        course_content = None
        if isinstance(data, dict) and 'course_title' in data:
            if str(data.get("course_id", 1)) == str(request.course_id):
                course_content = data
        elif isinstance(data, list):
            for course in data:
                if str(course.get("course_id", "")) == str(request.course_id):
                    course_content = course
                    break
        
        if not course_content:
            raise HTTPException(status_code=404, detail=f"Course {request.course_id} not found")
        
        logging.info(f"Generating comprehensive course quiz")
        quiz = await quiz_service.generate_course_quiz(course_content)
        
        quiz_display = quiz_service.get_quiz_without_answers(quiz.quiz_id)
        if not quiz_display:
            raise HTTPException(status_code=500, detail="Failed to prepare quiz for display")
        
        return {
            "message": "Course quiz generated successfully",
            "quiz": quiz_display.dict()
        }
    except Exception as e:
        logging.error(f"Error generating course quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/quiz/submit")
async def submit_quiz(submission: QuizSubmission):
    """Submit quiz answers and get evaluation results."""
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        logging.info(f"Processing quiz submission for quiz {submission.quiz_id}")
        result = quiz_service.evaluate_quiz(submission)
        
        return {
            "message": "Quiz evaluated successfully",
            "result": result.dict()
        }
    except ValueError as ve:
        logging.error(f"Validation error in quiz submission: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logging.error(f"Error evaluating quiz: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/quiz/{quiz_id}")
async def get_quiz(quiz_id: str):
    """Get a specific quiz (without answers) for display."""
    if not SERVICES_AVAILABLE or not quiz_service:
        raise HTTPException(status_code=503, detail="Quiz service not available")
    
    try:
        quiz = quiz_service.get_quiz_without_answers(quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail=f"Quiz {quiz_id} not found")
        
        return {"quiz": quiz.dict()}
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error retrieving quiz {quiz_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== CHAT & COMMUNICATION ENDPOINTS =====

@app.post("/api/chat")
async def chat_endpoint(request: dict):
    """Text-only chat endpoint."""
    if not SERVICES_AVAILABLE or not chat_service:
        raise HTTPException(status_code=503, detail="Chat service not available")
    
    try:
        query = request.get('message') or request.get('query')
        language = request.get('language', 'en-IN')
        
        if not query:
            raise HTTPException(status_code=400, detail="Message/query is required")
        
        logging.info(f"Chat query: {query[:50]}...")
        response_data = await chat_service.ask_question(query, language)
        return response_data
    except Exception as e:
        logging.error(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat-with-audio")
async def chat_with_audio_endpoint(request: dict):
    """Chat endpoint with automatic audio generation."""
    if not SERVICES_AVAILABLE or not chat_service or not audio_service:
        raise HTTPException(status_code=503, detail="Chat or audio service not available")
    
    try:
        query = request.get('message') or request.get('query')
        language = request.get('language', 'en-IN')
        
        if not query:
            raise HTTPException(status_code=400, detail="Message/query is required")
        
        logging.info(f"Chat with audio query: {query[:50]}...")
        
        # Get text response
        response_data = await chat_service.ask_question(query, language)
        answer_text = response_data.get('answer', '')
        
        # Generate audio
        audio_buffer = await audio_service.generate_audio_from_text(answer_text, language)
        audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
        
        return {
            "answer": answer_text,
            "audio_data": audio_base64,
            "metadata": response_data
        }
    except Exception as e:
        logging.error(f"Error in chat with audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/transcribe")
async def transcribe_endpoint(language: str = Form("en-IN"), audio_file: UploadFile = File(...)):
    """Audio transcription for voice input."""
    if not SERVICES_AVAILABLE or not audio_service:
        raise HTTPException(status_code=503, detail="Audio service not available")
    
    try:
        logging.info(f"Transcribing audio file: {audio_file.filename}")
        audio_data = await audio_file.read()
        
        # Save to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_file:
            temp_file.write(audio_data)
            temp_path = temp_file.name
        
        try:
            text = await audio_service.transcribe_audio(temp_path, language)
            return {"transcription": text}
        finally:
            os.unlink(temp_path)
            
    except Exception as e:
        logging.error(f"Error transcribing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== CLASS TEACHING ENDPOINTS =====

@app.post("/api/start-class")
async def start_class_endpoint(request: dict):
    """Start a class session with content preview and audio generation."""
    if not SERVICES_AVAILABLE or not teaching_service or not audio_service:
        raise HTTPException(status_code=503, detail="Required services not available")
    
    try:
        course_id = request.get("course_id")
        module_index = request.get("module_index", 0)
        sub_topic_index = request.get("sub_topic_index", 0)
        language = request.get("language", "en-IN")
        content_only = request.get("content_only", False)
        
        logging.info(f"Starting class for course: {course_id}, module: {module_index}, topic: {sub_topic_index}")
        
        # Load course content
        if not os.path.exists(config.OUTPUT_JSON_PATH):
            raise HTTPException(status_code=404, detail="Course content not found")
        
        with open(config.OUTPUT_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Handle both single course and multi-course formats
        if isinstance(data, dict) and 'course_title' in data:
            course_data = data
        elif isinstance(data, list):
            course_data = None
            for course in data:
                if str(course.get("course_id", "")) == str(course_id):
                    course_data = course
                    break
            if not course_data:
                course_data = data[0] if data else None
        else:
            course_data = None
            
        if not course_data:
            raise HTTPException(status_code=404, detail="Course content not found")
        
        # Validate indices
        if module_index >= len(course_data.get("modules", [])):
            raise HTTPException(status_code=400, detail="Module not found")
            
        module = course_data["modules"][module_index]
        
        if sub_topic_index >= len(module.get("sub_topics", [])):
            raise HTTPException(status_code=400, detail="Sub-topic not found")
            
        sub_topic = module["sub_topics"][sub_topic_index]
        
        # Generate teaching content
        raw_content = sub_topic.get('content', '')
        if not raw_content:
            raw_content = f"This topic covers {sub_topic['title']} as part of {module['title']}."
        
        try:
            teaching_content = await teaching_service.generate_teaching_content(
                module_title=module['title'],
                sub_topic_title=sub_topic['title'],
                raw_content=raw_content,
                language=language
            )
            
            if not teaching_content or len(teaching_content.strip()) == 0:
                raise Exception("Empty teaching content generated")
                
        except Exception as e:
            logging.error(f"Error generating teaching content: {e}")
            teaching_content = f"Welcome to the lesson on {sub_topic['title']}. {raw_content[:500]}..."
        
        logging.info(f"Generated teaching content: {len(teaching_content)} characters")
        
        # If only content preview is requested, return it
        if content_only:
            return {
                "content_preview": teaching_content[:400] + "..." if len(teaching_content) > 400 else teaching_content,
                "full_content_length": len(teaching_content),
                "module_title": module['title'],
                "sub_topic_title": sub_topic['title']
            }
        
        # Generate audio
        logging.info("Generating audio for teaching content...")
        audio_buffer = await audio_service.generate_audio_from_text(teaching_content, language)
        
        if not audio_buffer.getbuffer().nbytes:
            raise HTTPException(status_code=500, detail="Failed to generate audio")
        
        logging.info(f"Audio generated: {audio_buffer.getbuffer().nbytes} bytes")
        return StreamingResponse(audio_buffer, media_type="audio/mpeg")
        
    except Exception as e:
        logging.error(f"Error starting class: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "version": "2.0.0-production",
        "message": "ProfAI Production API with Celery Workers"
    }


@app.get("/health")
async def health_check():
    """Detailed health check"""
    health = {
        "api": "healthy",
        "services": SERVICES_AVAILABLE,
        "celery": "unknown"
    }
    
    try:
        # Check Celery connection
        inspector = celery_app.control.inspect()
        stats = inspector.stats()
        health["celery"] = "healthy" if stats else "no_workers"
    except Exception as e:
        health["celery"] = f"error: {str(e)}"
    
    return health


# Start server
if __name__ == "__main__":
    import uvicorn
    
    # Start WebSocket server in background
    websocket_thread = run_websocket_server_in_thread()
    
    # Start FastAPI server
    uvicorn.run(
        app,
        host=config.HOST,
        port=config.PORT,
        log_level="info"
    )
