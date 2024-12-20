FROM python:3.12-slim

RUN apt-get update && apt-get install -y git

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app /app
COPY run.sh .

CMD ["/bin/sh", "./run.sh"]
