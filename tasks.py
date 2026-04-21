from celery_app import celery
from shapely.geometry import Polygon
from shapely.ops import unary_union
import json, os
from db import update_job

OUTPUT_DIR = "files"

@celery.task(bind=True)
def run_nesting(self, job_id, polygons_json):
    try:
        polygons = [Polygon(p) for p in polygons_json]

        union = unary_union(polygons)
        _, _, maxx, maxy = union.bounds

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        file_path = f"{OUTPUT_DIR}/{job_id}.json"

        with open(file_path, "w") as f:
            json.dump(polygons_json, f)

        update_job(job_id, "SUCCESS", maxx, maxy, file_path)

        return {"W": maxx, "H": maxy}

    except Exception as e:
        update_job(job_id, "FAILED")
        raise e
