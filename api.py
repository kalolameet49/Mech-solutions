from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import uuid
import os
from deepnest_runner import run_deepnest

app = FastAPI()

WORK_DIR = "jobs"
os.makedirs(WORK_DIR, exist_ok=True)


@app.post("/nest")
async def nest(file: UploadFile = File(...)):
    job_id = str(uuid.uuid4())

    input_path = f"{WORK_DIR}/{job_id}.svg"
    output_path = f"{WORK_DIR}/{job_id}_out.svg"

    with open(input_path, "wb") as f:
        f.write(await file.read())

    result = run_deepnest(input_path, output_path)

    if not result:
        return {"error": "Deepnest failed"}

    return FileResponse(output_path, filename="nested.svg")
