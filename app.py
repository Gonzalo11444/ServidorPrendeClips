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
    return "Servidor PrendeClips V2 (Modo Paranoico)"

def obtener_info_real(license_key, hwid):
    """
    Función auxiliar que hace el TRIPLE chequeo para encontrar la metadata.
    Devuelve: (EsValida, CanalGuardado, MembershipID)
    """
    # Paso 1: Validar para obtener el ID de membresía y metadata básica
    url_validate = f"https://api.whop.com/api/v2/memberships/{license_key}/validate_license"
    payload = {"metadata": {"hwid": hwid}}
    
    try:
        r = requests.post(url_validate, json=payload, headers=get_headers(), timeout=10)
        
        if r.status_code not in [200, 201]:
            return False, None, None
            
        data = r.json()
        is_valid = data.get("valid", False)
        mem_id = data.get("id") # ID real de la membresía (mem_...)
        
        # Intentamos leer el canal de la respuesta de validación
        meta = data.get("metadata", {})
        canal = meta.get("twitch_channel")
        
        # Paso 2: Si es válida pero no vemos canal, consultamos la ID directa (Más fiable)
        if is_valid and not canal and mem_id:
            url_get = f"https://api.whop.com/api/v2/memberships/{mem_id}"
            r2 = requests.get(url_get, headers=get_headers(), timeout=5)
            if r2.status_code == 200:
                data2 = r2.json()
                meta2 = data2.get("metadata", {})
                canal = meta2.get("twitch_channel")
        
        return is_valid, canal, mem_id

    except Exception as e:
        print(f"Error obteniendo info: {e}")
        return False, None, None

@app.route('/validar', methods=['POST'])
def validar():
    data = request.json
    key = data.get('license_key')
    hwid = data.get('hwid')

    if not key or not hwid:
        return jsonify({"valid": False, "error": "Faltan datos"}), 400

    is_valid, canal, _ = obtener_info_real(key, hwid)
    
    if is_valid is False:
        # Si obtener_info_real falló, puede ser inválida o error 404
        return jsonify({"valid": False, "error": "Licencia no válida o no encontrada"}), 200 # Devolvemos 200 con valid:False para que el cliente lo gestione
        
    return jsonify({
        "valid": is_valid,
        "linked_channel": canal,
        "status": 200
    })

@app.route('/vincular', methods=['POST'])
def vincular():
    data = request.json
    key = data.get('license_key')
    canal_nuevo = data.get('canal')
    hwid = data.get('hwid')

    if not all([key, canal_nuevo, hwid]):
        return jsonify({"success": False, "error": "Faltan datos"}), 400

    # 1. 🔒 INSPECCIÓN PROFUNDA
    is_valid, canal_existente, mem_id = obtener_info_real(key, hwid)

    if not is_valid:
        return jsonify({"success": False, "error": "No se puede vincular una licencia inválida"}), 403

    # 2. 🔒 EL CANDADO
    if canal_existente and canal_existente.strip():
        # Ya hay un canal. Comparamos (ignorando mayúsculas)
        if canal_existente.lower().strip() != canal_nuevo.lower().strip():
            print(f"BLOQUEO: {canal_existente} vs {canal_nuevo}")
            return jsonify({
                "success": False, 
                "error": f"🔒 ERROR CRÍTICO: Esta licencia YA pertenece a '{canal_existente}'. No puedes cambiarla."
            }), 200 # Devolvemos 200 pero success False para que el cliente muestre el mensaje

    # 3. GUARDAR (Usando el ID real si lo tenemos, es más seguro)
    target_id = mem_id if mem_id else key
    url_update = f"https://api.whop.com/api/v2/memberships/{target_id}"
    
    payload = {
        "metadata": {
            "twitch_channel": canal_nuevo,
            "hwid": hwid
        }
    }

    try:
        r = requests.post(url_update, json=payload, headers=get_headers(), timeout=10)
        if r.status_code in [200, 201]:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": f"Whop Error: {r.status_code}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
