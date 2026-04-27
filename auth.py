import hashlib
from backend.db import get_conn

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def create_user(u, p):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("CREATE TABLE IF NOT EXISTS users (u TEXT, p TEXT)")
    cur.execute("INSERT INTO users VALUES (?,?)", (u, hash_pw(p)))

    conn.commit()
    conn.close()

def login_user(u, p):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT * FROM users WHERE u=? AND p=?", (u, hash_pw(p)))
    user = cur.fetchone()

    conn.close()
    return user is not None
