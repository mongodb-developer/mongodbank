#!/bin/bash
set -e

# Update pip and install wheel
pip install --upgrade pip wheel

# Install psycopg2-binary separately
pip install psycopg2-binary==2.9.5 --no-binary psycopg2-binary

# Install the rest of the requirements
pip install -r requirements.txt