import streamlit as st
import pyodbc

def app():
    server = '61.91.59.134'
    port = '1544'
    database = 'KGETEST'
    db_username = 'sa'
    db_password = 'kg@dm1nUsr!'
    conn_str = f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server},{port};DATABASE={database};UID={db_username};PWD={db_password}'

    try:
        with pyodbc.connect(conn_str) as conn:
            st.write("Connection successful")
            # Your database operations here
    except pyodbc.Error as e:
        st.error(f"Database connection error: {e}")
        # Log the error to a file or external logging service if needed

if __name__ == "__main__":
    app()
