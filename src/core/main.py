import os
import psycopg2  # Example for connecting to the database

# Read environment variables
supabase_url = os.getenv("SUPABASE_URL", "http://localhost:54321")
supabase_key = os.getenv("SUPABASE_KEY", "your-anon-key")

# Connect to the Supabase PostgreSQL database
try:
    conn = psycopg2.connect(
        host="supabase_db",  # Use the service name defined in docker-compose.yml
        database="postgres",
        user="postgres",
        password="postgres"
    )
    print("Connected to the database!")
except Exception as e:
    print(f"Database connection error: {e}")
