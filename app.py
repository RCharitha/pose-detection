from flask import Flask, render_template, request, url_for, redirect, flash, session
import sqlite3
import mediapipe as mp
import numpy as np
import time
import threading
from werkzeug.security import generate_password_hash

from datetime import datetime
from utils.exercise_logic import get_exercise_function, ExerciseState
import secrets
from flask import jsonify  
import cv2
from flask import Response

mp_pose=mp.solutions.pose
mp_draw=mp.solutions.drawing_utils

count=0
direction=None
feedback="start position"

app = Flask(__name__)
app.secret_key = secrets.token_hex(32) # Required for flash messages and session

# Dictionary to store exercise states for each session
exercise_states = {}
exercise_states_lock = threading.Lock()

# Helper to connect to the database
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

# Home redirects to login
@app.route("/")
def home():
    return render_template('home.html')

# Registration route
# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        number = request.form['number'].strip()
        password = request.form['password']
        weight = request.form.get('weight')

        if not username or not number or not password:
            flash('All fields except weight are required.', 'error')
            return redirect(url_for('register'))

        weight = float(weight) if weight else None
        hashed_password = generate_password_hash(password)

        con = get_db_connection()
        cursor = con.cursor()
        try:
            cursor.execute('INSERT INTO users (username, number, password, weight) VALUES (?, ?, ?, ?)',
                           (username, number, hashed_password, weight))
            con.commit()
            flash('Registered successfully! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username already exists.', 'error')
        finally:
            con.close()
    return render_template('register.html')


# Login route
from werkzeug.security import check_password_hash

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        con = get_db_connection()
        user = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        con.close()

        if user and check_password_hash(user['password'], password):
            session['user'] = user['username']
            session['user_id'] = user['id']   # store ID too (useful for workouts, etc.)
            session['session_id'] = secrets.token_hex(16)  # Unique session ID
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


# Dashboard route
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        flash('Please login first.', 'error')
        return redirect(url_for('login'))
    return render_template('dashboard.html', user=session['user'])

@app.route('/exercise/<exercise>')
def exercise(exercise):
    # Initialize exercise state for this session
    session_id = session.get('session_id')
    if session_id:
        with exercise_states_lock:
            exercise_states[session_id] = ExerciseState()
            exercise_states[session_id].start_time = time.time()
    
    return render_template('exercise.html', exercise=exercise, session_id=session.get('session_id'))

@app.route('/video_feed/<exercise>/<session_id>')
def video_feed(exercise, session_id):
    logic_function = get_exercise_function(exercise)
    if not logic_function:
        return "Exercise not found", 404
    
    def generate():
        if not session_id or session_id not in exercise_states:
            # Return error frame if no session
            error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(error_frame, "Session Error", (150, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', error_frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            return
        
        # Get state for this session
        with exercise_states_lock:
            if session_id not in exercise_states:
                exercise_states[session_id] = ExerciseState()
                exercise_states[session_id].start_time = time.time()
            
            state = exercise_states[session_id]
        
        # Try different camera indices
        cap = None
        for camera_index in [0, 1, 2]:
            cap = cv2.VideoCapture(camera_index)
            if cap.isOpened():
                print(f"✅ Camera {camera_index} opened successfully")
                break
            if cap:
                cap.release()
        
        if not cap or not cap.isOpened():
            print("❌ No camera found")
            # Return a static error image
            error_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(error_frame, "Camera Not Available", (150, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(error_frame, "Please check camera connection", (100, 280), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            ret, buffer = cv2.imencode('.jpg', error_frame)
            if ret:
                frame_bytes = buffer.tobytes()
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            return

        pose = mp_pose.Pose()
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("❌ Failed to grab frame")
                    break

                # Process frame
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(frame_rgb)

                if results.pose_landmarks:
                    try:
                        # Update the state with exercise logic
                        with exercise_states_lock:
                            state = logic_function(results.pose_landmarks.landmark, state)
                            exercise_states[session_id] = state
                            
                        mp_draw.draw_landmarks(
                            frame,
                            results.pose_landmarks,
                            mp_pose.POSE_CONNECTIONS,
                            mp_draw.DrawingSpec(color=(245,117,66), thickness=2, circle_radius=2),
                            mp_draw.DrawingSpec(color=(245,66,230), thickness=2, circle_radius=2)
                        )
                    except Exception as e:
                        print(f"❌ Error in exercise logic: {e}")
                        state.feedback = f"Error: {str(e)}"
                        state.feedback_class = "error"

                # Add overlay
                cv2.putText(frame, f"Reps: {state.reps}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                cv2.putText(frame, f"Time: {int(state.current_time)}s", (10, 70),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
                # Feedback color
                if state.feedback_class == "correct":
                    color = (0, 255, 0)
                elif state.feedback_class == "warning":
                    color = (0, 165, 255)
                elif state.feedback_class == "error":
                    color = (0, 0, 255)
                else:
                    color = (255, 255, 255)
                
                cv2.putText(frame, state.feedback, (10, 110),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                # Encode frame
                ret, buffer = cv2.imencode('.jpg', frame)
                if ret:
                    frame_bytes = buffer.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                else:
                    print("❌ Failed to encode frame")

        except Exception as e:
            print(f"❌ Error in video generation: {e}")
            
        finally:
            if cap:
                cap.release()
            pose.close()

    return Response(generate(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/get_stats')
def get_stats():
    session_id = session.get('session_id')
    if not session_id or session_id not in exercise_states:
        return jsonify({
            "reps": 0,
            "time": 0,
            "feedback": "Start position",
            "feedback_class": "neutral"
        })
    
    with exercise_states_lock:
        state = exercise_states[session_id]
    
    return jsonify({
        "reps": state.reps,
        "time": state.current_time,
        "feedback": state.feedback,
        "feedback_class": state.feedback_class
    })

@app.route('/complete_workout/<exercise>')
def complete_workout(exercise):
    if 'user' not in session:
        return redirect(url_for('login'))

    session_id = session.get('session_id')
    state = ExerciseState()
    
    if session_id and session_id in exercise_states:
        with exercise_states_lock:
            state = exercise_states[session_id]
            # Remove the state from memory
            del exercise_states[session_id]

    # Build stats dictionary
    stats = {
        "reps": state.reps,
        "time_minutes": int(state.current_time) // 60,
        "time_seconds": int(state.current_time) % 60,
        "feedback": state.feedback
    }
    
    return render_template("complete_workout.html", exercise=exercise, stats=stats)

@app.route('/logout')
def logout():
    session_id = session.get('session_id')
    if session_id and session_id in exercise_states:
        with exercise_states_lock:
            del exercise_states[session_id]
    
    session.pop('user', None)
    session.pop('session_id', None)
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)