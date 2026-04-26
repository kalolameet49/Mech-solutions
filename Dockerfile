FROM python:3.11-slim

WORKDIR /app

# Copy project
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Start Streamlit using Railway's PORT variable
CMD streamlit run main.py --server.port=${PORT:-8501} --server.address=0.0.0.0
