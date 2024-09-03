#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Update pip
python -m pip install --upgrade pip

# Install wheel
pip install wheel

# Install the requirements
pip install -r requirements.txt