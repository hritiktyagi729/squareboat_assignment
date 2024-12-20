from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session
from typing import List
from smtplib import SMTP

# Database Configuration (To be configure for mysql)
DATABASE_URL = "mysql+mysqlconnector://root:ritik@localhost/job_api"
Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# OAuth2 Token Authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# FastAPI App
app = FastAPI()

# Dependency to Get Database Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False)
    password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)

class Job(Base):
    __tablename__ = "jobs"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    recruiter_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    recruiter = relationship("User", back_populates="jobs")

class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, index=True)
    candidate_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    job = relationship("Job")

User.jobs = relationship("Job", back_populates="recruiter")
User.applications = relationship("Application", back_populates="candidate")
Application.candidate = relationship("User", back_populates="applications")

# Pydantic Models
class SignupRequest(BaseModel):
    email: str
    password: str
    role: str

class JobPostRequest(BaseModel):
    title: str
    description: str

class JobResponse(BaseModel):
    id: int
    title: str
    description: str

class ApplyRequest(BaseModel):
    job_id: int

# Root Endpoint
@app.get("/")
def default():
    return {"message": "welcome home"}

# User Signup
@app.post("/signup")
def signup(user: SignupRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="User already exists")

    new_user = User(email=user.email, password=user.password, role=user.role)
    db.add(new_user)
    db.commit()
    return {"message": "User created successfully"}

# User Login (Token Generation)
@app.post("/auth/token")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username, User.password == form_data.password).first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")
    return {"access_token": user.email, "token_type": "bearer"}

# List All Jobs
@app.get("/jobs", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    return db.query(Job).all()

# Post a Job
@app.post("/jobs")
def post_job(job: JobPostRequest, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    user = db.query(User).filter(User.email == token).first()
    if not user or user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Not authorized")

    new_job = Job(title=job.title, description=job.description, recruiter_id=user.id)
    db.add(new_job)
    db.commit()
    return {"message": "Job posted successfully"}

# Utility Function: Send Email
def send_email(to_email: str, subject: str, body: str):
    try:
        with SMTP("smtp.example.com") as smtp:
            smtp.login("xyz@gmail.com", "pass@123")
            smtp.sendmail("xyz@gmail.com", to_email, f"Subject: {subject}\n\n{body}")
    except Exception as e:
        print(f"Error sending email: {e}")

# Apply to a Job
@app.post("/applications")
def apply_to_job(request: ApplyRequest, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    user = db.query(User).filter(User.email == token).first()
    if not user or user.role != "candidate":
        raise HTTPException(status_code=403, detail="Not authorized")

    job = db.query(Job).filter(Job.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    application = Application(candidate_id=user.id, job_id=job.id)
    db.add(application)
    db.commit()

    send_email(job.recruiter.email, "Job Application Received", f"{user.email} applied for your job '{job.title}'")
    send_email(user.email, "Application Submitted", f"You applied for the job '{job.title}'")

    return {"message": "Applied successfully"}

# List Applications for Candidates
@app.get("/applications")
def list_applications(db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    user = db.query(User).filter(User.email == token).first()
    if not user or user.role != "candidate":
        raise HTTPException(status_code=403, detail="Not authorized")
    return [application.job for application in user.applications]

# List Applicants for a Job
@app.get("/applicants")
def list_applicants(job_id: int, db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)):
    user = db.query(User).filter(User.email == token).first()
    if not user or user.role != "recruiter":
        raise HTTPException(status_code=403, detail="Not authorized")

    job = db.query(Job).filter(Job.id == job_id, Job.recruiter_id == user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return [application.candidate.email for application in job.applications]

# User Logout
@app.post("/auth/logout")
def logout():
    return {"message": "Logged out successfully"}

# Initialize Database Tables
Base.metadata.create_all(bind=engine)
