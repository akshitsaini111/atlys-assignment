from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Import models first to ensure they're registered
from app.models.user import User
from app.models.task import Task, TaskAssignment, TaskDependency, Tag, TaskHistory

# Import database
from app.db.base import engine, Base

# Import routers
from app.api.v1 import auth, tasks

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    debug=settings.DEBUG,
    description="Task Management API with authentication, filtering, and analytics",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")

@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "Task Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc"
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "task-management-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)