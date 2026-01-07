import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- CONFIGURACIÓN ---
# Las claves las pondrás en RENDER (Environment Variables)
WHOP_API_KEY = os.environ.get("WHOP_API_KEY", "")
# Datos de Upstash (Base de datos gratis)
UPSTASH_URL = os.environ.get("UPSTASH_REDIS_REST_URL", "")
UPSTASH_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
# Tu clave secreta para desvincular manualmente (pon la que quieras en Render)
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "PrendoElMejor1234")

# --- HELPERS ---
def get_whop_headers():
    token = WHOP_API_KEY.replace("Bearer ", "").strip()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def db_get(key):
    """Lee un valor de la base de datos Upstash"""
    if not UPSTASH_URL: return None
    try:
        # Usamos la API REST de Upstash para leer
        url = f"{UPSTASH_URL}/get/{key}"
        headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        # Upstash devuelve: {"result": "valor_guardado"} o {"result": null}
        return data.get("result") 
    except:
        return None

def db_set_nx(key, value):
    """
    Guarda SOLO si no existe (SET NX).
    Devuelve True si se guardó, False si ya existía (estaba bloqueado).
    """
    if not UPSTASH_URL: return False
    try:
        # Comando SET con opción NX (Not Exists)
        url = f"{UPSTASH_URL}/set/{key}/{value}?nx"
        headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=5)
        data = r.json()
        # Si guardó, result es "OK". Si ya existía, result es null.
        return data.get("result") == "OK"
    except:
        return False

def db_del(key):
    """Borra un valor (Para el Admin)"""
    if not UPSTASH_URL: return False
    try:
        url = f"{UPSTASH_URL}/del/{key}"
        headers = {"Authorization": f"Bearer {UPSTASH_TOKEN}"}
        requests.get(url, headers=headers, timeout=5)
        return True
    except:
        return False

# --- RUTAS ---

@app.route('/')
def home():
    return "Servidor PrendeClips con DB Persistente 🚀"

@app.route('/validar', methods=['POST'])
def validar():
    """Valida en Whop y consulta el canal BLINDADO en nuestra DB"""
    data = request.json
    license_key = data.get('license_key')
    hwid = data.get('hwid')

    if not license_key or not hwid:
        return jsonify({"valid": False, "error": "Faltan datos"}), 400

    # 1. Validar validez con Whop (Esto siempre es necesario para ver si paga)
    url_whop = f"https://api.whop.com/api/v2/memberships/{license_key}/validate_license"
    
    try:
        r = requests.post(url_whop, json={"metadata": {"hwid": hwid}}, headers=get_whop_headers(), timeout=10)
        
        if r.status_code in [200, 201]:
            whop_data = r.json()
            is_valid = whop_data.get("valid", False)
            
            linked_channel = None
            if is_valid:
                # 2. AQUÍ ESTÁ EL TRUCO: No miramos Whop, miramos NUESTRA DB
                # Buscamos si esta licencia ya tiene dueño en Upstash
                linked_channel = db_get(f"binding:{license_key}")

            return jsonify({
                "valid": is_valid,
                "linked_channel": linked_channel, # Devolvemos lo que hay en DB (o None si es virgen)
                "status": r.status_code
            })
        
        elif r.status_code == 404:
            return jsonify({"valid": False, "error": "Licencia no existe"}), 404
        else:
            return jsonify({"valid": False, "error": f"Whop Error: {r.status_code}"}), r.status_code

    except Exception as e:
        return jsonify({"valid": False, "error": str(e)}), 500

@app.route('/vincular', methods=['POST'])
def vincular():
    """Intenta bloquear la licencia a un canal en la DB"""
    data = request.json
    license_key = data.get('license_key')
    canal_nuevo = data.get('canal', '').strip().lower()
    hwid = data.get('hwid')

    if not all([license_key, canal_nuevo, hwid]):
        return jsonify({"success": False, "error": "Faltan datos"}), 400

    # 1. Intentamos guardar con "SET NX" (Solo guardar si está vacía)
    guardado_ok = db_set_nx(f"binding:{license_key}", canal_nuevo)

    if guardado_ok:
        # ¡Éxito! Era virgen y ahora es tuya.
        # (Opcional) También lo guardamos en Whop por si quieres verlo en su panel,
        # pero la autoridad la tiene Upstash.
        try:
            url_whop = f"https://api.whop.com/api/v2/memberships/{license_key}"
            requests.post(url_whop, json={"metadata": {"twitch_channel": canal_nuevo}}, headers=get_whop_headers(), timeout=5)
        except: pass # Si falla Whop da igual, tenemos Upstash
        
        return jsonify({"success": True})
    
    else:
        # Falló al guardar -> YA EXISTÍA ALGO.
        # Leemos qué canal era para ver si es el mismo o un intento de hackeo.
        canal_existente = db_get(f"binding:{license_key}")
        
        if canal_existente == canal_nuevo:
            return jsonify({"success": True}) # Es el mismo, todo ok.
        else:
            return jsonify({
                "success": False, 
                "error": f"🔒 BLOQUEADO: Esta licencia ya pertenece a '{canal_existente}'."
            }), 409

# --- RUTA ADMIN PARA DESVINCULAR ---
@app.route('/admin/reset', methods=['POST'])
def admin_reset():
    """
    Ruta secreta para borrar un vínculo si un cliente llora.
    Headers: { "X-Admin-Secret": "tu_clave_secreta" }
    Body: { "license_key": "XXX" }
    """
    secret = request.headers.get("X-Admin-Secret")
    if secret != ADMIN_SECRET:
        return jsonify({"error": "Unauthorized"}), 401
    
    key = request.json.get("license_key")
    if db_del(f"binding:{key}"):
        return jsonify({"success": True, "message": f"Licencia {key} reseteada."})
    else:
        return jsonify({"success": False, "error": "No se pudo borrar"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
