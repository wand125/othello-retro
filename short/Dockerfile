ARG BASE_IMAGE
FROM ${BASE_IMAGE}
COPY --chown=app:app ui/short.html ui/short.css ui/short.js /app/ui/
COPY --chown=app:app install_short.py /tmp/install_short.py
RUN python /tmp/install_short.py && rm /tmp/install_short.py
