from fastapi import FastAPI, UploadFile, File
from fastapi.responses import FileResponse
import tempfile
import os
from deepnest_runner import run_deepnest

app = FastAPI()

@app.post("/nest")
async def nest(file: UploadFile = File(...)):
    # Save uploaded SVG
    with tempfile.NamedTemporaryFile(delete=False, suffix=".svg") as tmp:
        tmp.write(await file.read())
        input_path = tmp.name

    output_path, error = run_deepnest(input_path)

    if error:
        return {"error": error}

    return FileResponse(output_path, filename="nested.svg")
