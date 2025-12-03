"""
Database Service - ACTUAL Neon Schema
Matches the real database schema with TEXT UUIDs
"""

import os
import logging
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, ARRAY, Boolean, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session
from contextlib import contextmanager
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL')
USE_DATABASE = os.getenv('USE_DATABASE', 'false').lower() == 'true'

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SQLAlchemy Base
Base = declarative_base()

# ============================================================
# DATABASE MODELS (Match ACTUAL schema)
# ============================================================

class User(Base):
    """User accounts - ACTUAL schema with TEXT id"""
    __tablename__ = 'users'
    
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(Text, unique=True, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    password = Column(Text, nullable=False)
    role = Column(Text, default='student', nullable=False)
    student_type = Column(Text)
    college_name = Column(Text)
    degree = Column(Text)
    school_class = Column(Text)
    school_affiliation = Column(Text)
    terms_accepted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    institution = Column(Text)
    subject = Column(Text)
    experience = Column(Text)


class Course(Base):
    """Main course entities - ACTUAL schema with TEXT id"""
    __tablename__ = 'courses'
    
    id = Column(Text, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(Text, nullable=False)
    description = Column(Text)
    level = Column(Text, default='Beginner')
    teacher_id = Column(Text, nullable=False)
    is_free = Column(Boolean, default=False, nullable=False)
    price = Column(Numeric, default=0)
    currency = Column(Text, default='INR')
    course_order = Column(Integer)
    file_metadata = Column(JSONB)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    created_by = Column(String)  # Kept for compatibility
    
    # Relationships
    modules = relationship("Module", back_populates="course", cascade="all, delete-orphan")
    quizzes = relationship("Quiz", back_populates="course", cascade="all, delete-orphan")


class Module(Base):
    """Course modules - ACTUAL schema"""
    __tablename__ = 'modules'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    course_id = Column(Text, ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    week = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text)
    learning_objectives = Column(ARRAY(Text))
    order_index = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    course = relationship("Course", back_populates="modules")
    topics = relationship("Topic", back_populates="module", cascade="all, delete-orphan")


class Topic(Base):
    """Module topics - ACTUAL schema"""
    __tablename__ = 'topics'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    module_id = Column(Integer, ForeignKey('modules.id', ondelete='CASCADE'), nullable=False)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    order_index = Column(Integer)
    estimated_time = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    module = relationship("Module", back_populates="topics")


class Quiz(Base):
    """Quiz metadata - ACTUAL schema"""
    __tablename__ = 'quizzes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(String, unique=True, nullable=False)
    course_id = Column(Text, ForeignKey('courses.id', ondelete='CASCADE'), nullable=False)
    module_id = Column(Integer, ForeignKey('modules.id', ondelete='SET NULL'))
    title = Column(String, nullable=False)
    description = Column(Text)
    quiz_type = Column(String, default='module')
    passing_score = Column(Integer, default=70)
    time_limit = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    course = relationship("Course", back_populates="quizzes")
    questions = relationship("QuizQuestion", back_populates="quiz", cascade="all, delete-orphan")


class QuizQuestion(Base):
    """Individual quiz questions - ACTUAL schema"""
    __tablename__ = 'quiz_questions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(String, ForeignKey('quizzes.quiz_id', ondelete='CASCADE'), nullable=False)
    question_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSONB, nullable=False)
    correct_answer = Column(String(1), nullable=False)
    explanation = Column(Text)
    difficulty = Column(String)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    quiz = relationship("Quiz", back_populates="questions")


class QuizResponse(Base):
    """User quiz submissions - ACTUAL schema"""
    __tablename__ = 'quiz_responses'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    quiz_id = Column(String, ForeignKey('quizzes.quiz_id', ondelete='CASCADE'), nullable=False)
    user_id = Column(Text, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    answers = Column(JSONB, nullable=False)
    score = Column(Integer)
    total_questions = Column(Integer)
    correct_answers = Column(Integer)
    submitted_at = Column(DateTime, default=datetime.now)
    time_taken = Column(Integer)


class UserProgress(Base):
    """User learning progress - ACTUAL schema"""
    __tablename__ = 'user_progress'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Text, nullable=False)
    course_id = Column(Text, nullable=False)
    module_id = Column(Integer)
    topic_id = Column(Integer)
    status = Column(String, default='not_started')
    progress_percentage = Column(Integer, default=0)
    last_accessed = Column(DateTime, default=datetime.now)
    completion_date = Column(DateTime)


# ============================================================
# DATABASE SERVICE CLASS
# ============================================================

class DatabaseService:
    """Database operations service - ACTUAL schema"""
    
    def __init__(self, database_url: str = None):
        """Initialize database connection"""
        self.database_url = database_url or DATABASE_URL
        
        if not self.database_url:
            raise ValueError("DATABASE_URL not configured")
        
        self.engine = create_engine(
            self.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info("✅ Database service initialized")
    
    @contextmanager
    def get_session(self) -> Session:
        """Context manager for database sessions"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
    
    # ============================================================
    # COURSE OPERATIONS
    # ============================================================
    
    def create_course(self, course_data: Dict[str, Any], teacher_id: str = None) -> str:
        """Create a new course with modules and topics - returns TEXT UUID"""
        with self.get_session() as session:
            # Generate UUID for course
            course_id = str(uuid.uuid4())
            
            # Create course
            course = Course(
                id=course_id,
                title=course_data.get('course_title', 'Untitled Course'),
                description=course_data.get('description', ''),
                teacher_id=teacher_id or 'system',
                level='Beginner',
                is_free=True,
                price=0,
                currency='INR',
                created_by=teacher_id or 'system'
            )
            session.add(course)
            session.flush()  # Get course.id
            
            # Create modules
            for module_data in course_data.get('modules', []):
                module = Module(
                    course_id=course.id,  # TEXT UUID
                    week=module_data.get('week', 1),
                    title=module_data.get('title', ''),
                    description=module_data.get('description', ''),
                    learning_objectives=module_data.get('learning_objectives', []),
                    order_index=module_data.get('week', 1)
                )
                session.add(module)
                session.flush()  # Get module.id
                
                # Create topics
                for idx, topic_data in enumerate(module_data.get('sub_topics', [])):
                    topic = Topic(
                        module_id=module.id,  # Integer
                        title=topic_data.get('title', ''),
                        content=topic_data.get('content', ''),
                        order_index=idx + 1
                    )
                    session.add(topic)
            
            session.commit()
            logger.info(f"✅ Created course: {course.title} (ID: {course.id})")
            return course.id  # Return TEXT UUID
    
    def get_course(self, course_id: str) -> Optional[Dict[str, Any]]:
        """Get course with all modules and topics - accepts TEXT UUID"""
        with self.get_session() as session:
            course = session.query(Course).filter(Course.id == course_id).first()
            
            if not course:
                return None
            
            # Build course structure
            course_dict = {
                'course_id': course.id,  # TEXT UUID
                'course_title': course.title,
                'description': course.description,
                'created_at': course.created_at.isoformat() if course.created_at else None,
                'modules': []
            }
            
            # Add modules
            for module in sorted(course.modules, key=lambda m: m.week):
                module_dict = {
                    'week': module.week,
                    'title': module.title,
                    'description': module.description,
                    'learning_objectives': module.learning_objectives or [],
                    'sub_topics': []
                }
                
                # Add topics
                for topic in sorted(module.topics, key=lambda t: t.order_index or 0):
                    topic_dict = {
                        'title': topic.title,
                        'content': topic.content
                    }
                    module_dict['sub_topics'].append(topic_dict)
                
                course_dict['modules'].append(module_dict)
            
            return course_dict
    
    def list_courses(self, teacher_id: str = None) -> List[Dict[str, Any]]:
        """List all courses"""
        with self.get_session() as session:
            query = session.query(Course)
            
            if teacher_id:
                query = query.filter(Course.teacher_id == teacher_id)
            
            courses = query.all()
            
            return [{
                'course_id': c.id,  # TEXT UUID
                'course_title': c.title,
                'modules': len(c.modules),
                'created_at': c.created_at.isoformat() if c.created_at else None
            } for c in courses]
    
    # ============================================================
    # QUIZ OPERATIONS
    # ============================================================
    
    def create_quiz(self, quiz_data: Dict[str, Any], course_id: str) -> str:
        """Create a quiz with questions - accepts TEXT course_id"""
        with self.get_session() as session:
            # Get module_id if module quiz
            module_id = None
            if quiz_data.get('module_week'):
                module = session.query(Module).filter(
                    Module.course_id == course_id,  # TEXT UUID
                    Module.week == quiz_data['module_week']
                ).first()
                if module:
                    module_id = module.id  # Integer
            
            # Create quiz
            quiz = Quiz(
                quiz_id=quiz_data.get('quiz_id', f"quiz_{uuid.uuid4().hex[:8]}"),
                course_id=course_id,  # TEXT UUID
                module_id=module_id,  # Integer or None
                title=quiz_data.get('title', 'Quiz'),
                quiz_type=quiz_data.get('quiz_type', 'module')
            )
            session.add(quiz)
            session.flush()
            
            # Create questions
            for question_data in quiz_data.get('questions', []):
                question = QuizQuestion(
                    quiz_id=quiz.quiz_id,
                    question_number=question_data.get('question_number', 1),
                    question_text=question_data.get('question', ''),
                    options=question_data.get('options', {}),
                    correct_answer=question_data.get('correct_answer', 'A'),
                    explanation=question_data.get('explanation', '')
                )
                session.add(question)
            
            session.commit()
            logger.info(f"✅ Created quiz: {quiz.quiz_id}")
            return quiz.quiz_id
    
    def get_quiz(self, quiz_id: str) -> Optional[Dict[str, Any]]:
        """Get quiz with all questions"""
        with self.get_session() as session:
            quiz = session.query(Quiz).filter(Quiz.quiz_id == quiz_id).first()
            
            if not quiz:
                return None
            
            return {
                'quiz_id': quiz.quiz_id,
                'title': quiz.title,
                'course_id': quiz.course_id,  # TEXT UUID
                'questions': [{
                    'question_number': q.question_number,
                    'question': q.question_text,
                    'options': q.options,
                    'correct_answer': q.correct_answer,
                    'explanation': q.explanation
                } for q in sorted(quiz.questions, key=lambda q: q.question_number)]
            }


# ============================================================
# SINGLETON INSTANCE
# ============================================================

_db_service = None

def get_database_service() -> Optional[DatabaseService]:
    """Get database service singleton"""
    global _db_service
    
    if not USE_DATABASE:
        logger.warning("Database not enabled (USE_DATABASE=False)")
        return None
    
    if _db_service is None:
        try:
            _db_service = DatabaseService()
            logger.info("✅ Database service singleton created")
        except Exception as e:
            logger.error(f"Failed to initialize database service: {e}")
            return None
    
    return _db_service
