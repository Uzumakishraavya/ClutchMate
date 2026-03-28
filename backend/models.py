from flask_sqlalchemy import SQLAlchemy
import json
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    grade_class = db.Column(db.String(50), nullable=True)
    subjects = db.Column(db.Text, default='[]')  # JSON list
    current_grades = db.Column(db.Text, default='{}')  # JSON object
    goals = db.Column(db.Text, default='{}')  # JSON object

    def __init__(self, name, email, password):
        self.name = name
        self.email = email
        self.password = password

    # def generate_username(self):
    #     """Generate a username from the name"""
    #     # base_name = self.name.split()[0].lower()  # First name
    #     # return base_name

    @property
    def subjects_list(self):
        return json.loads(self.subjects) if self.subjects else []

    @subjects_list.setter
    def subjects_list(self, value):
        self.subjects = json.dumps(value) if value else '[]'

    @property
    def grades_dict(self):
        return json.loads(self.current_grades) if self.current_grades else {}

    @grades_dict.setter
    def grades_dict(self, value):
        self.current_grades = json.dumps(value) if value else '{}'

    @property
    def goals_dict(self):
        return json.loads(self.goals) if self.goals else {}

    @goals_dict.setter
    def goals_dict(self, value):
        self.goals = json.dumps(value) if value else '{}'

class StudySession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(100), nullable=False)
    topic = db.Column(db.String(200))  # Optional specific topic
    duration = db.Column(db.Integer, default=0)  # in seconds
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime)
    date = db.Column(db.Date, default=datetime.utcnow().date)

    def __init__(self, user_id, subject, topic=None, duration=0):
        self.user_id = user_id
        self.subject = subject
        self.topic = topic
        self.duration = duration

class StudyPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan = db.Column(db.Text, default='[]')
    syllabus = db.Column(db.Text, default='[]')
    exam_date = db.Column(db.String(50))

    def __init__(self, user_id, plan='[]', syllabus='[]', exam_date=''):
        self.user_id = user_id
        self.plan = plan
        self.syllabus = syllabus
        self.exam_date = exam_date

class TimetableEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day = db.Column(db.String(20), default='Monday')
    start_time = db.Column(db.String(10), default='08:00')
    end_time = db.Column(db.String(10), default='09:00')
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(100), default='General')
    category = db.Column(db.String(80), default='Study')
    notes = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, user_id, title, day='Monday', start_time='08:00', end_time='09:00', subject='General', category='Study', notes=''):
        self.user_id = user_id
        self.day = day
        self.start_time = start_time
        self.end_time = end_time
        self.title = title
        self.subject = subject
        self.category = category
        self.notes = notes

class PerformanceData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    marks = db.Column(db.Text, default='{}')
    weak_areas = db.Column(db.Text, default='[]')
    trends = db.Column(db.Text, default='[]')

    def __init__(self, user_id, marks='{}', weak_areas='[]', trends='[]'):
        self.user_id = user_id
        self.marks = marks
        self.weak_areas = weak_areas
        self.trends = trends

class KnowledgeMap(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    graph_data = db.Column(db.Text, default='{}')

    def __init__(self, user_id, graph_data='{}'):
        self.user_id = user_id
        self.graph_data = graph_data

class CognitiveProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    learning_speed = db.Column(db.Float, default=1.0)
    memory_strength = db.Column(db.Text, default='{}')
    forgetting_risk = db.Column(db.Float, default=0.5)

    def __init__(self, user_id, learning_speed=1.0, memory_strength='{}', forgetting_risk=0.5):
        self.user_id = user_id
        self.learning_speed = learning_speed
        self.memory_strength = memory_strength
        self.forgetting_risk = forgetting_risk

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    deadline = db.Column(db.DateTime, nullable=False)
    completed = db.Column(db.Boolean, default=False)
    subject = db.Column(db.String(100), nullable=True)

    def __init__(self, user_id, title, deadline, subject=None):
        self.user_id = user_id
        self.title = title
        self.deadline = deadline
        self.subject = subject or ''

class StudyMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    subject = db.Column(db.String(100), default='General')
    material_type = db.Column(db.String(50), default='notes')
    file_path = db.Column(db.String(255), nullable=True)
    original_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, user_id, title, description='', subject='General', material_type='notes', file_path=None, original_filename=None):
        self.user_id = user_id
        self.title = title
        self.description = description
        self.subject = subject
        self.material_type = material_type
        self.file_path = file_path
        self.original_filename = original_filename

class PaperAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    extracted_text = db.Column(db.Text, default='')
    analysis = db.Column(db.Text, default='')
    syllabus_text = db.Column(db.Text, default='')
    source = db.Column(db.String(50), default='google_vision')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, user_id, extracted_text='', analysis='', syllabus_text='', source='google_vision'):
        self.user_id = user_id
        self.extracted_text = extracted_text
        self.analysis = analysis
        self.syllabus_text = syllabus_text
        self.source = source

class MoodEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    mood = db.Column(db.String(50), nullable=False)
    note = db.Column(db.Text, default='')
    sleep_hours = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, user_id, mood, note='', sleep_hours=None):
        self.user_id = user_id
        self.mood = mood
        self.note = note
        self.sleep_hours = sleep_hours

class ReflectionEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stressors = db.Column(db.Text, default='')
    wins = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, user_id, stressors='', wins=''):
        self.user_id = user_id
        self.stressors = stressors
        self.wins = wins

class CommunityPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    subject = db.Column(db.String(100), default='General')
    likes = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, user_id, title, content, subject='General'):
        self.user_id = user_id
        self.title = title
        self.content = content
        self.subject = subject

class CommunityComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('community_post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, post_id, user_id, content):
        self.post_id = post_id
        self.user_id = user_id
        self.content = content

class BehaviorTracking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    study_time = db.Column(db.Integer, default=0)  # in minutes - daily total
    completed_tasks = db.Column(db.Integer, default=0)
    skipped_tasks = db.Column(db.Integer, default=0)
    date = db.Column(db.Date, default=datetime.utcnow().date)

    def __init__(self, user_id, study_time=0, completed_tasks=0, skipped_tasks=0):
        self.user_id = user_id
        self.study_time = study_time
        self.completed_tasks = completed_tasks
        self.skipped_tasks = skipped_tasks

class Gamification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    xp = db.Column(db.Integer, default=0)
    streak = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    badges = db.Column(db.Text, default='[]')  # JSON list

    def __init__(self, user_id, xp=0, streak=0, level=1, badges=None):
        self.user_id = user_id
        self.xp = xp
        self.streak = streak
        self.level = level
        self.badges = json.dumps(badges) if badges else '[]'

    @property
    def badges_list(self):
        return json.loads(self.badges) if self.badges else []

    @badges_list.setter
    def badges_list(self, value):
        self.badges = json.dumps(value) if value else '[]'

class MeditationSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    duration = db.Column(db.Integer, default=10)  # in minutes
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __init__(self, user_id, title, duration=10):
        self.user_id = user_id
        self.title = title
        self.duration = duration