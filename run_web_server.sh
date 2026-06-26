#!/bin/bash
echo "==================================================="
echo "🚀 Starting Liquor Bond Automation Web Server..."
echo "==================================================="

# Get the script's directory and navigate to it
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Activate virtual environment if it exists
if [ -d "env" ]; then
    echo "📦 Activating virtual environment 'env'..."
    source env/bin/activate
elif [ -d "venv" ]; then
    echo "📦 Activating virtual environment 'venv'..."
    source venv/bin/activate
else
    echo "⚠️ Virtual environment not found in root. Using system global Python..."
fi

echo "⏳ Installing/Verifying dependencies (FastAPI, Uvicorn, WebSockets)..."
python3 -m pip install --upgrade pip
pip install -r requirements.txt

# Discover Local IP on macOS/Linux
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || ipconfig getifaddr en2 2>/dev/null || hostname -I | awk '{print $1}')

echo ""
echo "==================================================="
echo "🌐 Web Dashboard is ready!"
echo ""
echo "👉 To access from THIS PC: http://localhost:8000"
if [ ! -z "$LOCAL_IP" ]; then
    echo "👉 To access from OTHER PCs on local network: http://$LOCAL_IP:8000"
fi
echo "==================================================="
echo ""

python3 app.py
