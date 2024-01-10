FROM python:3.9-slim

EXPOSE 8000

COPY . /app/

RUN python3 -m pip install -r /app/requirements.txt

WORKDIR /app

CMD [ "uvicorn", "app:app", "--host", "0.0.0.0" ]

