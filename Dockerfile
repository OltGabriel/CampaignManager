# Imagine de bază oficială Python
FROM python:3.11-slim

# Setează directorul de lucru în container
WORKDIR /app

# Copiază fișierele în container
COPY app/ /app/

# Instalează dependențele
RUN pip install --no-cache-dir -r requirements.txt

# Expune portul 8000
EXPOSE 8000

# Comandă default de rulare
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
