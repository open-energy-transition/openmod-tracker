# SPDX-FileCopyrightText: openmod-tracker contributors listed in AUTHORS.md
#
# SPDX-License-Identifier: CC0-1.0

FROM python:3.13-slim

COPY . ./

RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r website/requirements.txt pytest --root-user-action=ignore

RUN pytest tests/test_app.py

EXPOSE 8080

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health

CMD ["streamlit", "run", "website/⚡️_Tool_Repository_Metrics.py", "--server.port=8080", "--server.address=0.0.0.0"]
