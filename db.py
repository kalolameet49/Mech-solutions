from sqlalchemy import create_engine, Column, String, Float
from sqlalchemy.orm import declarative_base, sessionmaker
import uuid

engine = create_engine("sqlite:///jobs.db")
Session = sessionmaker(bind=engine)
Base = declarative_base()

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True)
    status = Column(String)
    width = Column(Float)
    height = Column(Float)
    file_path = Column(String)

Base.metadata.create_all(engine)

def create_job():
    session = Session()
    job_id = str(uuid.uuid4())

    job = Job(id=job_id, status="PENDING")
    session.add(job)
    session.commit()
    session.close()

    return job_id

def update_job(job_id, status, W=None, H=None, file_path=None):
    session = Session()
    job = session.get(Job, job_id)

    job.status = status
    job.width = W
    job.height = H
    job.file_path = file_path

    session.commit()
    session.close()

def get_jobs():
    session = Session()
    jobs = session.query(Job).all()
    session.close()
    return jobs
