import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.graph_objects as go
from dataclasses import dataclass
from typing import List, Optional
import time
import logging
from streamlit_autorefresh import st_autorefresh

# Configure logging
logging.basicConfig(level=logging.INFO)

@dataclass
class Question:
    id: int
    question_easy: str
    question_hard: str
    options: List[str]
    correct_answer: str
    explanation: str
    category: str
    image_url_easy: Optional[str] = None
    image_url_hard: Optional[str] = None
    spectrum_type: Optional[str] = None

class DatabaseManager:
    def __init__(self, db_name='quiz_results.db'):
        self.db_name = db_name
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_database(self):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_points INTEGER DEFAULT 0,
                    quiz_attempts INTEGER DEFAULT 0
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    question_id INTEGER,
                    user_answer TEXT,
                    is_correct BOOLEAN,
                    time_taken FLOAT,
                    timestamp TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id),
                    UNIQUE (user_id, question_id)
                )
            ''')

def create_question_bank() -> List[Question]:
    return [
        Question(
            id=1,
            question_easy="Identify the molecule with one halide from the easy spectrum shown.",
            question_hard="In the hard spectrum image, determine the presence and type of halide(s) in the molecule.",
            options=[
                "There is no chlorine or bromine atom in the measured molecule",
                "There is one chlorine atom in the measured molecule",
                "There is one bromine atom in the measured molecule",
                "There is one chlorine and one bromine atom in the measured molecule"
            ],
            correct_answer="There is one chlorine and one bromine atom in the measured molecule",
            explanation="The isotope pattern reveals the presence of both chlorine and bromine, with characteristic ratios.",
            category="Mass Spectrometry",
            image_url_easy="test_img.png",
            image_url_hard="test_img.png",
            spectrum_type="MS"
        ),
        # Add more questions as needed
    ]

class QuizApp:
    def __init__(self):
        self.db = DatabaseManager()
        self.questions = create_question_bank()
        self.init_session_state()
        self.setup_page()

    def init_session_state(self):
        # Initialize session state variables with defaults
        defaults = {
            "current_question": 0,
            "user_id": None,
            "quiz_mode": "Hard",
            "quiz_started": False,
            "start_time": None,
            "leaderboard_needs_update": False,
            "total_score": 0,
            "total_questions": len(self.questions)
        }
        
        for key, value in defaults.items():
            if key not in st.session_state:
                st.session_state[key] = value

    def setup_page(self):
        st.set_page_config(
            page_title="Quiz App", 
            page_icon="🧪", 
            layout="wide"
        )
        # Custom CSS for better styling
        st.markdown("""
        <style>
        .main {
            background-color: #f0f2f6;
        }
        .stButton>button {
            background-color: #4CAF50;
            color: white;
            transition: all 0.3s ease;
        }
        .stButton>button:hover {
            background-color: #45a049;
            transform: scale(1.05);
        }
        h1, h2, h3, h4 {
            font-size: 1.5em !important;
        }
        </style>
        """, unsafe_allow_html=True)

    def run(self):
        # Enhanced navigation with more descriptive sidebar
        st.sidebar.title("🔬 Quiz Navigation")
        page = st.sidebar.radio(
            "Navigate", 
            ["Quiz", "Leaderboard"], 
            index=0
        )

        # Route to appropriate page
        if page == "Quiz":
            self.show_quiz_page()
        elif page == "Leaderboard":
            self.show_leaderboard()

    def show_quiz_page(self):
        if not st.session_state.quiz_started:
            st.header("🧪 Welcome to the Quiz")
            with st.form(key='quiz_form'):
                new_name = st.text_input("Enter Your Name", help="Choose a unique name for the leaderboard", max_chars=20)
                # Mode selection with explanatory text
                st.session_state.quiz_mode = st.radio(
                    "Select Quiz Mode:",
                    ["Easy", "Hard"],
                    format_func=lambda x: f"{x} Mode - {'For Children' if x == 'Easy' else 'For Adults'}",
                    index=["Easy", "Hard"].index(st.session_state.quiz_mode),
                    key="quiz_mode_radio"
                )
                # Submit button for the form
                submitted = st.form_submit_button("Start Quiz")
                if submitted:
                    if len(new_name.strip()) < 3:
                        st.error("Name must be at least 3 characters long.")
                    else:
                        try:
                            if self.register_user(new_name.strip()):
                                st.success("Registration successful! Let's begin the quiz.")
                                st.session_state.user_id = self.get_user_id(new_name.strip())
                                st.session_state.quiz_started = True
                                st.session_state.start_time = time.time()
                                st.session_state.current_question = 0
                                st.session_state.total_score = 0
                                st.rerun()
                            else:
                                st.error("This name is already taken. Please choose another.")
                        except Exception as e:
                            st.error(f"Registration failed: {str(e)}")
        else:
            self.run_quiz()

    def run_quiz(self):
        if st.session_state.current_question >= len(self.questions):
            # Quiz completion screen
            st.balloons()
            st.success(f"🎉 Quiz completed! Your final score: {st.session_state.total_score} points")
            st.session_state.leaderboard_needs_update = True
            
            if st.button("Start a New Quiz"):
                self.reset_quiz()
            return

        question = self.questions[st.session_state.current_question]
        self.display_question(question)

    def display_question(self, question: Question):
        st.markdown(f"**Question {st.session_state.current_question + 1}/{st.session_state.total_questions}**")
        st.markdown(f"**Current Score:** {st.session_state.total_score} points")
        st.markdown("---")
        # Increase the text size using markdown headings
        st.markdown(
            f"#### {question.question_easy if st.session_state.quiz_mode == 'Easy' else question.question_hard}"
        )

        image_url = question.image_url_easy if st.session_state.quiz_mode == "Easy" else question.image_url_hard
        if image_url:
            # Display the image with a smaller width
            st.image(image_url, width=300, caption=f"{st.session_state.quiz_mode} Mode Spectrum")

        user_answer = st.radio("Select your answer:", question.options)

        if st.button("Submit Answer"):
            is_correct = user_answer == question.correct_answer
            time_taken = time.time() - st.session_state.start_time
            
            if is_correct:
                st.success("🎉 Correct! Great job!")
                st.session_state.total_score += 1
            else:
                st.error(f"❌ Incorrect. The correct answer was: {question.correct_answer}")
            
            st.info(f"**Explanation:** {question.explanation}")
            
            self.save_quiz_result(question.id, user_answer, is_correct, time_taken)
            st.session_state.current_question += 1
            st.session_state.start_time = time.time()
            st.rerun()

    def save_quiz_result(self, question_id: int, user_answer: str, is_correct: bool, time_taken: float):
        """
        Save the quiz result to the database
        """
        if not st.session_state.user_id:
            st.error("User not registered. Cannot save quiz result.")
            return

        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                
                # Insert quiz result
                c.execute('''
                    INSERT INTO quiz_results 
                    (user_id, question_id, user_answer, is_correct, time_taken, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    st.session_state.user_id, 
                    question_id, 
                    user_answer, 
                    is_correct, 
                    time_taken, 
                    datetime.now()
                ))
                
                # Update user points and attempts
                points = 1 if is_correct else 0
                c.execute('''
                    UPDATE users
                    SET total_points = total_points + ?,
                        quiz_attempts = quiz_attempts + 1
                    WHERE id = ?
                ''', (points, st.session_state.user_id))
                
                conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Database error when saving quiz result: {e}")
            st.error("An error occurred while saving your quiz result.")

    def register_user(self, name: str) -> bool:
        """
        Register a new user in the database
        """
        if not name:
            return False

        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                # Use INSERT OR IGNORE to prevent duplicate entries
                c.execute('INSERT OR IGNORE INTO users (name) VALUES (?)', (name,))
                
                # Check if a row was actually inserted
                if c.rowcount > 0:
                    conn.commit()
                    return True
                else:
                    # Name already exists
                    return False
        except sqlite3.IntegrityError:
            logging.error(f"Failed to register user: {name}")
            return False

    def get_user_id(self, name: str) -> Optional[int]:
        """
        Retrieve the user ID for a given name
        """
        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                c.execute('SELECT id FROM users WHERE name = ?', (name,))
                result = c.fetchone()
                return result[0] if result else None
        except sqlite3.Error as e:
            logging.error(f"Error retrieving user ID: {e}")
            return None

    def reset_quiz(self):
        """
        Reset the quiz state to its initial configuration
        """
        # Reset all session state variables
        st.session_state.quiz_started = False
        st.session_state.user_id = None
        st.session_state.current_question = 0
        st.session_state.start_time = None
        st.session_state.leaderboard_needs_update = False
        st.session_state.total_score = 0

    def show_leaderboard(self):
        """
        Display the leaderboard with top performers
        """
        st.title("🏆 Leaderboard")

        # Add an auto-refresh every 5 seconds
        count = st_autorefresh(interval=5000, limit=None, key="leaderboard_autorefresh")

        try:
            with self.db.get_connection() as conn:
                # Fetch top 10 users ordered by total points
                df = pd.read_sql_query('''
                    SELECT name, total_points, quiz_attempts
                    FROM users
                    ORDER BY total_points DESC
                    LIMIT 10
                ''', conn)
                
                if df.empty:
                    st.info("No data available yet. Start playing to appear on the leaderboard!")
                else:
                    # Rename columns for clarity
                    df.columns = ['Player', 'Total Points', 'Quiz Attempts']
                    
                    # Set index starting from 1
                    df.index += 1
                    
                    # Display leaderboard with styling
                    st.table(df)
                    
                    # Optional: Visualize top performers
                    fig = go.Figure(data=[go.Bar(
                        x=df['Player'], 
                        y=df['Total Points'], 
                        text=df['Total Points'],
                        textposition='auto',
                    )])
                    fig.update_layout(
                        title='Top Performers',
                        xaxis_title='Players',
                        yaxis_title='Total Points'
                    )
                    st.plotly_chart(fig)
        
        except sqlite3.Error as e:
            logging.error(f"Error fetching leaderboard: {e}")
            st.error("Unable to retrieve leaderboard data.")

def main():
    quiz_app = QuizApp()
    quiz_app.run()

if __name__ == "__main__":
    main()
