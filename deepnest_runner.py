import subprocess
import uuid

def run_deepnest(input_file):
    output_file = f"/tmp/{uuid.uuid4()}.svg"

    try:
        subprocess.run([
            "deepnest-cli",
            "--input", input_file,
            "--output", output_file,
            "--spacing", "3"
        ], check=True)

        return output_file, None

    except Exception as e:
        return None, str(e)
