from flask import Flask, render_template, request, redirect, url_for, flash, \
    session
from flask_login import LoginManager, UserMixin, login_user, login_required, \
    logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import sqlite3
import uuid

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'Invites')  # Use environment variable for security

# Configuration for file uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Database path for Render's persistent disk
DB_FILE = os.path.join('/data', 'invites.db')

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id):
        self.id = id
        self.username = 'admin'
        self.password = generate_password_hash(
            'admin123', method='pbkdf2:sha256'
        )

@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS invites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            uuid TEXT NOT NULL UNIQUE,
            message TEXT,
            image_path TEXT,
            event_date TEXT,
            event_time TEXT,
            location TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invite_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            number_of_attendees INTEGER NOT NULL,
            FOREIGN KEY(invite_id) REFERENCES invites(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == 'admin' and check_password_hash(
            User(1).password, password
        ):
            user = User(1)
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid credentials')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/admin_dashboard')
@login_required
def admin_dashboard():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        SELECT responses.name, responses.number_of_attendees,
               invites.event_date, invites.event_time, invites.location
        FROM responses
        JOIN invites ON responses.invite_id = invites.id
    ''')
    attendees = c.fetchall()
    conn.close()
    return render_template('admin_dashboard.html', attendees=attendees)

@app.route('/create_invite', methods=['GET', 'POST'])
@login_required
def create_invite():
    if request.method == 'POST':
        message = request.form['message']
        event_date = request.form['event_date']
        event_time_input = request.form['event_time']
        location = request.form['location']
        unique_id = str(uuid.uuid4())

        # Parse the time input from Flatpickr
        try:
            event_time_parsed = datetime.strptime(
                event_time_input, '%I:%M %p'
            )
            event_time = event_time_parsed.strftime('%H:%M')
        except ValueError:
            flash('Invalid time format.')
            return redirect(url_for('create_invite'))

        # Handle image upload
        image = request.files['image']
        if image and allowed_file(image.filename):
            image_filename = unique_id + '_' + secure_filename(
                image.filename
            )
            image_path = os.path.join(
                app.config['UPLOAD_FOLDER'], image_filename
            )
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            image.save(image_path)
        else:
            image_path = ''

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute(
            '''
            INSERT INTO invites (
                uuid, message, image_path, event_date, event_time, location
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (unique_id, message, image_path, event_date, event_time, location)
        )
        conn.commit()
        conn.close()
        invite_link = request.url_root + 'invite/' + unique_id
        return render_template(
            'invite_created.html', invite_link=invite_link
        )
    return render_template('create_invite.html')

@app.route('/invite/<invite_id>', methods=['GET', 'POST'])
def invite(invite_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        '''
        SELECT id, message, image_path, event_date, event_time, location
        FROM invites WHERE uuid = ?
        ''',
        (invite_id,)
    )
    result = c.fetchone()
    conn.close()
    if result:
        (
            invite_db_id, message, image_path, event_date,
            event_time, location
        ) = result

        # Convert event_time to 12-hour format with AM/PM
        event_time_parsed = datetime.strptime(event_time, '%H:%M')
        event_time_formatted = event_time_parsed.strftime('%I:%M %p')

        if request.method == 'POST':
            name = request.form['name']
            number_of_attendees = request.form['number_of_attendees']
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                '''
                INSERT INTO responses (
                    invite_id, name, number_of_attendees
                )
                VALUES (?, ?, ?)
                ''',
                (invite_db_id, name, number_of_attendees)
            )
            conn.commit()
            conn.close()
            return render_template('response.html', name=name)
        return render_template(
            'invitee_page.html',
            message=message,
            image_path=image_path,
            event_date=event_date,
            event_time=event_time_formatted,
            location=location
        )
    else:
        return 'Invalid invite link.'

if __name__ == '__main__':
    app.run(debug=True)
