FROM python:3.14

COPY requirements.txt .

RUN pip install --break-system-packages -r requirements.txt

COPY . /NewTests

WORKDIR /NewTests