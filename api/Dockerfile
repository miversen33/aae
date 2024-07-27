FROM python:3.11-alpine
WORKDIR /app
ADD ./requirements.txt /app/requirements.txt
RUN python3 -m pip install -r /app/requirements.txt

ADD . /app


CMD [ "python3", "app.py" ]
