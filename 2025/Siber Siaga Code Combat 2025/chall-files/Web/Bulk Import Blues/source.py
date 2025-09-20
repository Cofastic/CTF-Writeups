
import yaml
import os
import sys
from flask import Flask, request, render_template_string, jsonify
import subprocess
import tempfile

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Acme Inventory Manager</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 30px;
        }
        .actions {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-bottom: 20px;
            justify-content: center;
        }
        .form-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #555;
        }
        textarea {
            width: 100%;
            height: 200px;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 14px;
        }
        button {
            background-color: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 16px;
        }
        button:hover {
            background-color: #0056b3;
        }
        .btn-secondary {
            background-color: #6c757d;
        }
        .btn-secondary:hover {
            background-color: #545b62;
        }
        .inline {
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 5px;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
        }
        .success {
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }
        .error {
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }
        .info {
            background-color: #d1ecf1;
            border: 1px solid #bee5eb;
            color: #0c5460;
        }
        .warning {
            background-color: #fff3cd;
            border: 1px solid #ffeaa7;
            color: #856404;
            margin-bottom: 20px;
            padding: 15px;
            border-radius: 5px;
        }
        .grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 20px;
        }
        @media (min-width: 900px) {
            .grid {
                grid-template-columns: 1fr 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Acme Inventory Manager</h1>
        <div class="actions">
            <button type="button" id="viewProductsBtn" class="btn-secondary">View Products</button>
            <a href="/inventory" class="btn-secondary" style="text-decoration:none; padding: 10px 16px; border-radius: 5px;">Check Inventory</a>
        </div>

        <div class="grid">
            <form method="POST" action="/process">
                <div class="form-group">
                    <label for="yaml_content">Bulk Inventory Config:</label>
                    <textarea name="yaml_content" id="yaml_content" placeholder="Paste your inventory configuration..."># Example inventory config
inventory:
  - sku: WID-1001
    name: Standard Widget
    price: 19.99
    in_stock: true
  - sku: GAD-2002
    name: Premium Gadget
    price: 59.50
    in_stock: on
settings:
  currency: USD
  tax_rate: 0.07</textarea>
                </div>
                
                <button type="submit">Process Import</button>
            </form>

            <div>
                <pre id="apiResult" class="result info" style="display:none;"></pre>
            </div>
        </div>
        
        {% if result %}
        <div class="result {{ result_type }}">
            {{ result }}
        </div>
        {% endif %}
    </div>
</body>
</html>
<script>
(function(){
  const apiResult = document.getElementById('apiResult');
  const show = (obj) => {
    apiResult.style.display = 'block';
    apiResult.textContent = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
  };

  const viewBtn = document.getElementById('viewProductsBtn');
  if (viewBtn) {
    viewBtn.addEventListener('click', async () => {
      try {
        const res = await fetch('/products');
        const data = await res.json();
        show(data);
      } catch (e) {
        show('Failed to load products');
      }
    });
  }
})();
</script>
"""

INVENTORY_TEMPLATE = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Inventory Lookup • Acme Inventory Manager</title>
    <style>
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background:#f5f5f5; }
        .container { background: #fff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { text-align:center; margin:0 0 8px; }
        p { text-align:center; color:#666; margin-top:0; }
        .row { display:flex; gap:10px; justify-content:center; margin: 20px 0; }
        input { height: 40px; padding: 0 12px; border: 1px solid #ddd; border-radius: 6px; min-width: 260px; }
        button, a.btn { background:#007bff; color:#fff; border:none; border-radius:6px; padding: 10px 16px; cursor:pointer; text-decoration:none; display:inline-block; }
        button:hover, a.btn:hover { background:#0056b3; }
        pre { background:#eef6ff; border:1px solid #cfe2ff; color:#0c2d6b; padding:16px; border-radius:6px; white-space:pre-wrap; font-family:'Courier New', monospace; }
        .topnav { text-align:center; margin-bottom: 10px; }
        .topnav a { color:#007bff; text-decoration:none; }
    </style>
  </head>
  <body>
    <div class=\"container\">
      <div class=\"topnav\"><a href=\"/\">← Back to Import</a></div>
      <h1>Inventory Lookup</h1>
      <p>Enter a product SKU to view current details</p>
      <div class=\"row\">
        <input id=\"invSku\" placeholder=\"e.g., WID-1001\" />
        <button id=\"goBtn\">View</button>
      </div>
      <pre id=\"invResult\" style=\"display:none;\"></pre>
    </div>
    <script>
    (function(){
      const out = document.getElementById('invResult');
      const show = (obj) => { out.style.display='block'; out.textContent = typeof obj==='string' ? obj : JSON.stringify(obj, null, 2); };
      const go = async () => {
        const sku = (document.getElementById('invSku').value || '').trim();
        if (!sku) { show('Please enter a SKU'); return; }
        try {
          const res = await fetch('/inventory/' + encodeURIComponent(sku));
          const data = await res.json();
          show(data);
        } catch(e) { show('Failed to load'); }
      };
      document.getElementById('goBtn').addEventListener('click', go);
      document.getElementById('invSku').addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); go(); }});
    })();
    </script>
  </body>
</html>
"""

def yaml_load(yaml_content):
    try:
        data = yaml.load(yaml_content, Loader=yaml.Loader)
        return data, None
    except Exception as e:
        return None, str(e)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/inventory')
def inventory_page():
    return render_template_string(INVENTORY_TEMPLATE)

@app.route('/process', methods=['POST'])
def process_yaml():
    yaml_content = request.form.get('yaml_content')

    if not yaml_content.strip():
        return render_template_string(HTML_TEMPLATE,
                                    result="Error: No YAML content provided",
                                    result_type="error")

    result_data, error = yaml_load(yaml_content)
    if error:
        return render_template_string(HTML_TEMPLATE,
                                    result=f"Error processing YAML: {error}",
                                    result_type="error")

    result_text = "Import processed successfully:\n\n"
    result_text += yaml.dump(result_data, default_flow_style=False)

    return render_template_string(HTML_TEMPLATE,
                                result=result_text,
                                result_type="success")

@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy"})

CATALOG = [
    {"sku": "WID-1001", "name": "Standard Widget", "price": 19.99, "in_stock": True},
    {"sku": "GAD-2002", "name": "Premium Gadget", "price": 59.50, "in_stock": True},
    {"sku": "ACC-3003", "name": "Accessory Pack", "price": 9.99, "in_stock": False},
]

@app.route('/products')
def products():
    return jsonify({"items": CATALOG, "count": len(CATALOG)})

@app.route('/inventory/<sku>')
def inventory_detail(sku: str):
    for item in CATALOG:
        if item["sku"].lower() == sku.lower():
            return jsonify(item)
    return jsonify({"error": "SKU not found"}), 404

@app.route('/debug')
def debug_info():
    return jsonify({
        "python_version": sys.version.split(" ")[0],
        "yaml_version": yaml.__version__,
        "working_directory": os.getcwd()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
