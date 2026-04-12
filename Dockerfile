FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y make && rm -rf /var/lib/apt/lists/*

COPY . .
RUN pip install --no-cache-dir -e .

CMD ["make", "all"]
