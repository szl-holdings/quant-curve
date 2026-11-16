FROM python:3.15-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928

WORKDIR /srv
COPY requirements.txt .
# requirements.txt is hash-locked (compiled from requirements.in): pip refuses
# any distribution whose sha256 is not listed there.
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY app ./app
COPY site ./site

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
