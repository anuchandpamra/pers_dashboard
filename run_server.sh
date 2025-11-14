#!/bin/bash
# Quick setup and run script for Product Entity Resolution Web Interface

echo "Starting Product Entity Resolution Web Interface..."

# Check if we're in the right directory
if [ ! -f "manage.py" ]; then
    echo "Error: Please run this script from the pers_dashboard directory"
    exit 1
fi

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running database migrations..."
python manage.py migrate

# Get port from command line argument or use default 8000
PORT="${1:-8000}"

echo "Starting Django development server..."
echo "Web interface will be available at: http://127.0.0.1:$PORT"
echo "Also accessible from network at: http://<your-ip>:$PORT"
echo "Press Ctrl+C to stop the server"
echo ""

# Set environment variables for the web interface
export PER_RESULTS_DIR="$(dirname "$(pwd)")"
export PYTHONPATH="$(dirname "$(pwd)"):$PYTHONPATH"

python manage.py runserver 0.0.0.0:$PORT
