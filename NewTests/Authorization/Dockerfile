FROM python:3.14

RUN pip install uvicorn==0.52.4
RUN pip install fastapi==0.141.1

RUN mkdir /auth-service
COPY *.py /auth-service

WORKDIR /auth-service
ENTRYPOINT [ "uvicorn", "auth_service:app", "--host", "0.0.0.0", "--port", "8020"]

