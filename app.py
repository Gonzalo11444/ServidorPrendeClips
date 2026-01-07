import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")

def get_headers():
    token = WHOP_API_KEY.replace("Bearer ", "").strip()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

@app.route('/')
def home():
    return "Servidor PrendeClips BLINDADO 🔒"

@app.route('/validar', methods=['POST'])
def validar():
    """Valida y devuelve el canal vinculado"""
    data = request.json
    license_key = data.get('license_key')
    hwid = data.get('hwid')

    if not license_key or not hwid:
        return jsonify({"valid": False, "error": "Faltan datos"}), 400

    url = f"https://api.whop.com/api/v2/memberships/{license_key}/validate_license"
    payload = {"metadata": {"hwid": hwid}}
    
    try:
        r = requests.post(url, json=payload, headers=get_headers(), timeout=10)
        
        if r.status_code in [200, 201]:
            data_whop = r.json()
            is_valid = data_whop.get("valid", False)
            
            # Recuperar canal
            linked_channel = None
            if is_valid:
                meta = data_whop.get("metadata", {})
                linked_channel = meta.get("twitch_channel")

            return jsonify({
                "valid": is_valid,
                "linked_channel": linked_channel,
                "status": r.status_code
            })
        elif r.status_code == 404:
            return jsonify({"valid": False, "error": "Licencia no existe"}), 404
        else:
            return jsonify({"valid": False, "error": f"Whop: {r.status_code}"}), r.status_code

    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 500

@app.route('/vincular', methods=['POST'])
def vincular():
    """
    Intenta vincular. 
    🔒 SEGURIDAD MEJORADA: Usa validate_license para leer el estado actual.
    """
    data = request.json
    license_key = data.get('license_key')
    canal_nuevo = data.get('canal')
    hwid = data.get('hwid')

    if not all([license_key, canal_nuevo, hwid]):
        return jsonify({"success": False, "error": "Faltan datos"}), 400

    # 1. 🔒 LEER EL CANDADO (Usando validate, que nunca falla al leer por key)
    check_url = f"https://api.whop.com/api/v2/memberships/{license_key}/validate_license"
    # Enviamos metadata vacía para no alterar nada, solo leer
    try:
        r_check = requests.post(check_url, json={"metadata": {}}, headers=get_headers(), timeout=10)
        
        if r_check.status_code in [200, 201]:
            info = r_check.json()
            meta = info.get("metadata", {})
            canal_existente = meta.get("twitch_channel")

            # SI YA HAY UN CANAL GUARDADO...
            if canal_existente and canal_existente.strip() != "":
                # Y ES DIFERENTE AL QUE INTENTAN PONER...
                if canal_existente.lower().strip() != canal_nuevo.lower().strip():
                    return jsonify({
                        "success": False, 
                        "error": f"🔒 ERROR CRÍTICO: Esta licencia ya pertenece a '{canal_existente}'. No puedes cambiarla."
                    }), 403
    except Exception as e:
        return jsonify({"success": False, "error": f"Error verificando candado: {str(e)}"}), 500

    # 2. Si llegamos aquí, el candado está abierto o es el mismo canal. ESCRIBIMOS.
    update_url = f"https://api.whop.com/api/v2/memberships/{license_key}"
    payload = {
        "metadata": {
            "twitch_channel": canal_nuevo,
            "hwid": hwid
        }
    }

    try:
        r = requests.post(update_url, json=payload, headers=get_headers(), timeout=10)
        if r.status_code in [200, 201]:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": f"Whop Update falló: {r.status_code}"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
