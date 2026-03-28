from flask import Flask, request, jsonify, send_file, send_from_directory, redirect, session, url_for
from flask_cors import CORS
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import sys
import json
import re
import ast
import operator
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))
from models import db, User, StudyPlan, TimetableEntry, PerformanceData, KnowledgeMap, CognitiveProfile, Assignment, StudyMaterial, CommunityPost, CommunityComment, BehaviorTracking, Gamification, MeditationSession, StudySession, PaperAnalysis, MoodEntry, ReflectionEntry
import requests
from google_auth_oauthlib.flow import Flow
import secrets
from dotenv import load_dotenv
import datetime
import random
import networkx as nx
import matplotlib.pyplot as plt
import io
import base64
from sqlalchemy import text, func
from urllib.parse import urlencode

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')
load_dotenv()

app = Flask(__name__, static_folder='../frontend', static_url_path='')

# Configuration
INSTANCE_DIR = BASE_DIR / 'instance'
os.makedirs(INSTANCE_DIR, exist_ok=True)
DB_PATH = INSTANCE_DIR / 'clutchmate.db'

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', secrets.token_hex(16))
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_PATH.resolve().as_posix()}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = False

UPLOAD_FOLDER = BASE_DIR / 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Google OAuth Configuration
GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
GOOGLE_REDIRECT_URI = os.environ.get('GOOGLE_REDIRECT_URI', '').strip()
SCOPES = ['profile', 'email']

# Initialize extensions
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True, expose_headers=["Authorization"], allow_headers=["Content-Type", "Authorization"])
jwt = JWTManager(app)
db.init_app(app)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '').strip()
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')
N8N_WEBHOOK_URL = os.environ.get('N8N_WEBHOOK_URL', '').strip()
N8N_WEBHOOK_SECRET = os.environ.get('N8N_WEBHOOK_SECRET', '').strip()
N8N_TIMEOUT_SECONDS = float(os.environ.get('N8N_TIMEOUT_SECONDS', '8'))
AUTOMATION_API_SECRET = os.environ.get('AUTOMATION_API_SECRET', '').strip()


def serialize_user_for_n8n(user):
    subjects = json.loads(user.subjects) if user.subjects else []
    goals = json.loads(user.goals) if user.goals else {}
    return {
        'id': user.id,
        'name': user.name,
        'email': user.email,
        'grade_class': get_optional_user_attr(user, 'grade_class'),
        'subjects': subjects,
        'goals': goals
    }


def serialize_assignment_for_n8n(assignment):
    return {
        'id': assignment.id,
        'user_id': assignment.user_id,
        'title': assignment.title,
        'subject': assignment.subject or 'General',
        'deadline': assignment.deadline.isoformat() if assignment.deadline else None,
        'completed': bool(assignment.completed)
    }


def format_deadline_for_email(deadline_iso):
    if not deadline_iso:
        return 'an upcoming deadline'

    try:
        normalized = deadline_iso.replace('Z', '+00:00')
        parsed = datetime.datetime.fromisoformat(normalized)
        return parsed.strftime('%A, %b %d at %I:%M %p UTC')
    except (ValueError, TypeError):
        return deadline_iso


def build_assignment_email_templates(user_payload, assignment_payload):
    user_name = user_payload.get('name') or 'there'
    title = assignment_payload.get('title') or 'your assignment'
    subject = assignment_payload.get('subject') or 'General'
    deadline_text = format_deadline_for_email(assignment_payload.get('deadline'))

    subject_line = f'ClutchMate reminder: {title} is due soon'
    text_body = (
        f"Hi {user_name},\n\n"
        "Here is a quick reminder from ClutchMate.\n\n"
        "------------------------------\n"
        f"Assignment: {title}\n"
        f"Subject:    {subject}\n"
        f"Due:        {deadline_text}\n"
        "------------------------------\n\n"
        "Try to give it a focused push before the deadline.\n\n"
        "Stay steady,\n"
        "ClutchMate"
    )
    html_body = (
        "<div style=\"font-family:Arial,Helvetica,sans-serif; color:#172033; line-height:1.6; max-width:560px;\">"
        f"<p style=\"margin:0 0 16px 0;\">Hi {user_name},</p>"
        "<p style=\"margin:0 0 16px 0;\">Here is a quick reminder from <strong>ClutchMate</strong>.</p>"
        "<div style=\"padding:16px 18px; border-radius:14px; background:#f8fbff; border:1px solid #dbeafe; margin:0 0 18px 0;\">"
        f"<p style=\"margin:0 0 10px 0;\"><strong>Assignment:</strong><br>{title}</p>"
        f"<p style=\"margin:0 0 10px 0;\"><strong>Subject:</strong><br>{subject}</p>"
        f"<p style=\"margin:0;\"><strong>Due:</strong><br>{deadline_text}</p>"
        "</div>"
        "<p style=\"margin:0 0 16px 0;\">Try to give it a focused push before the deadline.</p>"
        "<p style=\"margin:0;\">Stay steady,<br><strong>ClutchMate</strong></p>"
        "</div>"
    )

    return {
        'assignment_reminder_subject': subject_line,
        'assignment_reminder_text': text_body,
        'assignment_reminder_html': html_body
    }


def build_daily_summary_email_templates(summary_payload):
    user_name = summary_payload['user'].get('name') or 'there'
    summary_date = summary_payload.get('summary_date') or datetime.date.today().isoformat()
    text_body = (
        f"Hi {user_name},\n\n"
        f"Here is your ClutchMate daily summary for {summary_date}.\n\n"
        "------------------------------\n"
        f"Study time today: {summary_payload.get('today_study_minutes', 0)} minutes\n"
        f"Pending tasks:    {summary_payload.get('pending_assignment_count', 0)}\n"
        f"Overdue:          {summary_payload.get('overdue_count', 0)}\n"
        f"Due today:        {summary_payload.get('due_today_count', 0)}\n"
        f"Due tomorrow:     {summary_payload.get('due_tomorrow_count', 0)}\n"
        "------------------------------\n\n"
        "Keep momentum with one small focused session today.\n\n"
        "ClutchMate"
    )
    html_body = (
        "<div style=\"font-family:Arial,Helvetica,sans-serif; color:#172033; line-height:1.6; max-width:560px;\">"
        f"<p style=\"margin:0 0 16px 0;\">Hi {user_name},</p>"
        f"<p style=\"margin:0 0 16px 0;\">Here is your ClutchMate daily summary for <strong>{summary_date}</strong>.</p>"
        "<div style=\"padding:16px 18px; border-radius:14px; background:#f8fbff; border:1px solid #dbeafe; margin:0 0 18px 0;\">"
        f"<p style=\"margin:0 0 10px 0;\"><strong>Study time today:</strong> {summary_payload.get('today_study_minutes', 0)} minutes</p>"
        f"<p style=\"margin:0 0 10px 0;\"><strong>Pending assignments:</strong> {summary_payload.get('pending_assignment_count', 0)}</p>"
        f"<p style=\"margin:0 0 10px 0;\"><strong>Overdue:</strong> {summary_payload.get('overdue_count', 0)}</p>"
        f"<p style=\"margin:0 0 10px 0;\"><strong>Due today:</strong> {summary_payload.get('due_today_count', 0)}</p>"
        f"<p style=\"margin:0;\"><strong>Due tomorrow:</strong> {summary_payload.get('due_tomorrow_count', 0)}</p>"
        "</div>"
        "<p style=\"margin:0 0 16px 0;\">Keep momentum with one small focused session today.</p>"
        "<p style=\"margin:0;\"><strong>ClutchMate</strong></p>"
        "</div>"
    )

    return {
        'daily_summary_subject': f'Your ClutchMate daily summary for {summary_date}',
        'daily_summary_text': text_body,
        'daily_summary_html': html_body
    }


def send_n8n_event(event_type, payload):
    if not N8N_WEBHOOK_URL:
        return False

    headers = {'Content-Type': 'application/json'}
    if N8N_WEBHOOK_SECRET:
        headers['X-ClutchMate-Secret'] = N8N_WEBHOOK_SECRET

    body = {
        'source': 'clutchmate-backend',
        'event_type': event_type,
        'sent_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'payload': payload
    }

    try:
        response = requests.post(
            N8N_WEBHOOK_URL,
            json=body,
            headers=headers,
            timeout=N8N_TIMEOUT_SECONDS
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        app.logger.warning('n8n webhook failed for %s: %s', event_type, exc)
        return False


def has_valid_automation_secret(req):
    if not AUTOMATION_API_SECRET:
        return False
    supplied = (req.headers.get('X-Automation-Secret') or '').strip()
    return bool(supplied) and secrets.compare_digest(supplied, AUTOMATION_API_SECRET)


def build_daily_summary_payload(user):
    today = datetime.date.today()
    tomorrow = today + datetime.timedelta(days=1)
    assignments = db.session.query(Assignment).filter_by(user_id=user.id).order_by(Assignment.deadline.asc()).all()
    today_tracking = db.session.query(BehaviorTracking).filter_by(user_id=user.id, date=today).first()
    today_study_minutes = today_tracking.study_time if today_tracking else 0

    pending_assignments = [assignment for assignment in assignments if not assignment.completed]
    overdue = [assignment for assignment in pending_assignments if assignment.deadline.date() < today]
    due_today = [assignment for assignment in pending_assignments if assignment.deadline.date() == today]
    due_tomorrow = [assignment for assignment in pending_assignments if assignment.deadline.date() == tomorrow]
    upcoming = [assignment for assignment in pending_assignments if assignment.deadline.date() > tomorrow][:5]

    summary_payload = {
        'user': serialize_user_for_n8n(user),
        'summary_date': today.isoformat(),
        'today_study_minutes': today_study_minutes,
        'pending_assignment_count': len(pending_assignments),
        'overdue_count': len(overdue),
        'due_today_count': len(due_today),
        'due_tomorrow_count': len(due_tomorrow),
        'overdue_assignments': [serialize_assignment_for_n8n(item) for item in overdue[:5]],
        'due_today_assignments': [serialize_assignment_for_n8n(item) for item in due_today[:5]],
        'due_tomorrow_assignments': [serialize_assignment_for_n8n(item) for item in due_tomorrow[:5]],
        'upcoming_assignments': [serialize_assignment_for_n8n(item) for item in upcoming]
    }

    summary_payload['email_templates'] = build_daily_summary_email_templates(summary_payload)
    return summary_payload


def get_openai_response(prompt, system_prompt=None, max_tokens=650, temperature=0.7):
    if not OPENAI_API_KEY:
        return None
    try:
        headers = {
            'Authorization': f'Bearer {OPENAI_API_KEY}',
            'Content-Type': 'application/json'
        }
        payload = {
            'model': OPENAI_MODEL,
            'messages': [
                {'role': 'system', 'content': system_prompt or 'You are a friendly, concise AI tutor that helps students understand academic concepts.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': temperature,
            'max_tokens': max_tokens
        }
        response = requests.post('https://api.openai.com/v1/chat/completions', json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content'].strip()
    except Exception as exc:
        app.logger.warning('OpenAI request failed: %s', exc)
        return None


def analyze_image_with_google_vision(image_bytes):
    api_key = os.environ.get('GOOGLE_VISION_API_KEY', '').strip()
    if not api_key:
        return {'text': '', 'error': 'Google Vision API key is not configured.'}

    try:
        vision_url = f'https://vision.googleapis.com/v1/images:annotate?key={api_key}'
        encoded_image = base64.b64encode(image_bytes).decode('utf-8')
        payload = {
            'requests': [
                {
                    'image': {'content': encoded_image},
                    'features': [
                        {'type': 'DOCUMENT_TEXT_DETECTION', 'maxResults': 1}
                    ]
                }
            ]
        }
        response = requests.post(vision_url, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        text = data.get('responses', [{}])[0].get('fullTextAnnotation', {}).get('text', '')
        return {'text': text or '', 'error': None}
    except requests.HTTPError as exc:
        error_text = ''
        try:
            error_text = exc.response.json().get('error', {}).get('message', str(exc))
        except Exception:
            error_text = str(exc)
        app.logger.warning('Google Vision REST request failed: %s', error_text)
        return {'text': '', 'error': f'Google Vision error: {error_text}'}
    except Exception as exc:
        app.logger.warning('Google Vision REST request failed: %s', exc)
        return {'text': '', 'error': f'Google Vision error: {exc}'}


def build_paper_analysis_prompt(extracted_text, syllabus_text=''):
    prompt = (
        'You are a student tutor assistant. The user has uploaded a scanned test paper. ' 
        'The scanned text is below. Identify likely mistakes, wrong answers, misconceptions, and suggest how to correct them. ' 
        'If the text contains student answers or calculations, point out the exact errors and provide the correct reasoning. ' 
        'Keep the response concise and helpful, and label any detected mistakes clearly.\n\n' 
        f'Text extracted from paper:\n{extracted_text}'
    )
    if syllabus_text and syllabus_text.strip():
        prompt += (
            '\n\nUse the following syllabus or course topic notes to prioritize the analysis and relate mistakes to the most relevant subjects:\n'
            f'{syllabus_text}'
        )
    return prompt


def fallback_paper_analysis(extracted_text):
    if not extracted_text or extracted_text.strip() == '':
        return 'No readable text was found on the uploaded paper. Please upload a clearer image or crop the paper to only the relevant portion.'

    sentences = [s.strip() for s in re.split(r'[\n\.!?]+', extracted_text) if s.strip()]
    mistakes = []
    for sentence in sentences:
        if re.search(r'\b(ans(?:wer)?|solution|incorrect|wrong|mistake|error|fail|not right|does not|doesnt)\b', sentence, re.I):
            mistakes.append(sentence)
        elif re.search(r'\b\d+\s*[+=-]\s*\d+\b', sentence) and re.search(r'wrong|incorrect|not correct|mistaken', extracted_text, re.I):
            mistakes.append(sentence)

    if mistakes:
        return (
            'Detected potential problem areas from the scanned text:\n' + '\n'.join(f'- {m}' for m in mistakes) +
            '\n\nIf you want, upload a clearer image or provide the student answer and correct answer for more precise grading.'
        )

    summary = sentences[:3]
    return (
        'The paper text was extracted, but no explicit mistake markers were found. ' 
        'Review the following content carefully for incorrect calculations, swapped signs, or misunderstandings:\n' 
        + '\n'.join(f'- {line}' for line in summary)
    )


def extract_paper_mistake_patterns(analysis_text):
    if not analysis_text:
        return []

    lines = [line.strip() for line in re.split(r'[\r\n]+|\.\s+', analysis_text) if line.strip()]
    patterns = []
    for line in lines:
        if re.search(r'\b(error|mistake|incorrect|wrong|misconception|confusion|misread|missing|forgot|not clear)\b', line, re.I):
            patterns.append(line)
        elif len(patterns) < 2 and len(line) > 20:
            patterns.append(line)

    if not patterns and lines:
        patterns = lines[:3]

    return [p if p.endswith('.') else f'{p}.' for p in patterns[:5]]


def compute_mental_health(user_id, average_score, assignments, today_study_minutes, grades):
    today = datetime.date.today()
    mood_entries = db.session.query(MoodEntry).filter_by(user_id=user_id).order_by(MoodEntry.created_at.desc()).all()
    reflection_recent = db.session.query(ReflectionEntry).filter(ReflectionEntry.user_id == user_id, ReflectionEntry.created_at >= datetime.datetime.utcnow() - datetime.timedelta(days=7)).all()

    mood_counts = {'good': 0, 'okay': 0, 'stressed': 0, 'overwhelmed': 0}
    recent_moods = []
    mood_days = set()
    today_mood = None

    for entry in mood_entries:
        mood = entry.mood.lower()
        if mood in mood_counts:
            mood_counts[mood] += 1
        if entry.created_at.date() == today and not today_mood:
            today_mood = mood
        if entry.created_at.date() >= today - datetime.timedelta(days=6):
            recent_moods.append(mood)
            mood_days.add(entry.created_at.date())

    missed_tasks = sum(1 for a in assignments if not a.completed and a.deadline.date() < today)
    completed_tasks = sum(1 for a in assignments if a.completed)
    total_assignments = len(assignments)
    completion_rate = int((completed_tasks / total_assignments) * 100) if total_assignments else 100

    stress_ratio = sum(1 for mood in recent_moods if mood in ['stressed', 'overwhelmed']) / max(len(recent_moods), 1)
    consistency_score = int(min(100, max(10, (len(mood_days) / 7) * 100)))
    high_performance = average_score >= 80

    burnout_risk = (today_mood in ['stressed', 'overwhelmed'] and missed_tasks >= 2) or (stress_ratio >= 0.5 and missed_tasks >= 3)
    overload_risk = stress_ratio >= 0.5 and consistency_score >= 40
    optimal_zone = today_mood == 'good' and high_performance and missed_tasks == 0

    if burnout_risk:
        state_label = 'Burnout risk'
        recommendation = 'Reduce today’s workload, start with one easy topic, then take a 10-minute reset.'
        coach_message = 'Your body is asking for a lighter day. Focus on consistency instead of urgency.'
    elif overload_risk:
        state_label = 'Overload warning'
        recommendation = 'Keep the plan steady, add a short calming break, and do one easy review first.'
        coach_message = 'You are pushing hard; a small reset now can preserve your momentum.'
    elif optimal_zone:
        state_label = 'Optimal zone'
        recommendation = 'Keep the momentum and try a slightly harder challenge today.'
        coach_message = 'You are balancing performance and mood well. Build on this with one stretch task.'
    elif today_mood == 'okay':
        state_label = 'Steady progress'
        recommendation = 'Maintain your current schedule and stay mindful of your energy.'
        coach_message = 'You are in a good place to keep the plan consistent with light motivation.'
    else:
        state_label = 'Needs attention'
        recommendation = 'Track your mood tomorrow, keep tasks small, and use a quick reset tool if stress grows.'
        coach_message = 'Small adjustments today can prevent a harder day tomorrow.'

    tool_list = [
        {'name': '2-min reset', 'description': 'Guided breathing to calm your mind quickly.'},
        {'name': 'Focus mode', 'description': 'Set a short distraction-free study timer.'},
        {'name': 'Emergency calm', 'description': 'A fast grounding routine for overwhelmed moments.'}
    ]

    return {
        'today_mood': today_mood,
        'mood_counts': mood_counts,
        'consistency_score': consistency_score,
        'missed_tasks': missed_tasks,
        'completion_rate': completion_rate,
        'homework_days': len(mood_days),
        'state_label': state_label,
        'burnout_risk': burnout_risk,
        'overload_risk': overload_risk,
        'optimal_zone': optimal_zone,
        'recommendation': recommendation,
        'coach_message': coach_message,
        'quick_tools': tool_list,
        'reflection_needed': len(reflection_recent) == 0,
        'weekly_reflection_prompt': 'What stressed you most this week? What went well?',
        'recent_mood_history': [
            {
                'created_at': entry.created_at.isoformat(),
                'mood': entry.mood,
                'sleep_hours': entry.sleep_hours,
                'note': entry.note
            }
            for entry in mood_entries[:7]
        ]
    }


SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos
}


def safe_eval_math_expression(expression):
    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Num):
            return node.n
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError('Unsupported expression')

    parsed = ast.parse(expression, mode='eval')
    return _eval(parsed)


def extract_math_expression(prompt):
    normalized = prompt.lower().replace('^', '**').replace('x', '*')
    match = re.search(r'([-+/*().\d\s]{3,}|\d[\d\s+\-/*().]*\d)', normalized)
    if not match:
        return None

    expression = ''.join(ch for ch in match.group(0) if ch in '0123456789+-*/().% ')
    expression = re.sub(r'\s+', ' ', expression).strip()
    if not expression or not re.search(r'\d', expression):
        return None
    return expression


def build_practice_questions(topic, subject):
    topic_label = topic or 'this topic'
    if subject == 'math':
        return [
            f'1. Solve one basic example involving {topic_label}.',
            f'2. Try a medium question and explain each step in words.',
            f'3. Create one mistake you might make in {topic_label} and correct it.'
        ]
    if subject == 'science':
        return [
            f'1. Define {topic_label} in one or two sentences.',
            '2. Draw or imagine a labeled diagram/process flow.',
            '3. Explain one real-life application or effect.'
        ]
    if subject == 'history':
        return [
            f'1. What happened in {topic_label}?',
            f'2. Why was {topic_label} important?',
            f'3. What was one short-term and one long-term effect of {topic_label}?'
        ]
    return [
        f'1. Write a 2-line explanation of {topic_label}.',
        f'2. Give one example connected to {topic_label}.',
        f'3. List one doubt you still have about {topic_label}.'
    ]


LOCAL_TOPIC_GUIDES = {
    'photosynthesis': (
        "Photosynthesis is the process plants use to make their own food.\n\n"
        "Step by step:\n"
        "1. The plant takes in sunlight with chlorophyll in the leaves.\n"
        "2. It absorbs water from the soil through the roots.\n"
        "3. It takes in carbon dioxide from the air.\n"
        "4. Using sunlight energy, it changes water and carbon dioxide into glucose, which is food for the plant.\n"
        "5. Oxygen is released into the air as a by-product.\n\n"
        "Easy memory trick:\n"
        "Sunlight + water + carbon dioxide -> food (glucose) + oxygen."
    ),
    'pythagorean theorem': (
        "The Pythagorean theorem is used in right-angled triangles.\n\n"
        "Rule:\n"
        "a^2 + b^2 = c^2\n\n"
        "Here, a and b are the shorter sides, and c is the longest side called the hypotenuse.\n\n"
        "Example:\n"
        "If the two shorter sides are 3 and 4, then:\n"
        "3^2 + 4^2 = 9 + 16 = 25\n"
        "c = 5"
    ),
    'newton first law': (
        "Newton's first law says that an object will stay at rest or keep moving at the same speed in a straight line unless an external force acts on it.\n\n"
        "Simple idea:\n"
        "Things do not change their motion by themselves.\n\n"
        "Example:\n"
        "A football stays still until someone kicks it."
    ),
    'mitosis': (
        "Mitosis is the process a cell uses to make two identical daughter cells.\n\n"
        "Main stages:\n"
        "1. Prophase: chromosomes become visible.\n"
        "2. Metaphase: chromosomes line up in the middle.\n"
        "3. Anaphase: chromosome copies are pulled apart.\n"
        "4. Telophase: two nuclei form.\n"
        "5. Cytokinesis: the cell splits into two."
    ),
    'democracy': (
        "Democracy is a system of government in which people choose their leaders by voting.\n\n"
        "Key idea:\n"
        "Power ultimately comes from the people.\n\n"
        "Main features:\n"
        "1. Elections\n"
        "2. Rule of law\n"
        "3. Rights and freedoms\n"
        "4. Accountability of leaders"
    )
}


def build_local_tutor_response(prompt, subjects=None):
    lower_prompt = prompt.lower()
    subjects = subjects or []

    subject = 'general'
    if any(word in lower_prompt for word in ['math', 'algebra', 'geometry', 'equation', 'solve', 'calculate']):
        subject = 'math'
    elif any(word in lower_prompt for word in ['science', 'physics', 'chemistry', 'biology']):
        subject = 'science'
    elif any(word in lower_prompt for word in ['history', 'war', 'civilization', 'revolution']):
        subject = 'history'
    elif any(word in lower_prompt for word in ['english', 'grammar', 'essay', 'poem', 'literature']):
        subject = 'english'
    elif any(word in lower_prompt for word in ['computer', 'programming', 'python', 'code', 'algorithm']):
        subject = 'computer science'
    elif subjects:
        subject = subjects[0]

    topic_match = re.search(r'(?:about|on|for|of)\s+([a-zA-Z0-9\s\-]{3,60})', prompt, re.IGNORECASE)
    topic = topic_match.group(1).strip(' .?!') if topic_match else prompt.strip(' .?!')

    for key, guide in LOCAL_TOPIC_GUIDES.items():
        if key in lower_prompt:
            return (
                f"{guide}\n\n"
                f"If you want, I can also give you a shorter revision note, a diagram-style summary, or practice questions on {key}."
            )

    if subject == 'math':
        expression = extract_math_expression(prompt)
        if expression:
            try:
                result = safe_eval_math_expression(expression)
                return (
                    f"Let's solve it step by step.\n\n"
                    f"Problem: {expression}\n"
                    f"Answer: {result}\n\n"
                    f"Method:\n"
                    f"1. Read the expression carefully.\n"
                    f"2. Apply brackets, powers, multiplication/division, then addition/subtraction.\n"
                    f"3. Recheck the sign of each term.\n\n"
                    f"Want me to break down each operation one line at a time?"
                )
            except Exception:
                pass

    if any(phrase in lower_prompt for phrase in ['practice question', 'practice questions', 'quiz me', 'test me']):
        questions = '\n'.join(build_practice_questions(topic, subject))
        return (
            f"Here are practice questions for {topic}:\n\n"
            f"{questions}\n\n"
            f"If you want, I can also turn these into multiple-choice or give model answers."
        )

    subject_openers = {
        'math': f"{topic} becomes easier when you treat it like a sequence of small steps instead of one big jump.",
        'science': f"{topic} is easiest to learn by focusing on what it is, how it works, and where you see it in real life.",
        'history': f"{topic} makes more sense when you organize it into cause, event, and impact.",
        'english': f"{topic} is easier when you identify the main idea first and then support it with clear evidence or examples.",
        'computer science': f"{topic} is best understood by combining the idea, the process, and one small example.",
        'general': f"Let's break down {topic} into a simple study guide."
    }

    return (
        f"{subject_openers.get(subject, subject_openers['general'])}\n\n"
        f"Simple explanation:\n"
        f"- Start by defining the core idea in one sentence.\n"
        f"- Identify the main parts, steps, or causes involved.\n"
        f"- Connect it to one familiar example so it is easier to remember.\n\n"
        f"How to study it:\n"
        f"1. Say the idea in your own words.\n"
        f"2. Write 3 key points you must remember.\n"
        f"3. Test yourself without looking at notes.\n\n"
        f"Quick example:\n"
        f"If you share the exact chapter, question, or problem from {subject}, I can give you a much more precise step-by-step answer."
    )


def model_has_column(model, column_name):
    return column_name in model.__table__.columns.keys()


def ensure_user_columns():
    inspector = db.session.execute(text("PRAGMA table_info(user);"))
    existing_columns = [row[1] for row in inspector.fetchall()]
    if 'username' not in existing_columns:
        db.session.execute(text("ALTER TABLE user ADD COLUMN username VARCHAR(50);"))
    if 'grade_class' not in existing_columns:
        db.session.execute(text("ALTER TABLE user ADD COLUMN grade_class VARCHAR(50);"))
    db.session.commit()


def ensure_study_material_columns():
    inspector = db.session.execute(text("PRAGMA table_info(study_material);"))
    existing_columns = [row[1] for row in inspector.fetchall()]
    if 'file_path' not in existing_columns:
        db.session.execute(text("ALTER TABLE study_material ADD COLUMN file_path VARCHAR(255);"))
    if 'original_filename' not in existing_columns:
        db.session.execute(text("ALTER TABLE study_material ADD COLUMN original_filename VARCHAR(255);"))
    db.session.commit()


def ensure_assignment_columns():
    inspector = db.session.execute(text("PRAGMA table_info(assignment);"))
    existing_columns = [row[1] for row in inspector.fetchall()]
    if 'subject' not in existing_columns:
        db.session.execute(text("ALTER TABLE assignment ADD COLUMN subject VARCHAR(100);"))
    db.session.commit()

def ensure_paper_analysis_columns():
    inspector = db.session.execute(text("PRAGMA table_info(paper_analysis);"))
    existing_columns = [row[1] for row in inspector.fetchall()]
    if 'syllabus_text' not in existing_columns:
        db.session.execute(text("ALTER TABLE paper_analysis ADD COLUMN syllabus_text TEXT DEFAULT ''"))
    db.session.commit()

with app.app_context():
    db.create_all()
    ensure_user_columns()
    ensure_study_material_columns()
    ensure_assignment_columns()
    ensure_paper_analysis_columns()


def get_optional_user_attr(user, attr_name, default=None):
    return getattr(user, attr_name, default) if hasattr(user, attr_name) else default


def build_google_client_config():
    redirect_uri = get_google_redirect_uri()
    return {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri]
        }
    }


def login_redirect_with_error(message):
    return redirect(f"/login?{urlencode({'error': message})}")


def get_google_redirect_uri():
    if GOOGLE_REDIRECT_URI:
        return GOOGLE_REDIRECT_URI
    return url_for('google_callback', _external=True)

# Serve frontend HTML files
FRONTEND_PATH = Path(__file__).parent.parent / 'frontend'

@app.route('/')
def home():
    return send_file(str(FRONTEND_PATH / 'landingpage.html'))

@app.route('/landing')
def landing_page():
    return send_file(str(FRONTEND_PATH / 'landingpage.html'))

@app.route('/login')
def login_page():
    return send_file(str(FRONTEND_PATH / 'login2.html'))

@app.route('/signup')
def signup_page():
    return send_file(str(FRONTEND_PATH / 'signup2.html'))

@app.route('/personalize')
def personalize_page():
    return send_file(str(FRONTEND_PATH / 'personalizationform.html'))

@app.route('/dashboard')
def dashboard_page():
    return send_file(str(FRONTEND_PATH / 'dashboard2.html'))

@app.route('/study-plan')
def study_plan_page():
    return send_file(str(FRONTEND_PATH / 'dashboard2.html'))  # All in one dashboard

@app.route('/performance')
def performance_page():
    return send_file(str(FRONTEND_PATH / 'dashboard2.html'))

@app.route('/knowledge-map')
def knowledge_map_page():
    return send_file(str(FRONTEND_PATH / 'dashboard2.html'))

@app.route('/ai-tutor')
def ai_tutor_page():
    return send_file(str(FRONTEND_PATH / 'dashboard2.html'))

@app.route('/assignments')
def assignments_page():
    return send_file(str(FRONTEND_PATH / 'dashboard2.html'))

@app.route('/meditation')
def meditation_page():
    return send_file(str(FRONTEND_PATH / 'dashboard2.html'))

@app.route('/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Missing required fields'}), 400

    name = (data.get('name') or '').strip()
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    username = (data.get('username') or '').strip() or None

    if not name or not email or not password:
        return jsonify({'error': 'Missing required fields'}), 400

    # Normalize and check if user already exists by email
    if db.session.query(User).filter(func.lower(User.email) == email).first():
        return jsonify({'error': 'Email already registered'}), 409

    if username and db.session.query(User).filter(func.lower(User.username) == username.lower()).first():
        return jsonify({'error': 'Username already taken'}), 409

    # Create new user
    hashed_password = generate_password_hash(password)
    new_user = User(
        name=name,
        email=email,
        password=hashed_password
    )
    if username:
        new_user.username = username

    db.session.add(new_user)
    db.session.commit()

    send_n8n_event('user.signup', {
        'user': serialize_user_for_n8n(new_user)
    })

    # Auto-login user after signup
    access_token = create_access_token(identity=str(new_user.id))
    return jsonify({
        'message': 'User created successfully',
        'token': access_token,
        'user_id': new_user.id
    }), 201

@app.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()

    if not data or not all(k in data for k in ['email', 'password']):
        return jsonify({'error': 'Missing email or password'}), 400

    user = db.session.query(User).filter_by(email=data['email']).first()

    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'error': 'Invalid email or password'}), 401

    access_token = create_access_token(identity=str(user.id))

    return jsonify({
        'token': access_token,
        'user_id': user.id,
        'message': 'Login successful'
    }), 200

@app.route('/auth/google')
def google_login():
    """Initiate Google OAuth flow"""
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return login_redirect_with_error('Google OAuth is not configured on the server yet.')

    client_config = build_google_client_config()

    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=get_google_redirect_uri()
    )
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )
    
    session['state'] = state
    session['client_config'] = client_config
    return redirect(authorization_url)

@app.route('/auth/google/callback')
def google_callback():
    """Handle Google OAuth callback"""
    state = session.get('state')
    client_config = session.get('client_config')

    oauth_error = request.args.get('error')
    if oauth_error:
        return login_redirect_with_error(f'Google sign-in was cancelled or failed: {oauth_error}')

    if not state or not client_config:
        return login_redirect_with_error('Google sign-in session expired. Please try again.')

    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return login_redirect_with_error('Google OAuth is not configured on the server.')

    try:
        flow = Flow.from_client_config(
            client_config,
            scopes=SCOPES,
            state=state,
            redirect_uri=get_google_redirect_uri()
        )
        
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # Get user info from Google
        user_info_service = requests.get(
            'https://www.googleapis.com/oauth2/v1/userinfo',
            headers={'Authorization': f'Bearer {credentials.token}'},
            timeout=15
        )
        user_info_service.raise_for_status()
        user_data = user_info_service.json()
        
        email = user_data.get('email')
        name = user_data.get('name')

        if not email:
            return login_redirect_with_error('Google did not provide an email address for this account.')

        # Check if user exists, if not create new user
        user = db.session.query(User).filter_by(email=email).first()
        if not user:
            # Create new user with random password (they won't need it for Google auth)
            random_password = secrets.token_hex(16)
            user = User(
                name=name or email,
                email=email,
                password=generate_password_hash(random_password)
            )
            db.session.add(user)
            db.session.commit()
        
        # Create JWT token
        access_token = create_access_token(identity=str(user.id))

        session.pop('state', None)
        session.pop('client_config', None)

        # Redirect to dashboard with token
        return redirect(f'/dashboard?token={access_token}')

    except Exception as e:
        session.pop('state', None)
        session.pop('client_config', None)
        return login_redirect_with_error(f'Google authentication failed: {str(e)}')

@app.route('/user/personalize', methods=['POST'])
@jwt_required()
def personalize():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()

    if 'gradeClass' in data and model_has_column(User, 'grade_class'):
        user.grade_class = data['gradeClass']
    if 'subjects' in data:
        user.subjects = json.dumps(data['subjects']) if data['subjects'] else '[]'
    if 'grades' in data:
        user.current_grades = json.dumps(data['grades']) if data['grades'] else '{}'
    if 'goals' in data:
        user.goals = json.dumps(data['goals']) if data['goals'] else '{}'

    db.session.commit()

    return jsonify({'message': 'Personalization data updated successfully'}), 200

@app.route('/api/dashboard', methods=['GET'])
@jwt_required()
def get_dashboard_data():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Parse JSON fields
    subjects = json.loads(user.subjects) if user.subjects else []
    goals = json.loads(user.goals) if user.goals else {}
    grades = json.loads(user.current_grades) if user.current_grades else {}

    # Calculate average score from grades
    average_score = 0
    if grades:
        scores = [grade for grade in grades.values() if isinstance(grade, (int, float))]
        if scores:
            average_score = sum(scores) / len(scores)

    # Get target grade from goals
    target_grade = goals.get('targetGrade', 85) if goals else 85

    # Calculate actual days left from exam date
    days_left = 30  # default
    if goals and 'examDate' in goals:
        try:
            exam_date = datetime.datetime.fromisoformat(goals['examDate'])
            days_left = max(0, (exam_date - datetime.datetime.now()).days)
        except (ValueError, TypeError):
            days_left = 30

    # Get today's study time from BehaviorTracking
    today = datetime.date.today()
    today_tracking = db.session.query(BehaviorTracking).filter_by(user_id=user_id, date=today).first()
    today_study_minutes = today_tracking.study_time if today_tracking else 0

    # Get gamification stats
    gamify = db.session.query(Gamification).filter_by(user_id=user_id).first()
    if not gamify:
        gamify = Gamification(user_id=user_id, xp=1250, streak=7, level=12, badges=['First Study Session', 'Week Warrior'])
        db.session.add(gamify)
        db.session.commit()

    # Build grade and subject summaries
    numeric_grades = {}
    for subject, value in grades.items():
        try:
            numeric_grades[subject] = float(value)
        except (TypeError, ValueError):
            continue

    if not subjects and numeric_grades:
        subjects = sorted(numeric_grades.keys(), key=lambda s: numeric_grades[s], reverse=True)[:5]

    sorted_scores = sorted(numeric_grades.items(), key=lambda pair: pair[1])
    weak_topics = [subject for subject, _ in sorted_scores[:3]] if sorted_scores else subjects[:3]
    strong_topics = [subject for subject, _ in sorted_scores[-3:][::-1]] if sorted_scores else subjects[:3]

    # Load assignments from the database
    assignments_query = db.session.query(Assignment).filter_by(user_id=user_id).order_by(Assignment.deadline).all()
    assignments = []
    for a in assignments_query:
        due_date = a.deadline.date()
        days_to_due = (due_date - datetime.date.today()).days
        if a.completed:
            status = 'Completed'
        elif days_to_due < 0:
            plural = 's' if abs(days_to_due) != 1 else ''
            status = f'Overdue by {-days_to_due} day{plural}'
        elif days_to_due == 0:
            status = 'Due today'
        else:
            plural = 's' if days_to_due != 1 else ''
            status = f'Due in {days_to_due} day{plural}'

        assignments.append({
            'id': a.id,
            'title': a.title,
            'status': status,
            'due': a.deadline.strftime('%b %d'),
            'deadline': a.deadline.isoformat(),
            'linked_subject': a.subject or 'General',
            'completed': a.completed
        })

    completed_assignments = sum(1 for a in assignments if a.get('completed'))
    total_assignments = len(assignments)
    completion_rate = int((completed_assignments / total_assignments) * 100) if total_assignments else min(100, max(50, int(average_score)))

    # Generate hero data
    hero = {
        'tagline': 'Welcome back, champion!',
        'name': get_optional_user_attr(user, 'username') or user.name.split()[0],
        'days_left': days_left,
        'average_score': round(average_score, 1),
        'goal': target_grade,
        'xp': gamify.xp,
        'streak': gamify.streak,
        'completion_rate': completion_rate,
        'level': gamify.level,
        'today_study_time': today_study_minutes
    }

    # Generate productivity data from user sessions
    subject_durations = {}
    study_sessions = db.session.query(StudySession).filter_by(user_id=user_id).all()
    for session_entry in study_sessions:
        subject = session_entry.subject or 'General'
        duration_seconds = session_entry.duration or 0
        subject_durations[subject] = subject_durations.get(subject, 0) + duration_seconds

    time_per_subject = []
    for subject, total_seconds in subject_durations.items():
        time_per_subject.append({'subject': subject, 'hours': round(total_seconds / 3600, 1)})

    if not time_per_subject and subjects:
        estimated_hours = round((today_study_minutes / 60) / max(len(subjects), 1), 1)
        time_per_subject = [{'subject': subject, 'hours': estimated_hours} for subject in subjects[:4]]

    best_return_subject = None
    best_return_value = 0
    for item in time_per_subject:
        grade = numeric_grades.get(item['subject'], average_score or 75)
        hours = item['hours'] or 1
        return_value = grade / hours
        if return_value > best_return_value:
            best_return_value = return_value
            best_return_subject = item['subject']

    productivity_roi = {
        'time_per_subject': time_per_subject,
        'best_return': f'{best_return_subject or (subjects[0] if subjects else "Study") } - {round(best_return_value, 1)} points per hour',
        'inefficient_area': f'{weak_topics[0] if weak_topics else "General"} - review study approach for this topic',
        'optimization_tip': 'Target your weakest topics with active recall and written practice.'
    }

    # Generate daily recommendations, study planning, and revision items
    focus_subject = subjects[0] if subjects else 'General study'
    recommended_duration = max(90, today_study_minutes + 30)
    daily_recommendations = {
        'focus_subject': focus_subject,
        'study_duration': f'{recommended_duration // 60}h {recommended_duration % 60}m',
        'revision_topics': weak_topics if weak_topics else [focus_subject]
    }

    study_plan_items = []
    if subjects:
        plan_subjects = subjects[:3]
        for index, subject in enumerate(plan_subjects):
            study_plan_items.append({
                'time': f'{9 + index * 2}:00',
                'subject': subject,
                'task': f'Review key concepts and solve practice questions for {subject}',
                'duration': '1h 30m' if index == 0 else '1h',
                'priority': 'High' if subject in weak_topics else 'Medium',
                'revision_due': 'Today' if subject in weak_topics else 'Tomorrow'
            })
    else:
        study_plan_items.append({
            'time': '09:00',
            'subject': 'General study',
            'task': 'Build focus with a short review session',
            'duration': '1h',
            'priority': 'Medium',
            'revision_due': 'Today'
        })

    study_planning = {
        'daily_plan': study_plan_items,
        'auto_adjustment': 'Recommended plan adapts to your latest grades and study time.',
        'revision_schedule': [
            f'{weak_topics[i] if i < len(weak_topics) else focus_subject} - {(datetime.date.today() + datetime.timedelta(days=i)).strftime("%b %d")}'
            for i in range(min(len(weak_topics) or 1, 4))
        ],
        'priority_topics': weak_topics or subjects or ['Core concepts']
    }

    # Generate performance analysis data
    subject_stats = []
    for subject in subjects[:5]:
        score = numeric_grades.get(subject, average_score or 75)
        subject_stats.append({
            'name': subject,
            'score': score,
            'target': target_grade
        })

    performance_entries = db.session.query(PerformanceData).filter_by(user_id=user_id).order_by(PerformanceData.id.desc()).limit(7).all()
    trend_points = []
    if performance_entries:
        for idx, entry in enumerate(reversed(performance_entries), 1):
            entry_marks = json.loads(entry.marks or '{}')
            values = [float(v) for v in entry_marks.values() if isinstance(v, (int, float, str)) and str(v).replace('.', '', 1).isdigit()]
            entry_average = round(sum(values) / len(values), 1) if values else average_score
            trend_points.append({'label': f'Entry {idx}', 'score': entry_average})
    else:
        for i in range(7):
            trend_points.append({'label': f'Day {i+1}', 'score': min(100, max(40, round((average_score or 75) + i * 1.5)))})

    performance_analysis = {
        'subject_stats': subject_stats,
        'trend_points': trend_points
    }

    # Build knowledge mapping concepts from subjects and grades
    knowledge_mapping = {'concepts': []}
    for subject in subjects[:4]:
        score = numeric_grades.get(subject, average_score or 75)
        mastery = f'{min(100, max(20, int(score)))}%'
        knowledge_mapping['concepts'].append({'name': f'{subject} core concepts', 'mastery': mastery})
        knowledge_mapping['concepts'].append({'name': f'{subject} problem solving', 'mastery': mastery})

    if not knowledge_mapping['concepts']:
        knowledge_mapping['concepts'] = [{'name': 'Study planning', 'mastery': f'{min(100, max(20, int(average_score)))}%'}]

    # Build cognitive model from profile and performance
    profile = db.session.query(CognitiveProfile).filter_by(user_id=user_id).first()
    if not profile:
        profile = CognitiveProfile(user_id=user_id, learning_speed=1.0, memory_strength=json.dumps({'concept recall': 0.7}), forgetting_risk=0.4)
        db.session.add(profile)
        db.session.commit()

    memory_strength = json.loads(profile.memory_strength or '{}')
    recall_score = memory_strength.get('concept recall', 0.7)
    try:
        recall_score = float(recall_score)
    except (TypeError, ValueError):
        recall_score = 0.7
    cognitive_model = [
        {'model': 'Bloom\'s Taxonomy', 'status': 'Understanding → Applying', 'progress': f'{min(100, int(recall_score * 100))}%'} ,
        {'model': 'Spaced Repetition', 'status': 'Active', 'progress': 'Review schedule loaded'},
        {'model': 'Interleaving', 'status': 'Enabled', 'progress': 'Mixed practice active'}
    ]

    # Build AI tutoring prompts
    ai_tutoring = {
        'explanation': 'Ask anything about your concepts. ClutchMate uses your profile to personalize explanations.',
        'starter_prompts': [
            f'Explain {subjects[0]} in simple steps' if subjects else 'Explain a study topic simply',
            f'Why does this happen in {subjects[0]}?' if subjects else 'Why does this concept matter?',
            'Break down the hardest part of my current revision topic',
            'Give me a quick memory trick for a confusing concept'
        ]
    }

    # Add weakness intelligence data
    recent_paper_analyses = db.session.query(PaperAnalysis).filter_by(user_id=user_id).order_by(PaperAnalysis.created_at.desc()).limit(3).all()
    paper_findings = []
    for entry in recent_paper_analyses:
        paper_findings.extend(extract_paper_mistake_patterns(entry.analysis))
    paper_findings = list(dict.fromkeys(paper_findings))

    repeated_patterns = []
    if paper_findings:
        repeated_patterns.extend([f'Paper analysis insight: {pattern}' for pattern in paper_findings[:3]])

    if weak_topics:
        repeated_patterns.extend([
            f'Low score focus detected in {topic}. Review core formulas and practice application for this subject.'
            for topic in weak_topics
        ])

    if not repeated_patterns:
        repeated_patterns = [
            f'No repeated weakness patterns found yet for your selected subjects: {", ".join(subjects[:3]) or "General study"}.'
        ]

    high_risk_topics = weak_topics or subjects[:3] or ['General study']

    targeted_plan = []
    if weak_topics:
        targeted_plan = [
            f'{topic}: schedule one focused practice session and review the common mistakes in this subject.'
            for topic in weak_topics
        ]
    elif subjects:
        targeted_plan = [
            f'{subjects[0]}: begin with a quick concept review and 15 minutes of active problem solving.'
        ]
    else:
        targeted_plan = [
            'Start with a quick review of your current study topics and note the areas that feel least confident.'
        ]

    if paper_findings:
        targeted_plan.insert(0, f'Review the latest paper analysis note: {paper_findings[0]}')

    weakness_intelligence = {
        'repeated_patterns': repeated_patterns,
        'high_risk_topics': high_risk_topics,
        'targeted_plan': targeted_plan,
        'paper_analysis_insights': paper_findings,
        'paper_analysis_count': len(recent_paper_analyses)
    }

    # Load study materials from the database
    materials_query = db.session.query(StudyMaterial).filter_by(user_id=user_id).order_by(StudyMaterial.created_at.desc()).all()
    study_materials = [
        {
            'id': m.id,
            'title': m.title,
            'description': m.description,
            'subject': m.subject,
            'type': m.material_type,
            'date': m.created_at.strftime('%b %d, %Y')
        }
        for m in materials_query
    ]

    # Add gamification data
    gamification = {
        'badges': gamify.badges_list,
        'next_reward': 'Next badge: keep studying 3 more days to unlock the next milestone',
        'xp': gamify.xp,
        'level': gamify.level,
        'streak': gamify.streak
    }

    # Build smart alerts from assignments and weak topics
    smart_alerts = {'alerts': []}
    for a in assignments[:3]:
        smart_alerts['alerts'].append(f'Assignment "{a["title"]}" is {a["status"]}.')
    if weak_topics:
        smart_alerts['alerts'].append(f'Your weakest topic is {weak_topics[0]}; plan a focused study session.')

    if not smart_alerts['alerts']:
        smart_alerts['alerts'].append('Keep your study momentum going with a short review session today.')

    adaptive_testing = {
        'quiz_focus': weak_topics[0] if weak_topics else focus_subject,
        'difficulty': 'Adaptive based on your weakest scores',
        'feedback_mode': 'Detailed with concept-specific correction'
    }

    meditation_count = db.session.query(MeditationSession).filter_by(user_id=user_id).count()
    mental_health = compute_mental_health(user_id, average_score, assignments_query, today_study_minutes, grades)
    mental_health.update({
        'meditation_minutes': min(meditation_count * 10, 40),
        'recovery_tip': 'Take a short walking break after 45 minutes of focused study.',
        'focus_reset': 'Try a 25/5 Pomodoro cycle for your next session.'
    })

    system_features = {
        'profile_ready': bool(subjects and goals),
        'history_saved': bool(study_sessions or assignments or materials_query),
        'cross_device_sync': 'Enabled' if user.email else 'Available after login',
        'secure_data': 'Encrypted at rest'
    }

    integrations = {
        'available': ['Email reminders'] if user.email else [],
        'future': ['Calendar sync', 'Google Classroom integration'] if subjects else []
    }

    advanced_intelligence = {
        'exam_prediction': min(100, max(50, int(average_score + (5 if weak_topics else 8)))),
        'learning_style': 'Analytical' if any(sub.lower() in ['math', 'physics', 'computer science'] for sub in subjects) else 'Visual',
        'long_term_strategy': 'Use spaced practice and review weaker topics each day.'
    }

    multi_user = {
        'student_panel': 'Progress analytics and adaptive recommendations',
        'teacher_panel': 'Class monitoring and assignment insights',
        'parent_panel': 'Study summaries and readiness alerts'
    }

    # Add dashboard summary data
    dashboard = {
        'strong_topics': strong_topics,
        'weak_topics': weak_topics,
        'efficiency_metrics': [
            {
                'label': f'{item["subject"]} efficiency',
                'value': round((numeric_grades.get(item['subject'], average_score or 75) / max(item['hours'], 1)), 2)
            }
            for item in time_per_subject
        ] or [{'label': 'Overall efficiency', 'value': round((average_score or 75) / 2, 2)}]
    }

    return jsonify({
        'hero': hero,
        'daily_recommendations': daily_recommendations,
        'study_planning': study_planning,
        'performance_analysis': performance_analysis,
        'knowledge_mapping': knowledge_mapping,
        'cognitive_model': cognitive_model,
        'ai_tutoring': ai_tutoring,
        'weakness_intelligence': weakness_intelligence,
        'productivity_roi': productivity_roi,
        'assignments': assignments,
        'study_materials': study_materials,
        'gamification': gamification,
        'smart_alerts': smart_alerts,
        'adaptive_testing': adaptive_testing,
        'advanced_intelligence': advanced_intelligence,
        'mental_health': mental_health,
        'system_features': system_features,
        'dashboard': dashboard,
        'multi_user': multi_user,
        'integrations': integrations,
        # Keep original data for compatibility
        'name': user.name,
        'grade_class': get_optional_user_attr(user, 'grade_class'),
        'subjects': subjects,
        'goals': goals,
        'grades': grades
    }), 200

@app.route('/api/automation/daily-summaries', methods=['GET'])
def get_daily_summaries_for_automation():
    if not has_valid_automation_secret(request):
        return jsonify({'error': 'Unauthorized'}), 401

    user_id_filter = request.args.get('user_id', type=int)
    users_query = db.session.query(User).order_by(User.id.asc())
    if user_id_filter is not None:
        users_query = users_query.filter(User.id == user_id_filter)

    users = users_query.all()
    summaries = [build_daily_summary_payload(user) for user in users]

    return jsonify({
        'generated_at': datetime.datetime.utcnow().isoformat() + 'Z',
        'count': len(summaries),
        'summaries': summaries
    }), 200


@app.route('/api/wellness', methods=['GET'])
@jwt_required()
def get_wellness():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    grades = json.loads(user.current_grades) if user.current_grades else {}
    average_score = 0
    numeric_scores = [float(v) for v in grades.values() if isinstance(v, (int, float)) or (isinstance(v, str) and str(v).replace('.', '', 1).isdigit())]
    if numeric_scores:
        average_score = sum(numeric_scores) / len(numeric_scores)

    assignments_query = db.session.query(Assignment).filter_by(user_id=user_id).order_by(Assignment.deadline).all()
    today = datetime.date.today()
    today_tracking = db.session.query(BehaviorTracking).filter_by(user_id=user_id, date=today).first()
    today_study_minutes = today_tracking.study_time if today_tracking else 0

    wellness_data = compute_mental_health(user_id, average_score, assignments_query, today_study_minutes, grades)
    wellness_data['name'] = user.name
    return jsonify({'mental_health': wellness_data}), 200

@app.route('/api/wellness/mood', methods=['POST'])
@jwt_required()
def save_mood():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    mood = (data.get('mood') or '').strip().lower()
    note = (data.get('note') or '').strip()
    sleep_hours = data.get('sleep_hours')

    if mood not in ['good', 'okay', 'stressed', 'overwhelmed']:
        return jsonify({'error': 'Mood must be one of: good, okay, stressed, overwhelmed.'}), 400

    try:
        if sleep_hours is not None and sleep_hours != '':
            sleep_hours = float(sleep_hours)
        else:
            sleep_hours = None
    except (TypeError, ValueError):
        return jsonify({'error': 'Sleep hours must be a number if provided.'}), 400

    mood_entry = MoodEntry(user_id=user_id, mood=mood, note=note, sleep_hours=sleep_hours)
    db.session.add(mood_entry)
    db.session.commit()

    return jsonify({'message': 'Mood saved successfully.', 'today_mood': mood}), 201

@app.route('/api/wellness/reflection', methods=['POST'])
@jwt_required()
def save_reflection():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    stressors = (data.get('stressors') or '').strip()
    wins = (data.get('wins') or '').strip()

    if not stressors and not wins:
        return jsonify({'error': 'Please share at least one reflection note.'}), 400

    reflection_entry = ReflectionEntry(user_id=user_id, stressors=stressors, wins=wins)
    db.session.add(reflection_entry)
    db.session.commit()

    return jsonify({'message': 'Reflection saved. This helps your mental state model.'}), 201

@app.route('/auth/logout', methods=['POST'])
@jwt_required()
def logout():
    # JWT is stateless, so logout is handled client-side
    # In a production app, you might want to implement token blacklisting
    return jsonify({'message': 'Logged out successfully'}), 200

@app.route('/api/ai-tutor', methods=['POST'])
@jwt_required()
def ai_tutor():
    data = request.get_json(silent=True) or {}
    prompt = (data.get('prompt', '') or '').strip()

    if not prompt:
        return jsonify({'error': 'Prompt is required'}), 400

    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    subjects = user.subjects_list if user else []
    subject_context = f"User subjects: {', '.join(subjects)}." if subjects else "User subjects: general academic topics."

    system_prompt = (
        'You are ClutchMate, an encouraging AI tutor for students. Provide a clear, step-by-step explanation, ' 
        'use simple language, and include examples when possible. If the user question relates to a school subject, answer as a study guide.'
    )
    openai_prompt = f"{subject_context}\nQuestion: {prompt}"

    answer = get_openai_response(openai_prompt, system_prompt=system_prompt)
    if answer:
        return jsonify({'answer': answer, 'provider': 'openai'}), 200

    answer = build_local_tutor_response(prompt, subjects=subjects)
    return jsonify({'answer': answer, 'provider': 'local'}), 200

# Study Planning
@app.route('/api/study-plan/generate', methods=['POST'])
@jwt_required()
def generate_study_plan():
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    syllabus = data.get('syllabus', []) or []
    exam_date = data.get('exam_date')

    user = db.session.get(User, user_id)
    if not syllabus and user:
        syllabus = user.subjects_list or []

    if not syllabus:
        syllabus = ['Review notes', 'Practice problems', 'Self-test']

    plan = []
    try:
        days_until_exam = max(0, (datetime.datetime.fromisoformat(exam_date) - datetime.datetime.now()).days) if exam_date else 14
    except (TypeError, ValueError):
        days_until_exam = 14

    for i in range(min(days_until_exam, 30)):
        topics = random.sample(syllabus, min(3, len(syllabus))) if syllabus else ['General review']
        plan.append({
            'date': (datetime.datetime.now() + datetime.timedelta(days=i)).isoformat(),
            'topics': topics,
            'duration': '2h',
            'priority': 'High' if i < 7 else 'Medium'
        })

    study_plan = StudyPlan(user_id=user_id, plan=json.dumps(plan), syllabus=json.dumps(syllabus), exam_date=exam_date if isinstance(exam_date, str) else '')
    db.session.add(study_plan)
    db.session.commit()

    return jsonify({'plan': plan}), 200

@app.route('/api/study-plan', methods=['GET'])
@jwt_required()
def get_study_plan():
    user_id = get_jwt_identity()
    plan = db.session.query(StudyPlan).filter_by(user_id=user_id).first()
    if plan:
        return jsonify({'plan': json.loads(plan.plan)}), 200
    return jsonify({'plan': []}), 200

@app.route('/api/timetable', methods=['GET'])
@jwt_required()
def get_timetable():
    user_id = get_jwt_identity()
    entries = db.session.query(TimetableEntry).filter_by(user_id=user_id).order_by(TimetableEntry.day, TimetableEntry.start_time).all()
    return jsonify([
        {
            'id': entry.id,
            'day': entry.day,
            'start_time': entry.start_time,
            'end_time': entry.end_time,
            'title': entry.title,
            'subject': entry.subject,
            'category': entry.category,
            'notes': entry.notes
        }
        for entry in entries
    ]), 200

@app.route('/api/timetable', methods=['POST'])
@jwt_required()
def create_timetable_entry():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    day = (data.get('day') or 'Monday').strip()
    start_time = (data.get('start_time') or '08:00').strip()
    end_time = (data.get('end_time') or '09:00').strip()
    subject = (data.get('subject') or 'General').strip()
    category = (data.get('category') or 'Study').strip()
    notes = (data.get('notes') or '').strip()

    if not title:
        return jsonify({'error': 'title is required'}), 400

    entry = TimetableEntry(
        user_id=user_id,
        title=title,
        day=day,
        start_time=start_time,
        end_time=end_time,
        subject=subject,
        category=category,
        notes=notes
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({'message': 'Timetable entry created', 'id': entry.id}), 201

@app.route('/api/timetable/<int:entry_id>', methods=['PUT'])
@jwt_required()
def update_timetable_entry(entry_id):
    user_id = get_jwt_identity()
    entry = db.session.query(TimetableEntry).filter_by(id=entry_id, user_id=user_id).first()
    if not entry:
        return jsonify({'error': 'Timetable entry not found'}), 404

    data = request.get_json(silent=True) or {}
    if 'title' in data:
        entry.title = (data.get('title') or entry.title).strip()
    if 'day' in data:
        entry.day = (data.get('day') or entry.day).strip()
    if 'start_time' in data:
        entry.start_time = (data.get('start_time') or entry.start_time).strip()
    if 'end_time' in data:
        entry.end_time = (data.get('end_time') or entry.end_time).strip()
    if 'subject' in data:
        entry.subject = (data.get('subject') or entry.subject).strip()
    if 'category' in data:
        entry.category = (data.get('category') or entry.category).strip()
    if 'notes' in data:
        entry.notes = (data.get('notes') or entry.notes).strip()

    db.session.commit()
    return jsonify({'message': 'Timetable entry updated'}), 200

@app.route('/api/timetable/<int:entry_id>', methods=['DELETE'])
@jwt_required()
def delete_timetable_entry(entry_id):
    user_id = get_jwt_identity()
    entry = db.session.query(TimetableEntry).filter_by(id=entry_id, user_id=user_id).first()
    if not entry:
        return jsonify({'error': 'Timetable entry not found'}), 404

    db.session.delete(entry)
    db.session.commit()
    return jsonify({'message': 'Timetable entry deleted'}), 200

@app.route('/api/recommendations/articles', methods=['GET'])
@jwt_required()
def get_article_recommendations():
    subject = (request.args.get('subject') or '').strip()
    topic = (request.args.get('topic') or '').strip()
    lower_topic = topic.lower()
    lower_subject = subject.lower()

    if lower_subject in ('biology', 'bio', 'biology class') or 'bio' in lower_topic:
        recommendations = [
            {'title': 'The Science Behind CRISPR: Gene Editing Explained', 'url': 'https://example.com/crispr-intro'},
            {'title': 'How Ecosystems Respond to Climate Change', 'url': 'https://example.com/ecosystems-climate'},
            {'title': 'From Cells to Systems: Building a Passion for Biology', 'url': 'https://example.com/life-science-perspective'}
        ]
    elif lower_subject in ('physics',) or 'force' in lower_topic or 'energy' in lower_topic:
        recommendations = [
            {'title': 'How Quantum Physics Shapes the Modern World', 'url': 'https://example.com/quantum-world'},
            {'title': 'Renewable Energy and the Physics of Power', 'url': 'https://example.com/renewable-energy-physics'},
            {'title': 'The Physics Behind Everyday Technology', 'url': 'https://example.com/everyday-physics'}
        ]
    elif lower_subject in ('math', 'mathematics') or 'algebra' in lower_topic or 'calculus' in lower_topic:
        recommendations = [
            {'title': 'Why Math Matters: Real-World Applications of Algebra', 'url': 'https://example.com/math-in-life'},
            {'title': 'A Simple Guide to Geometry and Spatial Thinking', 'url': 'https://example.com/geometry-guide'},
            {'title': 'The Beauty of Patterns in Calculus', 'url': 'https://example.com/calculus-patterns'}
        ]
    else:
        recommendations = [
            {'title': 'Learning Beyond the Textbook: Explore More in Your Subject', 'url': 'https://example.com/learning-beyond'},
            {'title': 'How Curiosity Turns Topics into Passion Projects', 'url': 'https://example.com/curiosity-projects'},
            {'title': 'Study Smarter with Contextual Reading', 'url': 'https://example.com/contextual-reading'}
        ]

    return jsonify({'recommendations': recommendations}), 200

# Performance Analysis
@app.route('/api/performance/analyze', methods=['POST'])
@jwt_required()
def analyze_performance():
    user_id = get_jwt_identity()
    data = request.get_json() or {}
    marks = data.get('marks', {}) or {}

    weak_areas = [subject for subject, score in marks.items() if isinstance(score, (int, float)) and score < 70]
    trends = []
    for subject, score in marks.items():
        if isinstance(score, (int, float)):
            trends.append({'subject': subject, 'score': score})
        elif isinstance(score, str) and score.replace('.', '', 1).isdigit():
            trends.append({'subject': subject, 'score': float(score)})

    if not trends:
        trends = [{'subject': 'Overall', 'score': 0}]

    performance = PerformanceData(user_id=user_id, marks=json.dumps(marks), weak_areas=json.dumps(weak_areas), trends=json.dumps(trends))
    db.session.add(performance)
    db.session.commit()

    return jsonify({'weak_areas': weak_areas, 'trends': trends}), 200

# Knowledge Mapping
@app.route('/api/knowledge-map', methods=['GET'])
@jwt_required()
def get_knowledge_map():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Get user's subjects
    subjects = user.subjects_list if user.subjects_list else []
    
    # Create personalized knowledge graph
    G = nx.DiGraph()
    
    # Define knowledge structures for different subjects
    knowledge_structures = {
        'Mathematics': {
            'nodes': ['Arithmetic', 'Algebra', 'Geometry', 'Trigonometry', 'Calculus', 'Statistics', 'Linear Algebra'],
            'edges': [
                ('Arithmetic', 'Algebra'),
                ('Algebra', 'Geometry'),
                ('Algebra', 'Trigonometry'),
                ('Geometry', 'Trigonometry'),
                ('Trigonometry', 'Calculus'),
                ('Algebra', 'Calculus'),
                ('Calculus', 'Statistics'),
                ('Algebra', 'Linear Algebra'),
                ('Calculus', 'Linear Algebra')
            ]
        },
        'Physics': {
            'nodes': ['Mechanics', 'Thermodynamics', 'Electricity', 'Magnetism', 'Optics', 'Quantum Physics', 'Relativity'],
            'edges': [
                ('Mechanics', 'Thermodynamics'),
                ('Electricity', 'Magnetism'),
                ('Mechanics', 'Electricity'),
                ('Electricity', 'Optics'),
                ('Thermodynamics', 'Quantum Physics'),
                ('Optics', 'Quantum Physics'),
                ('Quantum Physics', 'Relativity')
            ]
        },
        'Chemistry': {
            'nodes': ['Basic Chemistry', 'Organic Chemistry', 'Inorganic Chemistry', 'Physical Chemistry', 'Biochemistry', 'Analytical Chemistry'],
            'edges': [
                ('Basic Chemistry', 'Organic Chemistry'),
                ('Basic Chemistry', 'Inorganic Chemistry'),
                ('Basic Chemistry', 'Physical Chemistry'),
                ('Organic Chemistry', 'Biochemistry'),
                ('Inorganic Chemistry', 'Biochemistry'),
                ('Physical Chemistry', 'Analytical Chemistry'),
                ('Organic Chemistry', 'Analytical Chemistry')
            ]
        },
        'Biology': {
            'nodes': ['Cell Biology', 'Genetics', 'Ecology', 'Evolution', 'Anatomy', 'Physiology', 'Microbiology'],
            'edges': [
                ('Cell Biology', 'Genetics'),
                ('Genetics', 'Evolution'),
                ('Cell Biology', 'Anatomy'),
                ('Anatomy', 'Physiology'),
                ('Cell Biology', 'Microbiology'),
                ('Genetics', 'Microbiology'),
                ('Evolution', 'Ecology')
            ]
        },
        'Computer Science': {
            'nodes': ['Programming Basics', 'Data Structures', 'Algorithms', 'Databases', 'Web Development', 'Machine Learning', 'Software Engineering'],
            'edges': [
                ('Programming Basics', 'Data Structures'),
                ('Data Structures', 'Algorithms'),
                ('Algorithms', 'Databases'),
                ('Programming Basics', 'Web Development'),
                ('Data Structures', 'Machine Learning'),
                ('Algorithms', 'Machine Learning'),
                ('Web Development', 'Software Engineering'),
                ('Databases', 'Software Engineering')
            ]
        },
        'English': {
            'nodes': ['Grammar', 'Vocabulary', 'Reading Comprehension', 'Writing', 'Literature Analysis', 'Creative Writing', 'Public Speaking'],
            'edges': [
                ('Grammar', 'Writing'),
                ('Vocabulary', 'Reading Comprehension'),
                ('Reading Comprehension', 'Literature Analysis'),
                ('Writing', 'Creative Writing'),
                ('Literature Analysis', 'Creative Writing'),
                ('Vocabulary', 'Public Speaking'),
                ('Creative Writing', 'Public Speaking')
            ]
        },
        'History': {
            'nodes': ['Ancient History', 'Medieval History', 'Modern History', 'World Wars', 'Civilizations', 'Political Systems', 'Economic History'],
            'edges': [
                ('Ancient History', 'Medieval History'),
                ('Medieval History', 'Modern History'),
                ('Modern History', 'World Wars'),
                ('Ancient History', 'Civilizations'),
                ('Medieval History', 'Civilizations'),
                ('Modern History', 'Political Systems'),
                ('Political Systems', 'Economic History')
            ]
        }
    }
    
    # Build graph based on user's subjects
    all_nodes = set()
    all_edges = []
    
    for subject in subjects:
        # Find matching knowledge structure (case-insensitive partial match)
        for key, structure in knowledge_structures.items():
            if key.lower() in subject.lower() or subject.lower() in key.lower():
                all_nodes.update(structure['nodes'])
                all_edges.extend(structure['edges'])
                break
    
    # If no specific subjects found, add a default structure
    if not all_nodes:
        default_subject = 'Mathematics'  # Default fallback
        structure = knowledge_structures[default_subject]
        all_nodes.update(structure['nodes'])
        all_edges.extend(structure['edges'])
    
    # Add nodes and edges to graph
    G.add_nodes_from(all_nodes)
    G.add_edges_from(all_edges)
    
    # Generate enhanced visualization
    plt.figure(figsize=(12, 8))
    plt.style.use('dark_background')
    
    # Use different layout for better visualization
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)
    
    # Draw the graph with enhanced styling
    nx.draw_networkx_nodes(G, pos, node_color='#f97316', node_size=2500, alpha=0.8)
    nx.draw_networkx_edges(G, pos, edge_color='#94a3b8', width=2, alpha=0.6, arrows=True, arrowsize=20)
    nx.draw_networkx_labels(G, pos, font_size=10, font_weight='bold', font_color='white')
    
    # Add title
    subject_list = ', '.join(subjects) if subjects else 'General Knowledge'
    plt.title(f'Knowledge Map - {subject_list}', fontsize=16, color='white', pad=20)
    
    # Remove axes
    plt.axis('off')
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor='#0f172a')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()
    
    # Store graph data in database
    graph_data = {
        'nodes': list(G.nodes()),
        'edges': list(G.edges()),
        'subjects': subjects
    }
    
    knowledge_map = db.session.query(KnowledgeMap).filter_by(user_id=user_id).first()
    if knowledge_map:
        knowledge_map.graph_data = json.dumps(graph_data)
    else:
        knowledge_map = KnowledgeMap(user_id=user_id, graph_data=json.dumps(graph_data))
        db.session.add(knowledge_map)
    
    db.session.commit()
    
    return jsonify({
        'map_image': f'data:image/png;base64,{img_base64}',
        'subjects': subjects,
        'node_count': len(G.nodes()),
        'edge_count': len(G.edges())
    }), 200

# Cognitive Modeling
@app.route('/api/cognitive/profile', methods=['GET'])
@jwt_required()
def get_cognitive_profile():
    user_id = get_jwt_identity()
    profile = db.session.query(CognitiveProfile).filter_by(user_id=user_id).first()
    if not profile:
        profile = CognitiveProfile(user_id=user_id, learning_speed=1.0, memory_strength=json.dumps({}), forgetting_risk=0.5)
        db.session.add(profile)
        db.session.commit()
    
    return jsonify({
        'learning_speed': profile.learning_speed,
        'memory_strength': json.loads(profile.memory_strength),
        'forgetting_risk': profile.forgetting_risk
    }), 200

# AI Tutoring Extended
@app.route('/api/ai-tutor/generate-questions', methods=['POST'])
@jwt_required()
def generate_practice_questions():
    data = request.get_json()
    topic = data.get('topic', '')
    questions = [f"What is the derivative of {topic}?", f"Solve for x in {topic} equation."]
    return jsonify({'questions': questions}), 200

# Daily Recommendations
@app.route('/api/recommendations/daily', methods=['GET'])
@jwt_required()
def get_daily_recommendations():
    user_id = get_jwt_identity()
    recs = {
        'study_duration': '2h 30m',
        'topics': ['Algebra', 'Physics'],
        'revision': ['Geometry']
    }
    return jsonify(recs), 200

# Behavior Tracking
@app.route('/api/behavior/track', methods=['POST'])
@jwt_required()
def track_behavior():
    user_id = get_jwt_identity()
    data = request.get_json()
    # Store tracking data
    tracking = BehaviorTracking(user_id=user_id, 
                               study_time=data.get('study_time', 0),
                               completed_tasks=data.get('completed_tasks', 0),
                               skipped_tasks=data.get('skipped_tasks', 0))
    db.session.add(tracking)
    db.session.commit()
    return jsonify({'message': 'Behavior tracked'}), 200

# Weakness Intelligence
@app.route('/api/weakness/intelligence', methods=['GET'])
@jwt_required()
def get_weakness_intelligence():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    subjects = user.subjects_list if user else []
    grades = user.grades_dict if user else {}

    numeric_grades = {}
    for subject, value in grades.items():
        try:
            numeric_grades[subject] = float(value)
        except (TypeError, ValueError):
            continue

    weaknesses = [subject for subject, score in numeric_grades.items() if score < 70]
    if not weaknesses and subjects:
        weaknesses = subjects[:2]

    if not weaknesses:
        weaknesses = ['General study']

    recommendations = [
        f'Focus on {topic} with active practice and revision.' for topic in weaknesses
    ]
    if not grades and subjects:
        recommendations = [
            f'Review the fundamentals of {subjects[0]} and build confidence with short practice sessions.'
        ]

    return jsonify({
        'weaknesses': weaknesses,
        'high_risk_topics': weaknesses,
        'recommendations': recommendations
    }), 200

# Productivity Analysis
@app.route('/api/productivity/analyze', methods=['GET'])
@jwt_required()
def analyze_productivity():
    user_id = get_jwt_identity()
    sessions = StudySession.query.filter_by(user_id=user_id).all()
    totals = {}
    total_seconds = 0
    for session_entry in sessions:
        subject = session_entry.subject or 'General'
        duration = session_entry.duration or 0
        totals[subject] = totals.get(subject, 0) + duration
        total_seconds += duration

    time_per_subject = [
        {'subject': subject, 'hours': round(seconds / 3600, 1)}
        for subject, seconds in totals.items()
    ]

    efficiency_value = round((sum(hours for _, hours in [(item['subject'], item['hours']) for item in time_per_subject]) or 1) * 10, 1)
    return jsonify({
        'time_per_subject': time_per_subject,
        'efficiency': efficiency_value,
        'total_study_hours': round(total_seconds / 3600, 1)
    }), 200

# Assignments
@app.route('/api/assignments', methods=['GET'])
@jwt_required()
def get_assignments():
    user_id = get_jwt_identity()
    assignments = db.session.query(Assignment).filter_by(user_id=user_id).order_by(Assignment.deadline).all()
    items = []
    for a in assignments:
        days_to_due = (a.deadline.date() - datetime.date.today()).days
        if a.completed:
            status = 'Completed'
        elif days_to_due < 0:
            plural = 's' if abs(days_to_due) != 1 else ''
            status = f'Overdue by {-days_to_due} day{plural}'
        elif days_to_due == 0:
            status = 'Due today'
        else:
            plural = 's' if days_to_due != 1 else ''
            status = f'Due in {days_to_due} day{plural}'

        items.append({
            'id': a.id,
            'title': a.title,
            'status': status,
            'due': a.deadline.strftime('%b %d'),
            'deadline': a.deadline.isoformat(),
            'linked_subject': a.subject or 'General',
            'completed': a.completed
        })

    return jsonify(items), 200

@app.route('/api/assignments', methods=['POST'])
@jwt_required()
def add_assignment():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}

    title = (data.get('title') or '').strip()
    deadline_value = data.get('deadline')
    subject = (data.get('subject') or 'General').strip()

    if not title:
        return jsonify({'error': 'title is required'}), 400

    if deadline_value:
        try:
            deadline = datetime.datetime.fromisoformat(deadline_value)
        except (ValueError, TypeError):
            return jsonify({'error': 'deadline must be a valid ISO datetime string'}), 400
    else:
        deadline = datetime.datetime.utcnow()

    assignment = Assignment(
        user_id=user_id,
        title=title,
        deadline=deadline,
        subject=subject
    )
    db.session.add(assignment)
    db.session.commit()

    assignment_payload = serialize_assignment_for_n8n(assignment)
    user_payload = serialize_user_for_n8n(db.session.get(User, user_id))
    send_n8n_event('assignment.created', {
        'user': user_payload,
        'assignment': assignment_payload,
        'email_templates': build_assignment_email_templates(user_payload, assignment_payload)
    })
    return jsonify({'message': 'Assignment added', 'id': assignment.id}), 201

@app.route('/api/assignments/<int:assignment_id>', methods=['PUT'])
@jwt_required()
def update_assignment(assignment_id):
    user_id = get_jwt_identity()
    assignment = db.session.query(Assignment).filter_by(id=assignment_id, user_id=user_id).first()
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    data = request.get_json(silent=True) or {}

    if 'title' in data:
        assignment.title = (data.get('title') or assignment.title).strip()
    if 'deadline' in data and data.get('deadline'):
        try:
            assignment.deadline = datetime.datetime.fromisoformat(data['deadline'])
        except (ValueError, TypeError):
            return jsonify({'error': 'deadline must be a valid ISO datetime string'}), 400
    if 'subject' in data:
        assignment.subject = (data.get('subject') or assignment.subject).strip()
    if 'completed' in data:
        completed_value = data.get('completed')
        if isinstance(completed_value, str):
            assignment.completed = completed_value.lower() in ('true', '1', 'yes')
        else:
            assignment.completed = bool(completed_value)

    db.session.commit()

    assignment_payload = serialize_assignment_for_n8n(assignment)
    user_payload = serialize_user_for_n8n(db.session.get(User, user_id))
    send_n8n_event('assignment.updated', {
        'user': user_payload,
        'assignment': assignment_payload,
        'email_templates': build_assignment_email_templates(user_payload, assignment_payload)
    })
    return jsonify({'message': 'Assignment updated successfully'}), 200

@app.route('/api/assignments/<int:assignment_id>', methods=['DELETE'])
@jwt_required()
def delete_assignment(assignment_id):
    user_id = get_jwt_identity()
    assignment = db.session.query(Assignment).filter_by(id=assignment_id, user_id=user_id).first()
    if not assignment:
        return jsonify({'error': 'Assignment not found'}), 404

    user = db.session.get(User, user_id)
    assignment_snapshot = serialize_assignment_for_n8n(assignment)

    db.session.delete(assignment)
    db.session.commit()

    user_payload = serialize_user_for_n8n(user) if user else {'id': user_id}
    send_n8n_event('assignment.deleted', {
        'user': user_payload,
        'assignment': assignment_snapshot,
        'email_templates': build_assignment_email_templates(user_payload, assignment_snapshot)
    })
    return jsonify({'message': 'Assignment deleted successfully'}), 200

@app.route('/api/community/posts', methods=['GET'])
@jwt_required()
def get_community_posts():
    user_id = get_jwt_identity()
    posts = db.session.query(CommunityPost).order_by(CommunityPost.created_at.desc()).limit(40).all()
    result = []
    for post in posts:
        author = db.session.query(User).filter_by(id=post.user_id).first()
        comments = db.session.query(CommunityComment).filter_by(post_id=post.id).order_by(CommunityComment.created_at.asc()).all()
        result.append({
            'id': post.id,
            'title': post.title,
            'content': post.content,
            'subject': post.subject,
            'likes': post.likes,
            'created_at': post.created_at.isoformat(),
            'author_name': author.name if author else 'Someone',
            'comments': [
                {
                    'id': comment.id,
                    'content': comment.content,
                    'created_at': comment.created_at.isoformat(),
                    'author_name': db.session.query(User).filter_by(id=comment.user_id).first().name if db.session.query(User).filter_by(id=comment.user_id).first() else 'Student'
                }
                for comment in comments
            ]
        })
    return jsonify(result), 200

@app.route('/api/community/posts', methods=['POST'])
@jwt_required()
def create_community_post():
    user_id = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    title = (data.get('title') or '').strip()
    content = (data.get('content') or '').strip()
    subject = (data.get('subject') or 'General').strip()

    if not title or not content:
        return jsonify({'error': 'title and content are required'}), 400

    post = CommunityPost(user_id=user_id, title=title, content=content, subject=subject)
    db.session.add(post)
    db.session.commit()
    return jsonify({'message': 'Post created', 'id': post.id}), 201

@app.route('/api/community/posts/<int:post_id>/comments', methods=['GET'])
@jwt_required()
def get_community_comments(post_id):
    post = db.session.query(CommunityPost).filter_by(id=post_id).first()
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    comments = db.session.query(CommunityComment).filter_by(post_id=post_id).order_by(CommunityComment.created_at.asc()).all()
    return jsonify([
        {
            'id': comment.id,
            'content': comment.content,
            'created_at': comment.created_at.isoformat(),
            'author_name': db.session.query(User).filter_by(id=comment.user_id).first().name if db.session.query(User).filter_by(id=comment.user_id).first() else 'Student'
        }
        for comment in comments
    ]), 200

@app.route('/api/community/posts/<int:post_id>/comments', methods=['POST'])
@jwt_required()
def add_community_comment(post_id):
    user_id = get_jwt_identity()
    post = db.session.query(CommunityPost).filter_by(id=post_id).first()
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    data = request.get_json(silent=True) or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({'error': 'content is required'}), 400

    comment = CommunityComment(post_id=post_id, user_id=user_id, content=content)
    db.session.add(comment)
    db.session.commit()
    return jsonify({'message': 'Comment added', 'id': comment.id}), 201

@app.route('/api/community/posts/<int:post_id>/like', methods=['POST'])
@jwt_required()
def like_community_post(post_id):
    user_id = get_jwt_identity()
    post = db.session.query(CommunityPost).filter_by(id=post_id).first()
    if not post:
        return jsonify({'error': 'Post not found'}), 404

    post.likes = (post.likes or 0) + 1
    db.session.commit()
    return jsonify({'message': 'Post liked', 'likes': post.likes}), 200

@app.route('/api/study-materials', methods=['GET'])
@jwt_required()
def get_study_materials():
    user_id = get_jwt_identity()
    materials = StudyMaterial.query.filter_by(user_id=user_id).order_by(StudyMaterial.created_at.desc()).all()
    results = []
    for m in materials:
        item = {
            'id': m.id,
            'title': m.title,
            'description': m.description,
            'subject': m.subject,
            'type': m.material_type,
            'date': m.created_at.strftime('%b %d, %Y')
        }
        if m.file_path:
            item['file_url'] = f"/uploads/{m.file_path}"
            item['original_filename'] = m.original_filename or m.title
        results.append(item)
    return jsonify(results), 200

@app.route('/api/paper-analyzer/analyze', methods=['POST'])
@jwt_required()
def analyze_paper():
    user_id = get_jwt_identity()

    image_bytes = None
    syllabus_text = ''
    syllabus_note = ''

    if request.content_type and request.content_type.startswith('multipart/form-data'):
        uploaded_file = request.files.get('file')
        if not uploaded_file or not uploaded_file.filename:
            return jsonify({'error': 'No file uploaded'}), 400

        filename = secure_filename(uploaded_file.filename)
        stored_name = f"{secrets.token_hex(8)}_{filename}"
        saved_path = UPLOAD_FOLDER / stored_name
        uploaded_file.save(saved_path)
        image_bytes = saved_path.read_bytes()

        syllabus_file = request.files.get('syllabus_file')
        if syllabus_file and syllabus_file.filename:
            syllabus_name = secure_filename(syllabus_file.filename)
            if syllabus_name.lower().endswith(('.txt', '.md', '.csv')):
                try:
                    syllabus_text = syllabus_file.read().decode('utf-8', errors='ignore').strip()
                    syllabus_note = syllabus_text[:1000]
                except Exception:
                    syllabus_note = f'Uploaded syllabus file: {syllabus_name} (could not parse text)'
            else:
                syllabus_note = f'Uploaded syllabus file: {syllabus_name}.'

        if not syllabus_text:
            syllabus_text = (request.form.get('syllabus_text') or '').strip()
            if syllabus_text and not syllabus_note:
                syllabus_note = syllabus_text[:1000]

    else:
        data = request.get_json(silent=True) or {}
        base64_image = data.get('image_data') or data.get('imageBase64')
        if not base64_image:
            return jsonify({'error': 'No image data provided'}), 400
        if base64_image.startswith('data:'):
            base64_image = base64_image.split(',', 1)[1]
        try:
            image_bytes = base64.b64decode(base64_image)
        except Exception:
            return jsonify({'error': 'Invalid base64 image data'}), 400

        syllabus_text = (data.get('syllabus_text') or '').strip()
        if syllabus_text:
            syllabus_note = syllabus_text[:1000]

    vision_result = analyze_image_with_google_vision(image_bytes)
    extracted_text = vision_result.get('text', '') or ''
    vision_error = vision_result.get('error')

    analysis = None
    if extracted_text.strip():
        prompt = build_paper_analysis_prompt(extracted_text, syllabus_text)
        analysis = get_openai_response(prompt, system_prompt='You are a helpful academic tutor. Identify mistakes and suggest corrections from the scanned paper text.', max_tokens=700, temperature=0.4)

    if not analysis:
        if vision_error and not extracted_text.strip():
            analysis = f'Paper OCR failed. {vision_error}'
        else:
            analysis = fallback_paper_analysis(extracted_text)

    paper_entry = PaperAnalysis(
        user_id=user_id,
        extracted_text=extracted_text,
        analysis=analysis,
        syllabus_text=syllabus_text,
        source='google_vision'
    )
    db.session.add(paper_entry)
    db.session.commit()

    result = {
        'extracted_text': extracted_text,
        'analysis': analysis,
        'source': 'google_vision',
        'vision_error': vision_error,
        'syllabus_note': syllabus_note
    }

    return jsonify(result), 200

@app.route('/api/study-materials', methods=['POST'])
@jwt_required()
def add_study_material():
    user_id = get_jwt_identity()
    title = ''
    description = ''
    subject = 'General'
    material_type = 'notes'
    saved_filename = None
    original_filename = None

    if request.content_type and request.content_type.startswith('multipart/form-data'):
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        subject = request.form.get('subject', 'General').strip()
        material_type = request.form.get('type', 'notes').strip()
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename:
            original_filename = uploaded_file.filename
            filename = secure_filename(uploaded_file.filename)
            unique_name = f"{secrets.token_hex(8)}_{filename}"
            saved_path = UPLOAD_FOLDER / unique_name
            uploaded_file.save(saved_path)
            saved_filename = unique_name
    else:
        data = request.get_json(silent=True) or {}
        title = data.get('title', '').strip()
        description = data.get('description', '').strip()
        subject = data.get('subject', 'General').strip()
        material_type = data.get('type', 'notes').strip()

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    material = StudyMaterial(
        user_id=user_id,
        title=title,
        description=description,
        subject=subject,
        material_type=material_type,
        file_path=saved_filename,
        original_filename=original_filename
    )
    db.session.add(material)
    db.session.commit()
    return jsonify({'message': 'Study material added', 'id': material.id}), 201

@app.route('/api/study-materials/<int:material_id>', methods=['DELETE'])
@jwt_required()
def delete_study_material(material_id):
    user_id = get_jwt_identity()
    material = StudyMaterial.query.filter_by(id=material_id, user_id=user_id).first()
    if not material:
        return jsonify({'error': 'Study material not found'}), 404

    if material.file_path:
        file_path = UPLOAD_FOLDER / material.file_path
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

    db.session.delete(material)
    db.session.commit()
    return jsonify({'message': 'Study material deleted'}), 200

@app.route('/uploads/<path:filename>')
def serve_uploaded_file(filename):
    return send_from_directory(str(UPLOAD_FOLDER), filename)

# Gamification
@app.route('/api/gamification/stats', methods=['GET'])
@jwt_required()
def get_gamification_stats():
    user_id = get_jwt_identity()
    gamify = Gamification.query.filter_by(user_id=user_id).first()
    if not gamify:
        gamify = Gamification(user_id=user_id, xp=1250, streak=7, level=12, badges=['First Study Session', 'Week Warrior'])
        db.session.add(gamify)
        db.session.commit()
    return jsonify({
        'xp': gamify.xp, 
        'streak': gamify.streak, 
        'level': gamify.level, 
        'badges': gamify.badges_list
    }), 200

# Meditation
@app.route('/api/meditation/sessions', methods=['GET'])
@jwt_required()
def get_meditation_sessions():
    sessions = [
        {'title': 'Deep Breathing', 'duration': '10 min'}, 
        {'title': 'Mindfulness', 'duration': '15 min'},
        {'title': 'Stress Relief', 'duration': '20 min'}
    ]
    return jsonify(sessions), 200

@app.route('/api/meditation/complete', methods=['POST'])
@jwt_required()
def complete_meditation():
    user_id = get_jwt_identity()
    data = request.get_json()
    session = MeditationSession(user_id=user_id, title=data['title'], duration=data['duration'])
    db.session.add(session)
    db.session.commit()
    return jsonify({'message': 'Meditation session completed'}), 200

# Study Session Management
@app.route('/api/study/start', methods=['POST'])
@jwt_required()
def start_study_session():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    subject = data.get('subject')
    topic = data.get('topic')
    
    if not subject:
        return jsonify({'error': 'Subject is required'}), 400
    
    # Create new study session
    session = StudySession(user_id=user_id, subject=subject, topic=topic)
    db.session.add(session)
    db.session.commit()
    
    return jsonify({
        'message': 'Study session started',
        'session_id': session.id,
        'start_time': session.start_time.isoformat()
    }), 201

@app.route('/api/study/stop', methods=['POST'])
@jwt_required()
def stop_study_session():
    user_id = get_jwt_identity()
    data = request.get_json()
    
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'Session ID is required'}), 400
    
    session = StudySession.query.filter_by(id=session_id, user_id=user_id).first()
    if not session:
        return jsonify({'error': 'Study session not found'}), 404
    
    if session.end_time:
        return jsonify({'error': 'Session already ended'}), 400
    
    # End the session
    session.end_time = datetime.datetime.utcnow()
    session.duration = int((session.end_time - session.start_time).total_seconds())
    db.session.commit()
    
    # Update daily total in BehaviorTracking
    today = datetime.date.today()
    tracking = db.session.query(BehaviorTracking).filter_by(user_id=user_id, date=today).first()
    if not tracking:
        tracking = BehaviorTracking(user_id=user_id, study_time=0)
        db.session.add(tracking)
    
    tracking.study_time += session.duration // 60  # Convert to minutes
    db.session.commit()
    
    return jsonify({
        'message': 'Study session ended',
        'duration': session.duration,
        'today_total_minutes': tracking.study_time
    }), 200

@app.route('/api/study/today', methods=['GET'])
@jwt_required()
def get_today_study_time():
    user_id = get_jwt_identity()
    today = datetime.date.today()
    
    tracking = db.session.query(BehaviorTracking).filter_by(user_id=user_id, date=today).first()
    total_minutes = tracking.study_time if tracking else 0
    
    return jsonify({
        'today_study_minutes': total_minutes,
        'today_study_hours': total_minutes // 60,
        'today_study_remaining_minutes': total_minutes % 60
    }), 200

# Profile Management
@app.route('/api/profile/update', methods=['POST'])
@jwt_required()
def update_profile():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json()

    # Update username if provided
    if 'username' in data and model_has_column(User, 'username'):
        new_username = data['username'].strip()
        if new_username:
            # Check if username is taken by another user
            existing = User.query.filter_by(username=new_username).first()
            if existing and existing.id != user.id:
                return jsonify({'error': 'Username already taken'}), 409
            user.username = new_username

    # Update other personalization fields
    if 'gradeClass' in data and model_has_column(User, 'grade_class'):
        user.grade_class = data['gradeClass']
    if 'subjects' in data:
        user.subjects = json.dumps(data['subjects']) if data['subjects'] else '[]'
    if 'grades' in data:
        user.current_grades = json.dumps(data['grades']) if data['grades'] else '{}'
    if 'goals' in data:
        user.goals = json.dumps(data['goals']) if data['goals'] else '{}'

    db.session.commit()

    return jsonify({'message': 'Profile updated successfully'}), 200

@app.route('/api/profile', methods=['GET'])
@jwt_required()
def get_profile():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'name': user.name,
        'username': get_optional_user_attr(user, 'username'),
        'email': user.email,
        'grade_class': get_optional_user_attr(user, 'grade_class'),
        'subjects': json.loads(user.subjects) if user.subjects else [],
        'grades': json.loads(user.current_grades) if user.current_grades else {},
        'goals': json.loads(user.goals) if user.goals else {}
    }), 200

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        ensure_user_columns()
        ensure_study_material_columns()
        ensure_assignment_columns()
        ensure_paper_analysis_columns()
    app.run(debug=True, port=5000)
