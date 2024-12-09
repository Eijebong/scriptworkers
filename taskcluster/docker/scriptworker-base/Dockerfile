FROM alpine:latest

RUN apk update && apk add curl unzip python3 py3-setuptools py3-pip bash
RUN curl -qSsL https://github.com/mozilla-releng/scriptworker/archive/refs/tags/60.5.0.zip -o /tmp/scriptworker.zip && \
    cd /tmp && \
    unzip /tmp/scriptworker.zip && \
    mv /tmp/scriptworker-60.5.0 /tmp/scriptworker && \
    cd /tmp/scriptworker && \
    pip install --break-system-packages . && \
    rm /tmp/scriptworker.zip && \
    rm -Rf /tmp/scriptworker

RUN adduser -D worker
USER worker
WORKDIR /home/worker

# %include scriptrunner.py
COPY /topsrcdir/scriptrunner.py /home/worker/
