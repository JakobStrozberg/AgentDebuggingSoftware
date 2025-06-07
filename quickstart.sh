#!/bin/bash

echo "🔍 CellSight Quick Start"
echo "========================"
echo ""

# Check Python version
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python version: $python_version"

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r cellsight/requirements.txt

# Install CellSight in development mode
echo ""
echo "Installing CellSight..."
pip install -e .

echo ""
echo "✅ Setup complete!"
echo ""
echo "To get started:"
echo ""
echo "1. Start the mock API server:"
echo "   cellsight start-api"
echo ""
echo "2. In another terminal, run a demo:"
echo "   python cellsight/demo.py"
echo ""
echo "3. Or try the CLI:"
echo "   cellsight run \"What's the weather in London?\" --mock"
echo ""
echo "4. Or launch the web dashboard:"
echo "   streamlit run cellsight/dashboard/app.py"
echo ""
echo "Happy debugging! 🚀" 