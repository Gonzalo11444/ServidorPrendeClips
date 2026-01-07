import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# La clave vive en las variables de entorno de Render
WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")

def get_headers():
    token = WHOP_API_KEY.replace("Bearer ", "").strip()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

@app.route('/')
def home():
    return "Servidor PrendeClips con CANDADO activado 🔒"

@app.route('/validar', methods=['POST'])
def validar():
    """Valida la licencia y recupera el canal si existe"""
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
            whop_data = r.json()
            is_valid = whop_data.get("valid", False)
            
            linked_channel = None
            if is_valid:
                # Buscamos el canal en la metadata para devolvérselo al cliente
                meta = whop_data.get("metadata", {})
                linked_channel = meta.get("twitch_channel")

            return jsonify({
                "valid": is_valid,
                "linked_channel": linked_channel,
                "status": r.status_code
            })
        
        elif r.status_code == 404:
            return jsonify({"valid": False, "error": "Licencia no encontrada"}), 404
        else:
            return jsonify({"valid": False, "error": f"Error Whop: {r.status_code}"}), r.status_code

    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 500

@app.route('/vincular', methods=['POST'])
def vincular():
    """
    Intenta vincular un canal. 
    🔒 CANDADO: Si ya existe un canal distinto, RECHAZA la petición.
    """
    data = request.json
    license_key = data.get('license_key')
    canal_nuevo = data.get('canal')
    hwid = data.get('hwid')

    if not all([license_key, canal_nuevo, hwid]):
        return jsonify({"success": False, "error": "Faltan datos"}), 400

    # 1. 🔒 COMPROBACIÓN DE SEGURIDAD (EL CANDADO)
    # Antes de escribir, leemos qué hay guardado.
    get_url = f"https://api.whop.com/api/v2/memberships/{license_key}"
    try:
        r_check = requests.get(get_url, headers=get_headers(), timeout=10)
        if r_check.status_code == 200:
            info = r_check.json()
            meta = info.get("metadata", {})
            canal_existente = meta.get("twitch_channel")

            # Si YA hay un canal y es diferente al que intentan poner... ¡ERROR!
            if canal_existente and canal_existente.strip() != "":
                if canal_existente.lower() != canal_nuevo.lower():
                    print(f"🔒 Bloqueo: Intento de cambio {canal_existente} -> {canal_nuevo}")
                    return jsonify({
                        "success": False, 
                        "error": f"🔒 BLOQUEADO: Esta licencia ya pertenece al canal '{canal_existente}'. No puedes cambiarlo."
                    }), 403
                else:
                    # Si es el mismo canal, dejamos pasar (es un re-vincular inofensivo)
                    pass
    except Exception as e:
        # Si falla la comprobación, por seguridad abortamos
        return jsonify({"success": False, "error": f"Error verificando candado: {str(e)}"}), 500

    # 2. Si pasamos el candado, procedemos a guardar (Metadata Update)
    post_url = f"https://api.whop.com/api/v2/memberships/{license_key}"
    payload = {
        "metadata": {
            "twitch_channel": canal_nuevo,
            "hwid": hwid
        }
    }

    try:
        r = requests.post(post_url, json=payload, headers=get_headers(), timeout=10)
        if r.status_code in [200, 201]:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "whop_status": r.status_code}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
