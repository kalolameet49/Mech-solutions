import subprocess
import uuid
import os

def run_deepnest(input_file):
    job_id = str(uuid.uuid4())
    output_file = f"/tmp/{job_id}_out.svg"

    try:
        subprocess.run([
            "deepnest",
            "--input", input_file,
            "--output", output_file,
            "--spacing", "3"
        ], check=True)

        return output_file, None

    except Exception as e:
        return None, str(e)
