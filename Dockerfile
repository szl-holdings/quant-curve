FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8

WORKDIR /srv
COPY requirements.txt .
# requirements.txt is hash-locked (compiled from requirements.in): pip refuses
# any distribution whose sha256 is not listed there.
RUN pip install --no-cache-dir --require-hashes -r requirements.txt
COPY app ./app
COPY site ./site

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
