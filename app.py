import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")

def get_headers():
    token = WHOP_API_KEY.replace("Bearer ", "").strip()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

@app.route('/')
def home():
    return "Servidor PrendeClips Activo"

@app.route('/validar', methods=['POST'])
def validar():
    data = request.json or {}
    license_key = data.get('license_key')
    hwid = data.get('hwid')

    if not license_key or not hwid:
        return jsonify({"valid": False, "error": "Faltan datos"}), 400

    url = f"https://api.whop.com/api/v2/memberships/{license_key}/validate_license"
    payload = {"metadata": {"hwid": hwid}}

    try:
        r = requests.post(url, json=payload, headers=get_headers(), timeout=10)

        if r.status_code in [200, 201]:
            whop_data = r.json()
            is_valid = whop_data.get("valid", False)

            linked_channel = None
            if is_valid:
                meta = whop_data.get("metadata", {}) or {}
                linked_channel = meta.get("twitch_channel")

            return jsonify({
                "valid": is_valid,
                "linked_channel": linked_channel,
                "status": r.status_code
            })

        elif r.status_code == 404:
            return jsonify({"valid": False, "error": "Licencia no existe"}), 404
        else:
            return jsonify({"valid": False, "error": "Error Whop"}), r.status_code

    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 500

@app.route('/vincular', methods=['POST'])
def vincular():
    data = request.json or {}
    license_key = data.get('license_key')
    canal = data.get('canal')
    hwid = data.get('hwid')

    if not all([license_key, canal, hwid]):
        return jsonify({"success": False, "error": "Faltan datos"}), 400

    url = f"https://api.whop.com/api/v2/memberships/{license_key}"
    payload = {
        "metadata": {
            "twitch_channel": canal,
            "hwid": hwid
        }
    }

    try:
        r = requests.post(url, json=payload, headers=get_headers(), timeout=10)
        if r.status_code in [200, 201]:
            return jsonify({"success": True})
        else:
            return jsonify({
                "success": False,
                "whop_status": r.status_code,
                "response": r.text
            }), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/admin/reset', methods=['POST'])
def admin_reset():
    secret = request.headers.get("X-Admin-Secret", "").strip()

    if not ADMIN_SECRET:
        return jsonify({"success": False, "error": "ADMIN_SECRET no configurado en el servidor"}), 500

    if secret != ADMIN_SECRET:
        return jsonify({"success": False, "error": "No autorizado"}), 401

    data = request.json or {}
    license_key = data.get("license_key", "").strip()

    if not license_key:
        return jsonify({"success": False, "error": "Falta license_key"}), 400

    url = f"https://api.whop.com/api/v2/memberships/{license_key}"
    payload = {
        "metadata": {
            "twitch_channel": None,
            "hwid": None
        }
    }

    try:
        r = requests.post(url, json=payload, headers=get_headers(), timeout=10)

        if r.status_code in [200, 201]:
            return jsonify({
                "success": True,
                "message": f"Licencia {license_key} liberada"
            }), 200

        return jsonify({
            "success": False,
            "error": "Whop devolvió error",
            "whop_status": r.status_code,
            "response": r.text
        }), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
