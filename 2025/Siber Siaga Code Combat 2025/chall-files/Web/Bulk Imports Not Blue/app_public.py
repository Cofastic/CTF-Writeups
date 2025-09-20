#!/usr/bin/env python3
import yaml
import json
import re
import os
import sys
from flask import Flask, request, render_template_string, jsonify, make_response
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
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; margin-bottom: 30px; }
        .actions { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 20px; justify-content: center; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #555; }
        textarea { width: 100%; height: 200px; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-family: 'Courier New', monospace; font-size: 14px; }
        button { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background-color: #0056b3; }
        .btn-secondary { background-color: #6c757d; }
        .btn-secondary:hover { background-color: #545b62; }
        .inline { display: inline-flex; align-items: center; gap: 8px; }
        .result { margin-top: 20px; padding: 15px; border-radius: 5px; white-space: pre-wrap; font-family: 'Courier New', monospace; }
        .success { background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; }
        .error { background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }
        .info { background-color: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; }
        .warning { background-color: #fff3cd; border: 1px solid #ffeaa7; color: #856404; margin-bottom: 20px; padding: 15px; border-radius: 5px; }
        .grid { display: grid; grid-template-columns: 1fr; gap: 20px; }
        @media (min-width: 900px) { .grid { grid-template-columns: 1fr 1fr; } }
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
  const show = (obj) => { apiResult.style.display = 'block'; apiResult.textContent = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2); };
  const viewBtn = document.getElementById('viewProductsBtn');
  if (viewBtn) {
    viewBtn.addEventListener('click', async () => {
      try { const res = await fetch('/products'); const data = await res.json(); show(data); } catch (e) { show('Failed to load products'); }
    });
  }
})();
</script>
"""

PORTAL_TEMPLATE = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Acme Portal</title>
  <style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background:#f5f5f5; }
    .container { background:#fff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    h1 { text-align:center; margin:0 0 10px; }
    p { color:#666; text-align:center; margin-top:0; }
    textarea { width:100%; height:180px; padding:10px; border:1px solid #ddd; border-radius:6px; font-family:'Courier New', monospace; }
    button, a.btn { background:#007bff; color:#fff; border:none; border-radius:6px; padding: 10px 16px; cursor:pointer; text-decoration:none; display:inline-block; }
    button:hover, a.btn:hover { background:#0056b3; }
    .row { display:flex; gap:10px; justify-content:center; align-items:center; margin-top: 15px; }
    .msg { margin-top:15px; padding:12px; border-radius:6px; white-space:pre-wrap; font-family:'Courier New', monospace; }
    .warn { background:#fff3cd; border:1px solid #ffe69c; color:#664d03; }
    .ok { background:#d1e7dd; border:1px solid #a3cfbb; color:#0f5132; }
  </style>
</head>
<body>
  <div class=\"container\">
    <h1>Acme Staff Portal</h1>
    <p>Update UI preferences and access permissions</p>
    <form method=\"POST\" action=\"/portal/config\">\n      <label for=\"json\"><strong>Portal Preferences</strong></label>\n      <textarea id=\"json\" name=\"json\" placeholder='{"theme":"dark"}'>{"theme":"light"}</textarea>\n      <div class=\"row\">\n        <button type=\"submit\">Apply Settings</button>\n        <a class=\"btn\" href=\"/\">Inventory Import</a>\n      </div>\n    </form>
    {% if portal_message %}
      <div class=\"msg {{ portal_class }}\">{{ portal_message }}</div>
    {% endif %}
    <div class=\"row\" style=\"margin-top:20px;\">
      {% if unlocked %}
        <a class=\"btn\" href=\"/challenge\">Enter Challenge Area →</a>
      {% else %}
        <div class=\"msg warn\">Challenge Area Locked</div>
      {% endif %}
    </div>
  </div>
</body>
</html>
"""

class PortalDefaults:
    challenge_unlocked = False
    theme = "light"
    role = "user"

PORTAL_PREFS = {"theme": PortalDefaults.theme}

class PortalState:
    def __init__(self) -> None:
        self.role = PortalDefaults.role
        self.theme = PortalDefaults.theme
        self.unlock = False
        self.allow_meta = False

PORTAL_STATE = PortalState()

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
        try { const res = await fetch('/inventory/' + encodeURIComponent(sku)); const data = await res.json(); show(data); } catch(e) { show('Failed to load'); }
      };
      document.getElementById('goBtn').addEventListener('click', go);
      document.getElementById('invSku').addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); go(); }});
    })();
    </script>
  </body>
</html>
"""

SEARCH_TEMPLATE = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Search • Acme</title>
  <style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background:#f5f5f5; }
    .container { background:#fff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    input { height: 38px; padding: 0 10px; border:1px solid #ddd; border-radius:6px; min-width: 260px; }
    button { background:#007bff; color:#fff; border:none; border-radius:6px; padding:10px 16px; cursor:pointer; }
  </style>
</head>
<body>
  <div class=\"container\">
    <h1>Site Search</h1>
    <form method=\"GET\" action=\"/search\" class=\"row\">
      <input name=\"q\" value=\"{{ query_raw }}\" placeholder=\"Search products...\" />
      <button type=\"submit\">Search</button>
    </form>
    <h3>Results for:</h3>
    <div id=\"result\">{{ query|safe }}</div>
  </div>
</body>
</html>
"""

FEEDBACK_TEMPLATE = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Feedback • Acme</title>
  <style>
    body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background:#f5f5f5; }
    .container { background:#fff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
    textarea { width:100%; height:160px; padding:10px; border:1px solid #ddd; border-radius:6px; font-family:'Courier New', monospace; }
    button { background:#007bff; color:#fff; border:none; border-radius:6px; padding:10px 16px; cursor:pointer; }
    .msg { margin-top:12px; padding:12px; background:#d1e7dd; border:1px solid #a3cfbb; color:#0f5132; border-radius:6px; }
  </style>
</head>
<body>
  <div class=\"container\">
    <h1>Feedback</h1>
    <form method=\"POST\" action=\"/feedback\"> 
      <textarea name=\"message\" placeholder=\"Tell us what you think...\"></textarea>
      <div style=\"margin-top:10px;\"><button type=\"submit\">Submit</button></div>
    </form>
    {% if saved %}
      <div class=\"msg\">Thanks! We saved your feedback ({{ size }} chars).</div>
    {% endif %}
  </div>
</body>
</html>
"""


def yaml_load(yaml_content, version="1.2"):
    try:
        if version == "1.1":
            yaml_content = yaml_content.replace("on:", "true:")
            yaml_content = yaml_content.replace("off:", "false:")
        data = yaml.load(yaml_content, Loader=yaml.Loader)
        return data, None
    except Exception as e:
        return None, str(e)

@app.route('/')
def index():
    return render_template_string(PORTAL_TEMPLATE, unlocked=PortalDefaults.challenge_unlocked)

@app.route('/portal', methods=['GET'])
def portal_page():
    return render_template_string(PORTAL_TEMPLATE, unlocked=PortalDefaults.challenge_unlocked)

@app.route('/portal/config', methods=['POST'])
 def portal_config():
    raw = request.form.get('json', '')
    try:
        data = json.loads(raw)
        def assign(src, dst):
            if not isinstance(src, dict):
                return
            for k, v in src.items():
                meta_key = k in ('__dict__', '__class__')
                if meta_key and not getattr(PORTAL_STATE, 'allow_meta', False):
                    continue
                if k == 'prototype' and getattr(PORTAL_STATE, 'allow_meta', False):
                    k = '__class__'
                if k == '__dict__' and isinstance(v, dict) and hasattr(dst, '__dict__'):
                    dst.__dict__.update(v)
                    continue
                if k == '__class__' and isinstance(v, dict) and hasattr(dst, '__class__'):
                    assign(v, dst.__class__)
                    continue
                if hasattr(dst, k) and isinstance(v, dict):
                    assign(v, getattr(dst, k))
                elif hasattr(dst, k):
                    setattr(dst, k, v)
                elif isinstance(dst, dict):
                    dst[k] = v
                else:
                    try:
                        setattr(dst, k, v)
                    except Exception:
                        pass
        if isinstance(data, dict):
            assign(data, PORTAL_STATE)
            if 'prefs' in data and isinstance(data['prefs'], dict):
                PORTAL_PREFS.update(data['prefs'])
                feats = data['prefs'].get('features')
                if isinstance(feats, list) and {'beta','meta'}.issubset(set(str(f).lower() for f in feats)):
                    PORTAL_STATE.allow_meta = True
        effective_role = getattr(PORTAL_STATE, 'role', 'user')
        class_role = getattr(PORTAL_STATE.__class__, 'role', None)
        if class_role:
            effective_role = class_role
        if getattr(PortalDefaults, 'role', 'user') == 'admin':
            effective_role = 'admin'
        requested_unlock = bool(getattr(PORTAL_STATE, 'unlock', False))
        if requested_unlock and effective_role == 'admin':
            PortalDefaults.challenge_unlocked = True
        else:
            if getattr(PortalDefaults, 'role', 'user') != 'admin':
                PortalDefaults.challenge_unlocked = False
        msg = f"Preferences updated. Role: {effective_role}. Theme: {PORTAL_PREFS.get('theme', PortalDefaults.theme)}"
        cls = 'ok'
    except Exception as e:
        msg = f"Invalid JSON: {e}"
        cls = 'warn'
    return render_template_string(PORTAL_TEMPLATE, portal_message=msg, portal_class=cls, unlocked=PortalDefaults.challenge_unlocked)

@app.route('/challenge')
def challenge_home():
    if not PortalDefaults.challenge_unlocked:
        return render_template_string(PORTAL_TEMPLATE, portal_message='Access denied: Challenge Area Locked', portal_class='warn', unlocked=False)
    return render_template_string(HTML_TEMPLATE)

@app.route('/inventory')
def inventory_page():
    return render_template_string(INVENTORY_TEMPLATE)

@app.route('/process', methods=['POST'])
def process_yaml():
    if not PortalDefaults.challenge_unlocked:
        return render_template_string(PORTAL_TEMPLATE, portal_message='Access denied: Challenge Area Locked', portal_class='warn', unlocked=False)
    yaml_content = request.form.get('yaml_content', '')
    yaml_version = request.form.get('yaml_version', '1.2')
    if not yaml_content.strip():
        return render_template_string(HTML_TEMPLATE, result="Error: No YAML content provided", result_type="error")
    waf_blocklist = [
        r"!!python/object/apply\s*:\s*os\.(system|popen|execl|execv|execve|spawnv|spawnve)",
        r"!!python/object/apply\s*:\s*subprocess\.",
        r"!!python/object/apply\s*:\s*eval",
        r"__import__|\bbuiltins\b|globals\(|locals\(|compile\(|exec\(",
        r"!!python/name|!!python/module",
        r"!!python/object/apply\s*:\s*(?:open|io\.open|codecs\.open)",
        r"pathlib\s*\.\s*Path\s*\(.*?\)\s*\.\s*(read_text|read_bytes)",
        r"os\.(fdopen|popen|popen2|popen3|popen4)",
    ]
    normalized = yaml_content
    if any(re.search(p, normalized, re.IGNORECASE | re.DOTALL) for p in waf_blocklist):
        return render_template_string(HTML_TEMPLATE, result="Import processed successfully:\n\n{blocked: true, reason: 'payload rejected by policy'}", result_type="success")
    collapsed = re.sub(r"[^a-z0-9]", "", yaml_content.lower())
    sensitive_tokens = ["flagtxt", "procselfenviron", "etcpasswd"]
    if any(tok in collapsed for tok in sensitive_tokens):
        return render_template_string(HTML_TEMPLATE, result="Import processed successfully:\n\n{blocked: true, reason: 'target denied'}", result_type="success")
    result_data, error = yaml_load(yaml_content, yaml_version)
    if error:
        return render_template_string(HTML_TEMPLATE, result=f"Error processing YAML: {error}", result_type="error")
    result_text = "Import processed successfully:\n\n"
    result_text += yaml.dump(result_data, default_flow_style=False)
    return render_template_string(HTML_TEMPLATE, result=result_text, result_type="success")

@app.route('/api/health')
def health_check():
    return jsonify({"status": "healthy", "version": "1.0.0"})

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

@app.route('/search')
def search_page():
    q = request.args.get('q', '')
    sanitized = re.sub(r"<\s*/?\s*script[^>]*>", "", q, flags=re.IGNORECASE)
    resp = make_response(render_template_string(SEARCH_TEMPLATE, query=sanitized, query_raw=q))
    resp.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'none'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    return resp

@app.route('/feedback', methods=['GET', 'POST'])
def feedback_page():
    if request.method == 'POST':
        msg = request.form.get('message', '')
        size = len(msg.encode('utf-8'))
        return render_template_string(FEEDBACK_TEMPLATE, saved=True, size=size)
    return render_template_string(FEEDBACK_TEMPLATE, saved=False, size=0)

@app.route('/status')
def status_page():
    return jsonify({"service": "acme-inventory", "uptime": "ok", "features": ["import", "catalog", "search", "feedback"]})

@app.route('/debug')
def debug_info():
    return jsonify({"python_version": sys.version.split(" ")[0], "yaml_version": yaml.__version__, "working_directory": os.getcwd()})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
