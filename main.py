import os
import uuid
import logging
import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
import aiofiles
from crewai import Crew  # no Process import
from agents import doctor, verifier, nutritionist, exercise_specialist
from task import verification, help_patients, nutrition_analysis, exercise_planning

# Configuration
data_dir = os.getenv("DATA_DIR", "data")
output_dir = os.getenv("OUTPUT_DIR", "output")

# Ensure directories exist
def ensure_directories():
    os.makedirs(data_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifespan context for setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create required directories once before serving
    await asyncio.to_thread(ensure_directories)
    yield

# Initialize FastAPI with lifespan
app = FastAPI(
    title="Blood Test Report Analyser",
    lifespan=lifespan
)

# Helper: create a crew
def make_crew(agents, tasks, parallel=False):
    return Crew(
        agents=agents,
        tasks=tasks,
        verbose=True
    )

# Helper: run crew offloaded to thread
def kickoff_threaded(crew, payload: dict):
    return crew.kickoff(payload)

# Core runners
def run_crew(query: str, file_path: str):
    logger.info(f"Running full crew on {file_path}")
    crew = make_crew(
        agents=[verifier, doctor, nutritionist, exercise_specialist],
        tasks=[verification, help_patients, nutrition_analysis, exercise_planning],
        parallel=True
    )
    return asyncio.get_event_loop().run_in_executor(
        None, kickoff_threaded, crew, {"query": query, "file_path": file_path}
    )

def run_verification_only(query: str, file_path: str):
    logger.info(f"Running verification only on {file_path}")
    crew = make_crew([verifier], [verification])
    return asyncio.get_event_loop().run_in_executor(
        None, kickoff_threaded, crew, {"query": query, "file_path": file_path}
    )

def run_medical_analysis_only(query: str, file_path: str):
    logger.info(f"Running medical analysis on {file_path}")
    crew = make_crew([verifier, doctor], [verification, help_patients])
    return asyncio.get_event_loop().run_in_executor(
        None, kickoff_threaded, crew, {"query": query, "file_path": file_path}
    )

# Utility: save result
async def save_result(file_id: str, result: dict):
    output_path = os.path.join(output_dir, f"result_{file_id}.json")
    async with aiofiles.open(output_path, 'w') as f:
        await f.write(json.dumps(result, indent=2))
    return output_path

# Endpoints
@app.get("/")
async def root():
    return {"message": "Blood Test Report Analyser API is running"}

async def process_file_and_run(
    file: UploadFile,
    query: str,
    runner,
    background_tasks: BackgroundTasks,
    default_query: str
):
    file_id = str(uuid.uuid4())
    filename = file.filename or "uploaded_file.pdf"
    ext = os.path.splitext(filename)[1] or ".pdf"
    temp_path = os.path.join(data_dir, f"upload_{file_id}{ext}")

    # Save upload asynchronously
    async with aiofiles.open(temp_path, 'wb') as out_file:
        content = await file.read()
        if len(content) > 10_000_000:
            raise HTTPException(status_code=413, detail="File too large")
        await out_file.write(content)

    if not query:
        query = default_query
    query = query.strip()

    # Run the specified crew
    try:
        response = await runner(query, temp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Build standardized result object
    result_obj = {
        "file_id": file_id,
        "original_filename": file.filename,
        "query": query,
        "analysis": repr(response)
    }

    # Save result in background
    background_tasks.add_task(save_result, file_id, result_obj)

    # Cleanup upload
    os.remove(temp_path)

    return result_obj

@app.post("/analyze")
async def analyze(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    query: str = Form(default="Provide a comprehensive analysis of my blood test report including medical interpretation, nutritional recommendations, and exercise planning.")
):
    return await process_file_and_run(
        file,
        query,
        run_crew,
        background_tasks,
        default_query="Provide a comprehensive analysis of my blood test report including medical interpretation, nutritional recommendations, and exercise planning."
    )

@app.post("/verify")
async def verify(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    query: str = Form(default="Verify if this document is a valid blood test report and extract key biomarkers.")
):
    return await process_file_and_run(
        file,
        query,
        run_verification_only,
        background_tasks,
        default_query="Verify if this document is a valid blood test report and extract key biomarkers."
    )

@app.post("/medical-analysis")
async def medical_analysis(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    query: str = Form(default="Provide medical interpretation of my blood test results.")
):
    return await process_file_and_run(
        file,
        query,
        run_medical_analysis_only,
        background_tasks,
        default_query="Provide medical interpretation of my blood test results."
    )

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Blood Test Report Analyser",
        "version": "1.0.0",
        "endpoints": ["/analyze", "/verify", "/medical-analysis"],
        "data_dir": data_dir,
        "output_dir": output_dir
    }

if __name__ == "__main__":
    import uvicorn
    ensure_directories()
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)

