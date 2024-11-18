import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import matplotlib.pyplot as plt

# Initialize session state to track the current question
if "current_question" not in st.session_state:
    st.session_state.current_question = 1

# Create or connect to a database
conn = sqlite3.connect('quiz_results.db')
c = conn.cursor()

# Create a table to store results
c.execute('''
    CREATE TABLE IF NOT EXISTS quiz_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        question TEXT,
        user_answer TEXT,
        correct_answer TEXT,
        is_correct BOOLEAN,
        timestamp TIMESTAMP
    )
''')
conn.commit()

# Function to save results to the database
def save_result(name, email, question, user_answer, correct_answer, is_correct):
    # Check if the user has already answered the question
    c.execute('''
        SELECT * FROM quiz_results WHERE name = ? AND email = ? AND question = ?
    ''', (name, email, question))
    if c.fetchone() is None:  # Only save if the question has not been answered before
        c.execute('''
            INSERT INTO quiz_results (name, email, question, user_answer, correct_answer, is_correct, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, email, question, user_answer, correct_answer, is_correct, datetime.now()))
        conn.commit()

# Function to display a single question
def display_question(question, options, correct_answer, image=None):
    st.write(question)
    
    # Display an image if provided
    if image:
        st.pyplot(image)
    
    user_answer = st.radio("Choose your answer:", options, key=question)
    
    if st.button("Submit Answer", key=f"button_{question}"):
        is_correct = user_answer == correct_answer
        st.write("🎉 Correct!" if is_correct else f"❌ Incorrect. The correct answer was {correct_answer}.")
        
        # Move to the next question
        st.session_state.current_question += 1
        return user_answer, is_correct
    return None, None

# Function to display a dummy plot
def create_dummy_plot():
    fig, ax = plt.subplots()
    ax.plot([0, 1, 2, 3], [0, 1, 4, 9])
    ax.set_title("Dummy Plot")
    return fig

# Function to calculate and display the leaderboard
def display_leaderboard():
    st.subheader("🏆 Live Leaderboard")

    # Retrieve all results from the database
    c.execute('SELECT name, is_correct FROM quiz_results')
    results = c.fetchall()

    # Calculate scores for each user
    scores = {}
    for name, is_correct in results:
        if name not in scores:
            scores[name] = 0
        if is_correct:
            scores[name] += 1

    # Convert scores to a DataFrame and sort by the number of correct answers
    leaderboard_df = pd.DataFrame(scores.items(), columns=["Name", "Score"])
    leaderboard_df = leaderboard_df.sort_values(by="Score", ascending=False).reset_index(drop=True)

    # Add some styling to the leaderboard
    st.table(leaderboard_df.style.format({"Score": "{:.0f}"}).highlight_max("Score", color="lightgreen"))

# App layout with tabs
st.title("Spectra to Structure Quiz")
st.write("Test your knowledge of interpreting spectra to determine structures. Have fun and learn!")

# Create tabs for the Quiz, Leaderboard, and Admin (restricted) section
tabs = st.tabs(["Quiz", "Leaderboard", "Admin"])

# Quiz tab
with tabs[0]:
    st.subheader("🧪 Take the Quiz")

    # User info
    name = st.text_input("Enter your name:")
    email = st.text_input("Enter your email:")

    if name and email:
        st.write("Answer the following questions one by one:")

        # Question 1
        if st.session_state.current_question == 1:
            question_1 = "What type of functional group is indicated by a strong absorption around 1700 cm⁻¹ in an IR spectrum?"
            options_1 = ["Alcohol", "Ketone", "Ester", "Amine"]
            correct_answer_1 = "Ketone"
            dummy_plot_1 = create_dummy_plot()
            user_answer_1, is_correct_1 = display_question(question_1, options_1, correct_answer_1, image=dummy_plot_1)
            
            if user_answer_1:
                save_result(name, email, question_1, user_answer_1, correct_answer_1, is_correct_1)

        # Question 2 (only shown if Question 1 is answered)
        elif st.session_state.current_question == 2:
            question_2 = "What splitting pattern would you expect for a methyl group adjacent to a methylene group in an NMR spectrum?"
            options_2 = ["Singlet", "Doublet", "Triplet", "Quartet"]
            correct_answer_2 = "Triplet"
            dummy_plot_2 = create_dummy_plot()
            user_answer_2, is_correct_2 = display_question(question_2, options_2, correct_answer_2, image=dummy_plot_2)
            
            if user_answer_2:
                save_result(name, email, question_2, user_answer_2, correct_answer_2, is_correct_2)

# Leaderboard tab
with tabs[1]:
    display_leaderboard()

# Admin tab (restricted access)
with tabs[2]:
    st.subheader("⚙️ Admin")
    
    # Simple password protection
    admin_password = st.text_input("Enter admin password:", type="password")
    if admin_password == "your_secure_password":
        if st.button("Clean Database"):
            c.execute('DELETE FROM quiz_results')
            conn.commit()
            st.success("Database has been cleaned successfully!")
    else:
        st.warning("Incorrect password. Access denied.")

# Close the database connection
conn.close()

# Instructions for running the app
st.write("Run this app with `streamlit run your_app_name.py`.")
