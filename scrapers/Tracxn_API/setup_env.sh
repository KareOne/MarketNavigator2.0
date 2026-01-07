#!/bin/bash

# Setup script for Tracxn API and Worker Agent dependencies

echo "🚀 Setting up Tracxn Worker Environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install API dependencies
if [ -f "requirements.txt" ]; then
    echo "📦 Installing Tracxn API dependencies..."
    pip install -r requirements.txt
else
    echo "⚠️ Tracxn API requirements.txt not found!"
fi

# Install Worker Agent dependencies
if [ -f "worker_agent/requirements.txt" ]; then
    echo "📦 Installing Worker Agent dependencies..."
    pip install -r worker_agent/requirements.txt
else
    echo "⚠️ Worker Agent requirements.txt not found!"
fi

echo "✅ Setup complete! Virtual environment is ready in ./venv"
echo "To activate manually: source venv/bin/activate"
