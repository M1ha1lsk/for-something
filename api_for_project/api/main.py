from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi import HTTPException
from pydantic import BaseModel
import logging
import json
import subprocess
from kafka_producer import send_purchase

app = FastAPI()

class Purchase(BaseModel):
    user_id: int
    product_id: str
    quantity: int

@app.post("/init-products")
def init_products():
    result = subprocess.run(
        [
            "docker", "exec", "spark-master",
            "spark-submit",
            "--packages", "org.apache.iceberg:iceberg-spark-runtime-3.4_2.12:1.4.3",
            "/app/spark_jobs/init_products_table.py"
        ],
        capture_output=True,
        text=True
    )

    return {
        "status": "ok" if result.returncode == 0 else "error",
        "stdout": result.stdout,
        "stderr": result.stderr
    }

@app.get("/products")
def get_products():
    result = subprocess.run([
        "docker", "exec", "spark-master",
        "spark-submit",
        "--packages", "org.apache.iceberg:iceberg-spark-runtime-3.4_2.12:1.4.3",
        "/app/spark_jobs/list_products.py"
    ], capture_output=True, text=True)

    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail=f"Spark job failed:\n{result.stderr}"
        )

    lines = result.stdout.splitlines()
    json_lines = [line for line in lines if line.strip().startswith(('[', '{'))]

    if not json_lines:
        raise HTTPException(
            status_code=500,
            detail="No valid JSON output from Spark job."
        )

    json_str = "\n".join(json_lines)

    try:
        output = json.loads(json_str)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Invalid JSON output from Spark job."
        )

    return output

@app.post("/purchase")
def create_purchase(p: Purchase):
    send_purchase(p.dict())
    return {"status": "ok"}
