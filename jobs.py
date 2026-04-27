from backend.db import get_conn
import json, datetime

def create_job(user, name, result):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        user TEXT,
        name TEXT,
        result TEXT,
        created TEXT
    )
    """)

    cur.execute("INSERT INTO jobs VALUES (?,?,?,?)",
                (user, name, json.dumps(result), str(datetime.datetime.now())))

    conn.commit()
    conn.close()

def get_jobs(user):

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT name, created FROM jobs WHERE user=?", (user,))
    data = cur.fetchall()

    conn.close()
    return data
