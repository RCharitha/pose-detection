import sqlite3
from werkzeug.security import generate_password_hash

def init_db():
    try:
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")

        # Create users table with improved schema
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                number TEXT NOT NULL,
                password TEXT NOT NULL,
                weight REAL,  
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create workouts table (for exercise tracking)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                exercise_type TEXT NOT NULL,
                duration_seconds INTEGER,
                reps_completed INTEGER,
                calories_burned REAL,
                performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')

        
        conn.commit()
        print("✅ Database initialized successfully with tables: users, workouts")

    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    init_db()