import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(r"c:\folder fix\backend\.env")

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL")
    exit(1)

sql_file = r"c:\folder fix\supabase\migrations\20260404_add_distance_km_schools.sql"
with open(sql_file, "r") as f:
    sql = f.read()

try:
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cursor = conn.cursor()
    cursor.execute(sql)
    print("Migration applied successfully.")
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals():
        conn.close()
