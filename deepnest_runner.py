import subprocess

def run_deepnest(input_path, output_path):
    try:
        subprocess.run([
            "deepnest",
            "--input", input_path,
            "--output", output_path,
            "--spacing", "3"
        ], check=True)

        return True
    except Exception as e:
        print(e)
        return False
