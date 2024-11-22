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

import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)

@dataclass
class Question:
    id: int
    question_easy: str
    question_hard: str
    options: List[str]
    correct_answer: str
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
            # Create users table
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_points INTEGER DEFAULT 0,
                    quiz_attempts INTEGER DEFAULT 0
                )
            ''')
            # Create quiz_results table
            c.execute('''
                CREATE TABLE IF NOT EXISTS quiz_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    question_id INTEGER,
                    user_answer TEXT,
                    is_correct BOOLEAN,
                    time_taken FLOAT,
                    timestamp TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            # Create batch_state table
            c.execute('''
                CREATE TABLE IF NOT EXISTS batch_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    current_batch INTEGER DEFAULT 1
                )
            ''')
            # Create quiz_sessions table
            c.execute('''
                CREATE TABLE IF NOT EXISTS quiz_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    total_score INTEGER,
                    total_time FLOAT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            # Initialize batch_state if not exists
            c.execute('INSERT OR IGNORE INTO batch_state (id, current_batch) VALUES (1, 1)')
            conn.commit()

    def get_current_batch(self):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT current_batch FROM batch_state WHERE id = 1')
            result = c.fetchone()
            return result[0] if result else 1

    def update_current_batch(self, next_batch):
        with self.get_connection() as conn:
            c = conn.cursor()
            c.execute('UPDATE batch_state SET current_batch = ? WHERE id = 1', (next_batch,))
            conn.commit()

def create_question_bank() -> List[Question]:
    questions = []
    question_id = 1  # Start with ID 1 and increment for each question

    # Get the list of JSON files and PNG files
    json_files = sorted(Path('json_questions').glob("ms_*.json"))  # Adjust path as needed
    easy_images = sorted(Path('easy').glob("easy_MS*.png"))  # Adjust path as needed
    hard_images = sorted(Path('hard').glob("hard_MS*.png"))  # Adjust path as needed
    # Ensure we have the same number of JSON files and image files
    if len(json_files) != len(easy_images) or len(json_files) != len(hard_images):
        raise ValueError("Mismatch between the number of JSON files and image files. Please ensure they match.")

    for json_file, easy_image, hard_image in zip(json_files, easy_images, hard_images):
        with open(json_file, 'r') as file:
            data = json.load(file)
            example = data['examples'][0]
            # Keep only the last two sentences
            example['input'] = '.'.join(example['input'].split('.')[-2:])

            # Extract question and options from the JSON
            question_easy = example['input'].format(type1="easy spectrum", entry1="image")
            question_hard = example['input'].format(type1="hard spectrum", entry1="image")
            options = list(example['target_scores'].keys())
            correct_answer = next(
                answer for answer, score in example['target_scores'].items() if score == 1
            )

            # Map the images dynamically
            image_url_easy = str(easy_image)
            image_url_hard = str(hard_image)

            # Add the question to the list
            questions.append(Question(
                id=question_id,
                question_easy=question_easy,
                question_hard=question_hard,
                options=options,
                correct_answer=correct_answer,
                category="Mass Spectrometry",
                image_url_easy=image_url_easy,
                image_url_hard=image_url_hard,
                spectrum_type="MS"
            ))
            question_id += 1

    return questions


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
            "quiz_mode": "Einfacher",
            "quiz_started": False,
            "start_time": None,
            "leaderboard_needs_update": False,
            "total_score": 0,
            "question_answered": False,  # Initialize question_answered
            "selected_questions": [],  # Store selected questions
            "questions_per_batch": 5,  # Number of questions per batch
            "current_batch": 1,  # Keep track of current batch
            "quiz_start_time": None,
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
        # Custom CSS for styling
        st.markdown("""
        <style>
        /* Adjust the sidebar width */
        [data-testid="stSidebar"] {
            width: 15rem; /* Adjust the sidebar width here */
        }
        [data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
            width: 15rem; /* Ensure the expanded sidebar has the same width */
        }
        [data-testid="stSidebar"][aria-expanded="false"] {
            width: 0; /* When collapsed, hide the sidebar */
        }
        /* General styling for the page background and buttons */
        .main {
            background-color: #f0f2f6;
        }
        .stButton>button {
            background-color: #7d10d2;
            color: white;
            transition: all 0.1s ease;
            font-size: 1.05em; /* Adjust button text size here */
            padding: 0.2em 0.4em; /* Adjust button padding here */
            /* Allow the button to adjust to text size */
            width: auto;
            height: auto;
        }
        .stButton>button:hover {
            background-color: #45a049;
            transform: scale(1.05);
        }
        /* Adjust heading sizes here */
        h1, h2, h3, h4, h5, h6 {
            font-size: 1.6em !important;
        }
        /* Adjust general text sizes here */
        p, div, label, input, textarea, select, button {
            font-size: 1.01em !important;
        }
        /* Custom CSS for radio buttons */
        .stRadio div[role="radiogroup"] {
            gap: 8px; /* Adjust space between options */
        }
        .stRadio label {
            display: flex; /* Use flexbox for alignment */
            align-items: center; /* Align the radio button and text vertically */
            font-size: 1.1em; /* Adjust text size */
            gap: 0.5em; /* Space between the radio button and text */
        }
        .stRadio input[type="radio"] {
            width: 1.2em; /* Adjust width to scale with text size (relative unit) */
            height: 1.2em; /* Adjust height to scale with text size */
            margin-right: 10px; /* Space between the radio button and the label text */
            accent-color: #4CAF50; /* Color of the radio button when selected */
            vertical-align: middle; /* Align the radio button with the text */
        }
        /* Make images responsive */
        img {
            max-width: 100%;
            height: auto;
        }
        /* Adjust input boxes to fit text */
        .stTextInput>div>div>input {
            font-size: 1.05em !important;
            padding: 0.5em;
        }
        /* Ensure containers adjust to content */
        .css-1l269bu .css-1v3fvcr {
            flex: 1 1 auto;
            width: auto;
            max-width: 100%;
        }
        /* Make the sidebar adjustable */
        @media (max-width: 768px) {
            [data-testid="stSidebar"] {
                width: 12rem; /* Narrower sidebar on smaller screens */
            }
            [data-testid="stSidebar"][aria-expanded="true"] > div:first-child {
                width: 12rem;
            }
        }
        </style>
        """, unsafe_allow_html=True)

    def run(self):
        # Enhanced navigation with more descriptive sidebar
        st.sidebar.title("🔬 Quiz Navigation")
        page = st.sidebar.radio(
            "Navigieren", 
            ["Quiz", "Leaderboard"], 
            index=0
        )

        # Route to appropriate page
        if page == "Quiz":
            self.show_quiz_page()
        elif page == "Leaderboard":
            self.show_leaderboard()

    def show_quiz_page(self):
        """
        Display the quiz page and handle user input for starting the quiz or answering questions.
        """
        if not st.session_state.quiz_started:
            # Display the quiz welcome page
            st.header("🧪 Willkommen zum Quiz")
            with st.form(key='quiz_form'):
                # Input field for user name
                new_name = st.text_input(
                    "Geben Sie Ihren Namen ein", 
                    help="Wähle einen eindeutigen Namen für das Leaderboard", 
                    max_chars=20
                )

                # Quiz mode selection
                st.session_state.quiz_mode = st.radio(
                    "Quiz-Modus auswählen:",
                    ["Einfacher", "Schwerer"],
                    format_func=lambda x: f"{x} Modus",
                    index=["Einfacher", "Schwerer"].index(st.session_state.quiz_mode),
                    key="quiz_mode_radio"
                )

                # Submit button to start the quiz
                submitted = st.form_submit_button("Quiz starten")
                if submitted:
                    # Validate user name
                    if len(new_name.strip()) < 3:
                        st.error("Der Name muss mindestens 3 Zeichen lang sein.")
                    else:
                        try:
                            # Register the user
                            if self.register_user(new_name.strip()):
                                st.success("Registrierung erfolgreich! Lass uns mit dem Quiz beginnen.")
                                st.session_state.user_id = self.get_user_id(new_name.strip())
                                st.session_state.quiz_started = True
                                st.session_state.quiz_start_time = time.time()  # Set quiz start time
                                st.session_state.start_time = time.time()  # For individual question timing
                                st.session_state.current_question = 0
                                st.session_state.total_score = 0
                                # Select questions for the current batch
                                self.select_questions()
                                st.rerun()  # Refresh the page to start the quiz
                            else:
                                st.error("Dieser Name ist bereits vergeben. Bitte wähle einen anderen Namen.")
                        except Exception as e:
                            st.error(f"Registrierung fehlgeschlagen: {str(e)}")
        else:
            # If the quiz has started, run the quiz logic
            self.run_quiz()


    def select_questions(self):
        """
        Wählen Sie Fragen für das Quiz basierend auf dem aktuellen Batch aus und speichern Sie sie im Sitzungszustand.
        """
        # Get current batch from the database
        current_batch = self.db.get_current_batch()
        st.session_state.current_batch = current_batch

        # Determine total number of batches
        total_questions = len(self.questions)
        questions_per_batch = st.session_state.questions_per_batch
        total_batches = total_questions // questions_per_batch
        if total_questions % questions_per_batch != 0:
            total_batches += 1

        # Get the indices for the current batch
        start_index = (current_batch - 1) * questions_per_batch
        end_index = start_index + questions_per_batch
        selected = self.questions[start_index:end_index]

        # If we reach the end, wrap around
        if not selected:
            # Reset to the first batch
            st.session_state.current_batch = 1
            start_index = 0
            end_index = questions_per_batch
            selected = self.questions[start_index:end_index]

        st.session_state.selected_questions = selected

        # Update the current batch for the next user
        next_batch = current_batch + 1
        if next_batch > total_batches:
            next_batch = 1  # Wrap around to the first batch

        self.db.update_current_batch(next_batch)
    
    def run_quiz(self):
        if st.session_state.current_question >= st.session_state.questions_per_batch:
            # Quiz completion screen
            st.balloons()
            st.success(f"🎉 Quiz abgeschlossen! Deine Endpunktzahl: {st.session_state.total_score} Punkte")
            st.session_state.leaderboard_needs_update = True

            # Calculate total time taken
            total_time = time.time() - st.session_state.quiz_start_time
            # Save the quiz session with total time
            self.save_quiz_session(st.session_state.total_score, total_time)

            if st.button("Neues Quiz starten"):
                self.reset_quiz()
            return

        question_index = st.session_state.current_question
        question = st.session_state.selected_questions[question_index]
        self.display_question(question)
    
    def format_time(self, seconds):
        """
        Format time from seconds to MM:SS format
        """
        minutes = int(seconds) // 60
        sec = int(seconds) % 60
        return f"{minutes:02d}:{sec:02d}"
    
    def reset_quiz(self):
        """
        Reset the quiz session state for a new quiz.
        """
        # Reset all session state variables
        st.session_state.quiz_started = False
        st.session_state.current_question = 0
        st.session_state.start_time = None
        st.session_state.quiz_start_time = None  # Reset quiz start time
        st.session_state.total_score = 0
        st.session_state.question_answered = False
        st.session_state.selected_questions = []


    def display_question(self, question: Question):
        # Add custom HTML and CSS for the question background with dynamic size
        st.markdown(
            """
            <style>
            .question-container {
                background-color: #f9f9fc;
                border: 2px solid #e0e0eb;
                border-radius: 10px;
                padding: 12px;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                margin-bottom: 12px;
                display: inline-block;
                width: 100%;  /* Adjust to full width */
                word-wrap: break-word;
            }
            </style>
            """, unsafe_allow_html=True
        )

        st.markdown(
            f"<h2 style='font-size:1.2em; font-weight:bold;'>Frage {st.session_state.current_question + 1}/{st.session_state.questions_per_batch}</h2>",
            unsafe_allow_html=True
        )
        st.markdown(f"<h4>Aktuelle Punktzahl: {st.session_state.total_score} Punkte</h4>", unsafe_allow_html=True)
        st.markdown("---")

        # Wrap the question in the styled div
        st.markdown(
            f"""
            <div class="question-container">
                <p>{question.question_easy if st.session_state.quiz_mode == 'Einfacher' else question.question_hard}</p>
            </div>
            """, unsafe_allow_html=True
        )

        image_url = question.image_url_easy if st.session_state.quiz_mode == "Einfacher" else question.image_url_hard
        if image_url:
            # Display the image and ensure it adjusts to screen width
            st.image(image_url, use_container_width=True, caption=f"{st.session_state.quiz_mode} Modus Spektrum")

        user_answer = st.radio("Wählen Sie Ihre Antwort:", question.options)
        submitted = st.button("Antwort einreichen")

        # Check if the question has already been answered
        question_answered = "question_answered" in st.session_state and st.session_state.question_answered

        if submitted and not question_answered:
            # Process the answer if it has not been processed yet
            is_correct = user_answer == question.correct_answer
            time_taken = time.time() - st.session_state.start_time

            if is_correct:
                st.success("🎉 Richtig! Gute Arbeit!")
                st.session_state.total_score += 1
            else:
                st.error(f"❌ Falsch. Die richtige Antwort war: {question.correct_answer}")

            # Save the quiz result
            self.save_quiz_result(question.id, user_answer, is_correct, time_taken)

            # Mark the question as answered
            st.session_state.question_answered = True

        # Add a "Next" button to move to the next question
        if st.session_state.question_answered:
            if st.button("Weiter"):
                st.session_state.current_question += 1
                st.session_state.start_time = time.time()
                st.session_state.question_answered = False
                st.rerun()

    def save_quiz_result(self, question_id: int, user_answer: str, is_correct: bool, time_taken: float):
        """
        Speichern Sie das Quiz-Ergebnis in der Datenbank
        """
        if not st.session_state.user_id:
            st.error("Benutzer nicht registriert. Quiz-Ergebnis kann nicht gespeichert werden.")
            return

        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()

                # Insert quiz result with timestamp to allow multiple attempts
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
            logging.error(f"Datenbankfehler beim Speichern des Quiz-Ergebnisses: {e}")
            st.error("Ein Fehler ist aufgetreten, während Ihr Quiz-Ergebnis gespeichert wurde.")

    def save_quiz_session(self, total_score: int, total_time: float):
        """
        Save the quiz session with total score and total time.
        """
        if not st.session_state.user_id:
            st.error("Benutzer nicht registriert. Quiz-Sitzung kann nicht gespeichert werden.")
            return

        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                # Save a new row for this quiz session
                c.execute('''
                    INSERT INTO quiz_sessions
                    (user_id, total_score, total_time, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (
                    st.session_state.user_id,
                    total_score,
                    total_time,
                    datetime.now()
                ))
                conn.commit()
        except sqlite3.Error as e:
            logging.error(f"Datenbankfehler beim Speichern der Quiz-Sitzung: {e}")
            st.error("Ein Fehler ist aufgetreten, während Ihre Quiz-Sitzung gespeichert wurde.")

    def register_user(self, name: str) -> bool:
        """
        Register a new user in the database. Prevent duplicate names.
        """
        if not name:
            st.error("Bitte geben Sie einen Namen ein.")
            return False

        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                # Check if the name already exists
                c.execute('SELECT id FROM users WHERE name = ?', (name,))
                if c.fetchone():
                    st.error("Dieser Name ist bereits vergeben. Bitte wählen Sie einen anderen Namen.")
                    return False

                # Insert new user
                c.execute('INSERT INTO users (name) VALUES (?)', (name,))
                conn.commit()
                return True
        except sqlite3.Error as e:
            logging.error(f"Registrierung des Benutzers fehlgeschlagen: {name}, Fehler: {e}")
            st.error("Ein Fehler ist aufgetreten, während der Benutzer registriert wurde.")
            return False


    def get_user_id(self, name: str) -> Optional[int]:
        """
        Benutzer-ID für einen gegebenen Namen abrufen
        """
        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                c.execute('SELECT id FROM users WHERE name = ?', (name,))
                result = c.fetchone()
                return result[0] if result else None
        except sqlite3.Error as e:
            logging.error(f"Fehler beim Abrufen der Benutzer-ID: {e}")
            return None
        
    from streamlit_autorefresh import st_autorefresh

    def show_leaderboard(self):

        """
        Display the leaderboard with unique entries per user, including predefined scores for the model, highlighted.
        """
        # Add an autorefresh to the leaderboard page
        count = st_autorefresh(interval=5000, key="leaderboard_refresh")

        st.title("🏆 Leaderboard")

        # Predefined scores for demonstration or model
        predefined_scores = pd.DataFrame({
            "Spieler": ["GPT", "Llama", "Claude", "Gemini"],
            "Gesamtpunkte": [2, 2, 1, 1],
            "Gesamtzeit": [0, 0, 0, 0]  # Time in seconds
        })

        try:
            with self.db.get_connection() as conn:
                # Fetch leaderboard data (latest session or best score per user)
                df = pd.read_sql_query('''
                    SELECT u.name AS Spieler, 
                        MAX(qs.total_score) AS Gesamtpunkte, 
                        MIN(qs.total_time) AS Gesamtzeit
                    FROM quiz_sessions qs
                    JOIN users u ON qs.user_id = u.id
                    GROUP BY qs.user_id
                    ORDER BY Gesamtpunkte DESC, Gesamtzeit ASC;
                ''', conn)

                if df.empty:
                    st.info("Noch keine Daten verfügbar. Beginnen Sie zu spielen, um auf der Leaderboard zu erscheinen!")
                    df = predefined_scores  # Only show predefined scores if no data exists
                else:
                    # Format the total time from seconds to MM:SS
                    df['Gesamtzeit'] = df['Gesamtzeit'].apply(lambda x: self.format_time(x))

                    # Combine predefined scores with actual data
                    df = pd.concat([df, predefined_scores]).sort_values(
                        by=["Gesamtpunkte", "Gesamtzeit"], ascending=[False, True]
                    )

                # Set index starting from 1
                df.index = range(1, len(df) + 1)

                # Highlight predefined models with softer purple and adjust text color
                def highlight_models(row):
                    if row['Spieler'] in predefined_scores['Spieler'].values:
                        return ['background-color: #CBC3E3; color: black'] * len(row)  # Softer purple with black text
                    else:
                        return [''] * len(row)

                # Apply styling
                styled_df = df.style.apply(highlight_models, axis=1)

                # Display leaderboard with styling
                st.dataframe(styled_df, use_container_width=True)
        except sqlite3.Error as e:
            logging.error(f"Fehler beim Abrufen der Leaderboard: {e}")
            st.error("Leaderboard-Daten können nicht abgerufen werden.")


def main():
    quiz_app = QuizApp()
    quiz_app.run()

if __name__ == "__main__":
    main()
