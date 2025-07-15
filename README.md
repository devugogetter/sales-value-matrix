# Sales Value Matrix Dashboard

Strategic analysis tool for agency value and engagement visualization.

## How to Use

### Run Locally
1. Install Python 3.7+
2. Clone this repository: `git clone https://github.com/devugogetter/sales-value-matrix.git`
3. Install requirements: `pip install -r requirements.txt`
4. Run the app: `python sales_value_matrix.py`
5. Open http://localhost:8050 in your browser

### On Google Colab
# Install required packages
!pip install -q dash dash_bootstrap_components pandas numpy plotly chardet

# Download the app code
!wget -q https://github.com/devugogetter/sales-value-matrix/main/sales_value_matrix.py

# Run the app in background
`import threading`<br>
`from sales_value_matrix import app, server`<br>

`def run_app():`<br>
    `app.run_server(host='0.0.0.0', port=8050, debug=False)`<br>

`thread = threading.Thread(target=run_app)`<br>
`thread.daemon = True`<br>
`thread.start()`<br>
