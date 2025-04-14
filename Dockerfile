#Imagem Python
FROM python:3.13-slim

#Pasta de Trabalho
WORKDIR /app

#Dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#Aplicação
COPY . .
EXPOSE 5000
CMD ["python", "app.py"]


