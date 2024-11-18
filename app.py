import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import plotly.graph_objects as go
from dataclasses import dataclass
from typing import List, Optional
import bcrypt  # Use bcrypt for secure password hashing
import time
import numpy as np
import os  # For environment variables
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

@dataclass
class Question:
    id: int
    question: str
    options: List[str]
    correct_answer: str
    explanation: str
    difficulty: str
    category: str
    image_url: Optional[str] = None  # For images if needed
    spectrum_type: Optional[str] = None  # 'NMR', 'MS', etc.
    spectrum_params: Optional[dict] = None  # Parameters for spectrum generation

class DatabaseManager:
    def __init__(self, db_name=None):
        # Use environment variable for the database name, default to 'quiz_results.db'
        self.db_name = db_name or os.getenv('DB_NAME', 'quiz_results.db')
        self.init_database()

    def get_connection(self):
        conn = sqlite3.connect(self.db_name)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_database(self):
        with self.get_connection() as conn:
            c = conn.cursor()
            
            # Users table
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_points INTEGER DEFAULT 0,
                    quiz_attempts INTEGER DEFAULT 0
                )
            ''')
            
            # Quiz results table with unique constraint on (user_id, question_id)
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
    questions = [
        Question(
            id=1,
            question="Which part of the electromagnetic spectrum is used in standard kitchen microwave ovens?",
            options=["Infrared", "Visible Light", "Microwaves", "Ultraviolet"],
            correct_answer="Microwaves",
            explanation="Microwave ovens use microwaves, a type of electromagnetic radiation, to heat food.",
            difficulty="easy",
            category="Everyday Spectroscopy"
        ),
        Question(
            id=2,
            question="What natural phenomenon creates a spectrum of colors in the sky known as a rainbow?",
            options=["Reflection", "Refraction", "Diffraction", "Interference"],
            correct_answer="Refraction",
            explanation="A rainbow is formed due to the refraction of sunlight by water droplets in the atmosphere.",
            difficulty="easy",
            category="Optical Spectroscopy"
        ),
        Question(
            id=3,
            question="Which device is used to split light into its component colors?",
            options=["Microscope", "Telescope", "Spectroscope", "Periscope"],
            correct_answer="Spectroscope",
            explanation="A spectroscope splits light into its component wavelengths, allowing us to see the spectrum.",
            difficulty="medium",
            category="Spectroscopy Tools"
        ),
        Question(
            id=4,
            question="What is the term for the range of all types of electromagnetic radiation?",
            options=["Electromagnetic Spectrum", "Visible Spectrum", "Ultraviolet Spectrum", "Infrared Spectrum"],
            correct_answer="Electromagnetic Spectrum",
            explanation="The electromagnetic spectrum encompasses all types of electromagnetic radiation.",
            difficulty="easy",
            category="Basics of Spectroscopy"
        ),
        Question(
            id=5,
            question="Which technology uses infrared spectroscopy to control remote devices like TVs?",
            options=["Bluetooth", "Wi-Fi", "Infrared Remote Control", "NFC"],
            correct_answer="Infrared Remote Control",
            explanation="Infrared remote controls use infrared light to send signals to devices.",
            difficulty="easy",
            category="Applications of Spectroscopy"
        ),
        Question(
            id=6,
            question="Identify the region in the NMR spectrum where protons in a benzene ring appear.",
            options=["0-1 ppm", "2-3 ppm", "5-6 ppm", "7-8 ppm"],
            correct_answer="7-8 ppm",
            explanation="Protons in aromatic rings like benzene typically appear downfield at 7-8 ppm due to deshielding.",
            difficulty="medium",
            category="NMR Spectroscopy",
            spectrum_type="NMR",
            spectrum_params={
                "peaks": [
                    {"center": 7.5, "height": 1, "width": 0.1},  # Aromatic proton signal
                    {"center": 2.5, "height": 0.5, "width": 0.2}  # Aliphatic proton signal
                ]
            }
        ),
        Question(
            id=7,
            question="Based on the mass spectrum provided, what does the peak at m/z 78 represent?",
            options=[
                "Base peak",
                "Molecular ion of benzene",
                "Fragment ion of toluene",
                "Doubly charged ion"
            ],
            correct_answer="Molecular ion of benzene",
            explanation="The peak at m/z 78 corresponds to the molecular ion of benzene (C6H6).",
            difficulty="medium",
            category="Mass Spectrometry",
            spectrum_type="MS",
            spectrum_params={
                "peaks": {
                    18: 15,    # Water loss
                    28: 30,    # CO or N2
                    44: 50,    # CO2
                    78: 100,   # Benzene molecular ion
                    91: 70,    # Tropylium ion
                    105: 40,   # Phenol molecular ion
                }
            }
        ),
        # Add more spectroscopy-themed questions suitable for non-chemists...
    ]
    return questions

class QuizApp:
    def __init__(self):
        self.db = DatabaseManager()
        self.questions = create_question_bank()
        self.init_session_state()
        self.setup_page()

    def init_session_state(self):
        if "current_question" not in st.session_state:
            st.session_state.current_question = 0
        if "user_id" not in st.session_state:
            st.session_state.user_id = None
        if "quiz_mode" not in st.session_state:
            st.session_state.quiz_mode = "Practice"
        if "start_time" not in st.session_state:
            st.session_state.start_time = None
        if "page" not in st.session_state:
            st.session_state.page = "Home"
        if "quiz_started" not in st.session_state:
            st.session_state.quiz_started = False
        if "answered_questions" not in st.session_state:
            st.session_state.answered_questions = set()  # Use a set to track answered question IDs
        if "login" not in st.session_state:
            st.session_state.login = False

    def setup_page(self):
        st.set_page_config(
            page_title="Spectroscopy for Everyone Quiz",
            page_icon="🔭",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        st.sidebar.title("🔭 Navigation")
        st.session_state.page = st.sidebar.radio(
            "Select Page",
            ["Home", "Quiz", "Learning Center", "Profile", "Leaderboard"],
            index=["Home", "Quiz", "Learning Center", "Profile", "Leaderboard"].index(st.session_state.page)
        )
        # Add a logout button if the user is logged in
        if st.session_state.user_id:
            if st.sidebar.button("Logout"):
                st.session_state.user_id = None
                st.session_state.quiz_started = False
                st.success("Logged out successfully.")
                st.rerun()
        self.page = st.session_state.page

    def display_question(self, question: Question) -> Optional[tuple]:
        # Check if the question has already been answered by querying the database
        if self.is_question_answered(question.id):
            st.markdown(f"### Question {st.session_state.current_question + 1}")
            st.info("You have already answered this question.")
            st.markdown(f"**Your previous answer:** {self.get_user_answer(question.id)}")
            st.markdown(f"**Explanation:** {question.explanation}")
            # Move to the next question
            if st.button("Next Question"):
                st.session_state.current_question += 1
                st.rerun()
            return None

        st.markdown(f"### Question {st.session_state.current_question + 1}")

        with st.form(key=f"question_form_{question.id}"):
            # Layout with image and text side by side
            if question.image_url or question.spectrum_type:
                col_image, col_text = st.columns([1, 3])  # Adjust the ratio as needed
            else:
                col_text = st.container()
                col_image = None

            if col_image:
                with col_image:
                    if question.image_url:
                        st.image(question.image_url, use_column_width=True)
                    elif question.spectrum_type:
                        if question.spectrum_type == "NMR":
                            self.display_nmr_spectrum(question.spectrum_params)
                        elif question.spectrum_type == "MS":
                            self.display_ms_spectrum(question.spectrum_params)
                        else:
                            st.write("Spectrum type not recognized.")
            with col_text:
                st.markdown(f"**{question.question}**")
                user_answer = st.radio("Select your answer:", question.options, key=f"q_{question.id}")
                st.markdown(f"**Difficulty:** {question.difficulty.capitalize()}")
                st.markdown(f"**Category:** {question.category}")

            submitted = st.form_submit_button("Submit Answer")
            if submitted:
                is_correct = user_answer == question.correct_answer
                time_taken = time.time() - st.session_state.start_time

                if is_correct:
                    st.success("🎉 Correct! Great job!")
                else:
                    st.error(f"❌ Incorrect. The correct answer was: {question.correct_answer}")

                st.info(f"📚 **Explanation:** {question.explanation}")

                # Update start time for the next question
                st.session_state.start_time = time.time()
                # Save the result
                self.save_quiz_result(question.id, user_answer, is_correct, time_taken)
                # Mark the question as answered
                st.session_state.answered_questions.add(question.id)
                # Update question index
                st.session_state.current_question += 1
                # Force a rerun to display the next question
                st.rerun()
            else:
                return None

    def is_question_answered(self, question_id: int) -> bool:
        """Check if the question has already been answered by the user."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT COUNT(*) FROM quiz_results
                WHERE user_id = ? AND question_id = ?
            ''', (st.session_state.user_id, question_id))
            result = c.fetchone()
            return result[0] > 0

    def get_user_answer(self, question_id: int) -> Optional[str]:
        """Get the user's previous answer to a question."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT user_answer FROM quiz_results
                WHERE user_id = ? AND question_id = ?
            ''', (st.session_state.user_id, question_id))
            result = c.fetchone()
            return result[0] if result else None

    def run(self):
        if self.page == "Home":
            self.show_home_page()
        elif self.page == "Quiz":
            self.show_quiz_page()
        elif self.page == "Learning Center":
            self.show_learning_center()
        elif self.page == "Profile":
            self.show_profile_page()
        elif self.page == "Leaderboard":
            self.show_leaderboard()

    def show_home_page(self):
        st.title("🔭 Welcome to Spectroscopy for Everyone Quiz")
        st.markdown("""
        ### Discover the World of Light and Spectra
        Dive into the fascinating world of spectroscopy with questions designed for everyone:
        - Learn about different types of light
        - Understand how we use light to explore the universe
        - Discover everyday applications of spectroscopy

        ### Features
        - Engaging questions suitable for all audiences
        - Detailed explanations to enhance understanding
        - Progress tracking and leaderboard
        - Learning resources to explore more
        """)

    def show_quiz_page(self):
        if not st.session_state.user_id:
            self.show_login_page()
            return

        st.title("📝 Spectroscopy Quiz")

        # Quiz mode selection
        if not st.session_state.quiz_started:
            st.session_state.quiz_mode = st.radio(
                "Select Quiz Mode:",
                ["Practice"],
                index=["Practice"].index(st.session_state.quiz_mode),
                key="quiz_mode_radio"
            )
            if st.button("Start Quiz"):
                st.session_state.start_time = time.time()
                st.session_state.quiz_started = True
                st.session_state.current_question = 0  # Reset question index
                st.session_state.answered_questions = set()  # Reset answered questions
                # Force a rerun to start the quiz
                st.rerun()
        else:
            self.start_quiz(st.session_state.quiz_mode)

    def hash_password(self, password: str) -> str:
        """Hash a password for storing."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, stored_password: str, provided_password: str) -> bool:
        """Verify a stored password against one provided by user"""
        return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))

    def show_login_page(self):
        st.title("👤 Login / Register")
        
        tab1, tab2 = st.tabs(["Login", "Register"])
        
        with tab1:
            st.subheader("Login")
            with st.form(key="login_form"):
                login_email = st.text_input("Email", key="login_email")
                login_password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Login")
                if submitted:
                    if self.authenticate_user(login_email.strip(), login_password.strip()):
                        st.success("Successfully logged in!")
                        st.session_state.user_id = self.get_user_id(login_email.strip())
                        # Force a rerun to update the page
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Invalid email or password")
        
        with tab2:
            st.subheader("Register")
            with st.form(key="register_form"):
                new_name = st.text_input("Name", key="reg_name")
                new_email = st.text_input("Email", key="reg_email")
                new_password = st.text_input("Password", type="password", key="reg_password")
                confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")
                submitted = st.form_submit_button("Register")
                if submitted:
                    if new_password != confirm_password:
                        st.error("Passwords do not match!")
                    elif self.register_user(new_name.strip(), new_email.strip(), new_password.strip()):
                        st.success("Registration successful! Please login.")
                        # Optionally, switch to the Login tab
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Registration failed. Email might already be registered.")

    def authenticate_user(self, email: str, password: str) -> bool:
        """Authenticate a user."""
        if not email or not password:
            return False
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT password_hash FROM users WHERE email = ?', (email,))
            result = c.fetchone()
            
            if result is None:
                return False
            
            stored_password = result[0]
            return self.verify_password(stored_password, password)

    def register_user(self, name: str, email: str, password: str) -> bool:
        """Register a new user."""
        if not name or not email or not password:
            return False
        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                password_hash = self.hash_password(password)
                c.execute(
                    'INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)',
                    (name, email, password_hash)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError as e:
            logging.error(f"IntegrityError: {e}")
            return False

    def get_user_id(self, email: str) -> Optional[int]:
        """Get user ID from email."""
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT id FROM users WHERE email = ?', (email,))
            result = c.fetchone()
            return result[0] if result else None

    def start_quiz(self, mode: str):
        """Start a new quiz based on the selected mode."""
        if mode == "Practice":
            self.run_practice_mode()

    def run_practice_mode(self):
        """Run the practice mode quiz."""
        if st.session_state.current_question >= len(self.questions):
            st.success("🎉 Quiz completed! Check your profile for results.")
            st.session_state.quiz_started = False
            return

        question = self.questions[st.session_state.current_question]
        self.display_question(question)

    def save_quiz_result(self, question_id: int, user_answer: str, is_correct: bool, time_taken: float):
        """Save quiz result to database and update user stats."""
        try:
            with self.db.get_connection() as conn:
                c = conn.cursor()
                c.execute('''
                    INSERT INTO quiz_results 
                    (user_id, question_id, user_answer, is_correct, time_taken, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (st.session_state.user_id, question_id, user_answer, is_correct, time_taken, datetime.now()))
                # Update user stats
                points = 1 if is_correct else 0
                c.execute('''
                    UPDATE users
                    SET total_points = total_points + ?,
                        quiz_attempts = quiz_attempts + 1
                    WHERE id = ?
                ''', (points, st.session_state.user_id))
                conn.commit()
        except sqlite3.IntegrityError as e:
            logging.error(f"IntegrityError: {e}")
            # Duplicate entry detected, do not award points again
            pass

    def show_profile_page(self):
        if not st.session_state.user_id:
            self.show_login_page()
            return
                
        st.title("👤 User Profile")
        
        # Fetch user data
        with self.db.get_connection() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT name, email, total_points, quiz_attempts 
                FROM users WHERE id = ?
            ''', (st.session_state.user_id,))
            user_data = c.fetchone()
            
            if user_data:
                name, email, total_points, quiz_attempts = user_data
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Name:** {name}")
                    st.markdown(f"**Email:** {email}")
                
                with col2:
                    st.markdown(f"**Total Points:** {total_points}")
                    st.markdown(f"**Quiz Attempts:** {quiz_attempts}")
                
                # Show progress charts
                self.show_user_progress()
            else:
                st.error("User data not found.")

    def show_user_progress(self):
        """Show user progress charts."""
        with self.db.get_connection() as conn:
            df = pd.read_sql_query('''
                SELECT 
                    strftime('%Y-%m-%d', timestamp) as date,
                    COUNT(*) as attempts,
                    AVG(CASE WHEN is_correct THEN 1 ELSE 0 END) * 100 as accuracy
                FROM quiz_results
                WHERE user_id = ?
                GROUP BY date
                ORDER BY date
            ''', conn, params=(st.session_state.user_id,))
            
            if not df.empty:
                st.subheader("Your Progress")
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df['date'],
                    y=df['accuracy'],
                    name='Accuracy (%)',
                    mode='lines+markers'
                ))
                
                fig.update_layout(
                    title='Daily Quiz Accuracy',
                    xaxis_title='Date',
                    yaxis_title='Accuracy (%)',
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No quiz data available to display progress.")

    def show_learning_center(self):
        st.title("📚 Learning Center")
        st.markdown("""
        ### Explore Spectroscopy

        Discover how spectroscopy impacts our daily lives and the world around us:

        - **Understanding Light:** Learn about the electromagnetic spectrum and types of light.
        - **Everyday Applications:** See how spectroscopy is used in common technologies.
        - **Astronomical Discoveries:** Find out how scientists use light to explore the universe.
        - **Interactive Resources:** Engage with videos and articles to deepen your knowledge.

        ### Featured Topics
        - The Science Behind Rainbows
        - How Remote Controls Work
        - Spectroscopy in Astronomy
        - Medical Imaging Technologies
        """)

        # Added NMR and MS Spectra Plots
        st.subheader("Interactive Spectra Plots")

        # Display NMR Spectra
        st.markdown("#### Example NMR Spectrum")
        self.display_nmr_spectrum()

        # Display MS Spectra
        st.markdown("#### Example Mass Spectrum")
        self.display_ms_spectrum()

        st.markdown("#### Useful Links")
        st.write("- [NASA's Introduction to the Electromagnetic Spectrum](https://science.nasa.gov/ems)")
        st.write("- [How Microwaves Work](https://home.howstuffworks.com/microwave.htm)")
        st.write("- [Spectroscopy Basics](https://www.khanacademy.org/science/physics/light-waves)")
        st.write("- [Rainbows Explained](https://www.metoffice.gov.uk/weather/learn-about/weather/optical-effects/rainbows)")

    def display_nmr_spectrum(self, spectrum_params=None):
        """Display a dummy NMR spectrum."""
        # Generate dummy NMR data
        ppm = np.linspace(10, 0, 1000)
        signal = np.zeros_like(ppm)

        # Default parameters if none provided
        if not spectrum_params:
            spectrum_params = {
                "peaks": [
                    {"center": 7.5, "height": 1, "width": 0.1},
                    {"center": 2.5, "height": 1, "width": 0.2}
                ]
            }

        for peak in spectrum_params.get("peaks", []):
            signal += self.nmr_signal(ppm, peak["center"], peak["height"], peak["width"])

        # Add noise
        signal += np.random.normal(0, 0.02, ppm.size)

        # Create the plot
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=ppm,
            y=signal,
            mode='lines',
            line_color='blue',
            name='NMR Signal'
        ))

        # Reverse x-axis for NMR spectra
        fig.update_layout(
            xaxis_title='Chemical Shift (ppm)',
            yaxis_title='Intensity',
            xaxis=dict(autorange='reversed'),
            showlegend=False,
            height=300
        )

        st.plotly_chart(fig, use_container_width=True)

    def nmr_signal(self, ppm, center, height, width):
        """Generate a Lorentzian peak for NMR signal."""
        return height * (width**2 / ((ppm - center)**2 + width**2))

    def display_ms_spectrum(self, spectrum_params=None):
        """Display a dummy Mass Spectrum."""
        # Generate dummy MS data
        m_z = np.arange(0, 200, 1)
        intensity = np.zeros_like(m_z, dtype=float)

        # Default parameters if none provided
        if not spectrum_params:
            spectrum_params = {
                "peaks": {
                    18: 15,    # Water loss
                    28: 30,    # CO or N2
                    44: 50,    # CO2
                    78: 100,   # Benzene molecular ion
                    91: 70,    # Tropylium ion
                    105: 40,   # Phenol molecular ion
                }
            }

        for mz_value, height in spectrum_params.get("peaks", {}).items():
            intensity[m_z == mz_value] = height

        # Add some random noise
        intensity += np.random.normal(0, 2, m_z.size)
        intensity = np.clip(intensity, 0, None)  # Ensure no negative intensities

        # Create the plot
        fig = go.Figure(go.Bar(
            x=m_z,
            y=intensity,
            marker_color='red',
            name='Intensity'
        ))

        fig.update_layout(
            xaxis_title='m/z (Mass-to-Charge Ratio)',
            yaxis_title='Relative Abundance',
            showlegend=False,
            height=300
        )

        st.plotly_chart(fig, use_container_width=True)

    def show_leaderboard(self):
        st.title("🏆 Leaderboard")
        st.markdown("### Top Users by Total Points")
        
        with self.db.get_connection() as conn:
            df = pd.read_sql_query('''
                SELECT name, total_points
                FROM users
                ORDER BY total_points DESC
                LIMIT 10
            ''', conn)
            
            if df.empty:
                st.info("No data to display yet.")
            else:
                # Reset the index and adjust it to start from 1
                df.reset_index(drop=True, inplace=True)
                df.index += 1
                df.index.name = 'Rank'
                # Display the leaderboard table
                st.table(df)

if __name__ == "__main__":
    quiz_app = QuizApp()
    quiz_app.run()
