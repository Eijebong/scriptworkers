FROM alpine:latest

RUN apk update && apk add curl unzip bash uv

RUN adduser -D worker
USER worker
WORKDIR /home/worker

RUN uv venv --python=3.13
RUN uv pip install scriptworker

# %include scriptrunner.py
COPY /topsrcdir/scriptrunner.py /home/worker/
