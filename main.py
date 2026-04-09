import requests
from bs4 import BeautifulSoup
from openai import OpenAI
import smtplib
from datetime import datetime
import sqlite3

# === CONFIG via ENV ===
import os
EMAIL = os.getenv("EMAIL")
PASSWORD = os.getenv("PASSWORD")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

USER_PROFILE = """
Executive bridging strategy and execution across business, product, and technology.
Strong in transformation, cyber security, and commercial impact.
Prefers Director / Head / Lead roles in EU or remote environments.
"""

# === DB ===
def init_db():
    conn = sqlite3.connect("jobs.db")
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        title TEXT,
        link TEXT,
        score INTEGER,
        status TEXT
    )
    """)
    conn.commit()
    conn.close()

# === FETCH ===
def fetch_jobs():
    queries = [
        "director transformation europe",
        "head of cyber security europe",
        "program director digital transformation remote"
    ]

    jobs = []

    for q in queries:
        url = f"https://www.indeed.com/jobs?q={q}&l=Europe"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(res.text, "html.parser")

        for job in soup.select("a.tapItem"):
            title = job.get_text(strip=True)
            link = "https://indeed.com" + job.get("href")

            jobs.append({
                "title": title,
                "link": link,
                "desc": title
            })

    return jobs

# === AI SCORE ===
def ai_score(job):
    text = job["title"] + " " + job["desc"]

    if "ibm" in text.lower():
        return 0, "Excluded (IBM)"

    prompt = f"""
    Candidate:
    {USER_PROFILE}

    Job:
    {text}

    Evaluate:
    - Seniority (0-3)
    - Domain fit (0-3)
    - Strategy/execution (0-2)
    - Scope EU/remote (0-2)

    Return:
    TOTAL: X/10
    REASON: short explanation
    """

    res = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    out = res.choices[0].message.content

    try:
        score = int(out.split("TOTAL:")[1].split("/")[0])
    except:
        score = 5

    return score, out

# === APPLICATION ===
def generate_application(job):
    prompt = f"""
    Write a sharp 5-line executive application.

    Candidate:
    {USER_PROFILE}

    Job:
    {job['title']}
    """

    res = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    return res.choices[0].message.content

# === SAVE ===
def save_job(job):
    conn = sqlite3.connect("jobs.db")
    c = conn.cursor()

    c.execute(
        "INSERT INTO jobs VALUES (?, ?, ?, ?)",
        (job["title"], job["link"], job["score"], "New")
    )

    conn.commit()
    conn.close()

# === EMAIL ===
def send_email(jobs):
    jobs = sorted(jobs, key=lambda x: x["score"], reverse=True)

    top5 = jobs[:5]
    rest = jobs[5:20]

    body = "🔥 TOP 5 MATCHES\n\n"

    for j in top5:
        app = generate_application(j)

        body += f"{j['title']} ({j['score']})\n{j['link']}\n"
        body += f"{j['reason']}\n\n"
        body += f"Suggested application:\n{app}\n\n"

    body += "\n---\n\nOther matches:\n\n"

    for j in rest:
        body += f"{j['title']} ({j['score']})\n{j['link']}\n\n"

    msg = f"Subject: 🎯 Job Matches {datetime.today().date()}\n\n{body}"

    with smtplib.SMTP("smtp.office365.com", 587) as server:
        server.starttls()
        server.login(EMAIL, PASSWORD)
        server.sendmail(EMAIL, EMAIL, msg)

# === MAIN ===
def run():
    init_db()
    jobs = fetch_jobs()

    enriched = []

    for j in jobs:
        score, reason = ai_score(j)

        if score >= 6:
            j["score"] = score
            j["reason"] = reason

            save_job(j)
            enriched.append(j)

    send_email(enriched)

run()
