#!/bin/bash
# Launch Ardi Market Dashboard locally
cd ~/Library/Mobile\ Documents/com~apple~CloudDocs/_ARDI

# Check if streamlit is installed
if ! command -v streamlit &>/dev/null; then
    echo "Streamlit not found. Installing..."
    pip3 install streamlit yfinance pandas requests plotly pytz
fi

LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "unknown")
echo ""
echo "Starting Ardi Market Dashboard..."
echo "================================="
echo "  Mac:    http://localhost:8501"
echo "  iPhone: http://${LOCAL_IP}:8501  (must be on home WiFi)"
echo ""
streamlit run MISC/Stock_Market/dashboard.py \
  --server.port 8501 \
  --server.address 0.0.0.0 \
  --browser.gatherUsageStats false
