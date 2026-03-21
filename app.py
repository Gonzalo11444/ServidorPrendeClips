import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# 🔒 LA CLAVE VIVE AQUÍ (En las variables de entorno de Render)
# Si no encuentra la clave, usará una cadena vacía (y fallará, protegiéndote)
WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")

def get_headers():
    # Aseguramos que el formato sea correcto
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
    """Valida la licencia y devuelve si tiene canal vinculado"""
    data = request.json
    license_key = data.get('license_key')
    hwid = data.get('hwid')

    if not license_key or not hwid:
        return jsonify({"valid": False, "error": "Faltan datos"}), 400

    # 1. Preguntamos a Whop
    url = f"https://api.whop.com/api/v2/memberships/{license_key}/validate_license"
    payload = {"metadata": {"hwid": hwid}}
    
    try:
        r = requests.post(url, json=payload, headers=get_headers(), timeout=10)
        
        if r.status_code in [200, 201]:
            whop_data = r.json()
            is_valid = whop_data.get("valid", False)
            
            # 2. Si es válida, miramos si tiene canal vinculado (Cloud Lock)
            linked_channel = None
            if is_valid:
                # A veces la metadata viene en 'metadata' o dentro del objeto principal
                # Intentamos obtener la info completa de la membresía para leer metadata
                # (El endpoint de validate a veces es escueto, mejor asegurar)
                meta = whop_data.get("metadata", {})
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
    """Bloquea la licencia a un canal y HWID en la nube"""
    data = request.json
    license_key = data.get('license_key')
    canal = data.get('canal')
    hwid = data.get('hwid')

    if not all([license_key, canal, hwid]):
        return jsonify({"success": False, "error": "Faltan datos"}), 400

    # Endpoint para EDITAR la membresía (guardar metadata)
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
            return jsonify({"success": False, "whop_status": r.status_code}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)