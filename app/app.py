from flask import Flask, render_template
import psycopg2
import os

app = Flask(__name__)

def get_db_connection():
    conn = psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        database=os.environ.get("POSTGRES_DB", "home_budget"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres")
    )
    return conn

@app.route("/")
def index():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT something, value FROM test LIMIT 1;")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("index.html", something=row[0], value=row[1])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
