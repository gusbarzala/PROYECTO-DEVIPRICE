import json
import os
import re
import sqlite3
import urllib.request
from collections import Counter
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, jsonify
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'devprice_clave_secreta_fts18'
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')
# Pegar aquí la URL de "Archivo -> Insertar informe -> Sitio web o portal" de Power BI Service
# (o definir la variable de entorno POWERBI_EMBED_URL).
POWERBI_EMBED_URL = os.environ.get('POWERBI_EMBED_URL', '').strip()
# IDs >= CUSTOM_ID_BASE corresponden a altas propias en DevPrice (no existen en Steam)
CUSTOM_ID_BASE = 90000000

@app.context_processor
def inject_globals():
    """Variables globales disponibles en todas las plantillas Jinja."""
    return {"custom_id_base": CUSTOM_ID_BASE}

# Listado curado de géneros y categorías principales presentes en la base de Steam
GENEROS_PRINCIPALES = [
    "Acción",
    "Aventura",
    "Juegos de Rol",
    "Estrategia",
    "Independiente",
    "Simulación",
    "Casual",
    "Deportes",
    "Carreras",
    "Multijugador Masivo",
    "Acceso Anticipado",
    "Free To Play",
]

CATEGORIAS_PRINCIPALES = [
    "Un Jugador",
    "Multijugador",
    "Cooperativo",
    "Online Cooperativo",
    "PvP",
    "Online PvP",
    "Cross-Platform Multiplayer",
    "Soporte total con mando",
    "Soporte parcial con mando",
    "Logros de Steam",
    "Steam Cloud",
    "Steam Workshop",
    "Steam Trading Cards",
    "Family Sharing",
]

# Catálogo de idiomas con su bandera emoji para selección en ABM y visualización en Detalle
IDIOMAS_CATALOGO = [
    {"nombre": "Español (Latinoamérica)", "bandera": "🇦🇷"},
    {"nombre": "Español (España)", "bandera": "🇪🇸"},
    {"nombre": "Inglés", "bandera": "🇺🇸"},
    {"nombre": "Portugués (Brasil)", "bandera": "🇧🇷"},
    {"nombre": "Portugués (Portugal)", "bandera": "🇵🇹"},
    {"nombre": "Francés", "bandera": "🇫🇷"},
    {"nombre": "Alemán", "bandera": "🇩🇪"},
    {"nombre": "Italiano", "bandera": "🇮🇹"},
    {"nombre": "Japonés", "bandera": "🇯🇵"},
    {"nombre": "Coreano", "bandera": "🇰🇷"},
    {"nombre": "Chino Simplificado", "bandera": "🇨🇳"},
    {"nombre": "Chino Tradicional", "bandera": "🇹🇼"},
    {"nombre": "Ruso", "bandera": "🇷🇺"},
    {"nombre": "Polaco", "bandera": "🇵🇱"},
    {"nombre": "Turco", "bandera": "🇹🇷"},
    {"nombre": "Árabe", "bandera": "🇸🇦"},
    {"nombre": "Neerlandés", "bandera": "🇳🇱"},
    {"nombre": "Sueco", "bandera": "🇸🇪"},
    {"nombre": "Noruego", "bandera": "🇳🇴"},
    {"nombre": "Danés", "bandera": "🇩🇰"},
    {"nombre": "Finlandés", "bandera": "🇫🇮"},
    {"nombre": "Checo", "bandera": "🇨🇿"},
    {"nombre": "Húngaro", "bandera": "🇭🇺"},
    {"nombre": "Ucraniano", "bandera": "🇺🇦"},
    {"nombre": "Griego", "bandera": "🇬🇷"},
    {"nombre": "Tailandés", "bandera": "🇹🇭"},
    {"nombre": "Vietnamita", "bandera": "🇻🇳"},
    {"nombre": "Indonesio", "bandera": "🇮🇩"},
    {"nombre": "Rumano", "bandera": "🇷🇴"},
    {"nombre": "Búlgaro", "bandera": "🇧🇬"},
]

SINONIMOS_IDIOMAS = {
    "español (latinoamérica)": ("Español (Latinoamérica)", "🇦🇷"),
    "español de américa latina": ("Español (Latinoamérica)", "🇦🇷"),
    "spanish - latin america": ("Español (Latinoamérica)", "🇦🇷"),
    "español latino": ("Español (Latinoamérica)", "🇦🇷"),
    "español (españa)": ("Español (España)", "🇪🇸"),
    "español de españa": ("Español (España)", "🇪🇸"),
    "spanish - spain": ("Español (España)", "🇪🇸"),
    "español": ("Español (España)", "🇪🇸"),
    "spanish": ("Español (España)", "🇪🇸"),
    "inglés": ("Inglés", "🇺🇸"),
    "ingles": ("Inglés", "🇺🇸"),
    "english": ("Inglés", "🇺🇸"),
    "portugués (brasil)": ("Portugués (Brasil)", "🇧🇷"),
    "portugués de brasil": ("Portugués (Brasil)", "🇧🇷"),
    "portugues de brasil": ("Portugués (Brasil)", "🇧🇷"),
    "portuguese - brazil": ("Portugués (Brasil)", "🇧🇷"),
    "portugués": ("Portugués (Brasil)", "🇧🇷"),
    "portuguese": ("Portugués (Brasil)", "🇧🇷"),
    "portugués (portugal)": ("Portugués (Portugal)", "🇵🇹"),
    "portugués de portugal": ("Portugués (Portugal)", "🇵🇹"),
    "portugues de portugal": ("Portugués (Portugal)", "🇵🇹"),
    "portuguese - portugal": ("Portugués (Portugal)", "🇵🇹"),
    "francés": ("Francés", "🇫🇷"),
    "frances": ("Francés", "🇫🇷"),
    "french": ("Francés", "🇫🇷"),
    "alemán": ("Alemán", "🇩🇪"),
    "aleman": ("Alemán", "🇩🇪"),
    "german": ("Alemán", "🇩🇪"),
    "italiano": ("Italiano", "🇮🇹"),
    "italian": ("Italiano", "🇮🇹"),
    "japonés": ("Japonés", "🇯🇵"),
    "japones": ("Japonés", "🇯🇵"),
    "japanese": ("Japonés", "🇯🇵"),
    "coreano": ("Coreano", "🇰🇷"),
    "corenao": ("Coreano", "🇰🇷"),
    "korean": ("Coreano", "🇰🇷"),
    "chino simplificado": ("Chino Simplificado", "🇨🇳"),
    "simplified chinese": ("Chino Simplificado", "🇨🇳"),
    "chino mandarín": ("Chino Simplificado", "🇨🇳"),
    "chino mandarin": ("Chino Simplificado", "🇨🇳"),
    "chinese": ("Chino Simplificado", "🇨🇳"),
    "chino tradicional": ("Chino Tradicional", "🇹🇼"),
    "traditional chinese": ("Chino Tradicional", "🇹🇼"),
    "ruso": ("Ruso", "🇷🇺"),
    "russian": ("Ruso", "🇷🇺"),
    "polaco": ("Polaco", "🇵🇱"),
    "polish": ("Polaco", "🇵🇱"),
    "turco": ("Turco", "🇹🇷"),
    "turkish": ("Turco", "🇹🇷"),
    "árabe": ("Árabe", "🇸🇦"),
    "arabe": ("Árabe", "🇸🇦"),
    "arabic": ("Árabe", "🇸🇦"),
    "neerlandés": ("Neerlandés", "🇳🇱"),
    "neerlandes": ("Neerlandés", "🇳🇱"),
    "dutch": ("Neerlandés", "🇳🇱"),
    "sueco": ("Sueco", "🇸🇪"),
    "swedish": ("Sueco", "🇸🇪"),
    "noruego": ("Noruego", "🇳🇴"),
    "norwegian": ("Noruego", "🇳🇴"),
    "danés": ("Danés", "🇩🇰"),
    "danes": ("Danés", "🇩🇰"),
    "danish": ("Danés", "🇩🇰"),
    "finlandés": ("Finlandés", "🇫🇮"),
    "finlandes": ("Finlandés", "🇫🇮"),
    "finnish": ("Finlandés", "🇫🇮"),
    "checo": ("Checo", "🇨🇿"),
    "czech": ("Checo", "🇨🇿"),
    "húngaro": ("Húngaro", "🇭🇺"),
    "hungaro": ("Húngaro", "🇭🇺"),
    "hungarian": ("Húngaro", "🇭🇺"),
    "ucraniano": ("Ucraniano", "🇺🇦"),
    "ukrainian": ("Ucraniano", "🇺🇦"),
    "griego": ("Griego", "🇬🇷"),
    "greek": ("Griego", "🇬🇷"),
    "tailandés": ("Tailandés", "🇹🇭"),
    "tailandes": ("Tailandés", "🇹🇭"),
    "thai": ("Tailandés", "🇹🇭"),
    "vietnamita": ("Vietnamita", "🇻🇳"),
    "vietnamese": ("Vietnamita", "🇻🇳"),
    "indonesio": ("Indonesio", "🇮🇩"),
    "indonesian": ("Indonesio", "🇮🇩"),
    "rumano": ("Rumano", "🇷🇴"),
    "romanian": ("Rumano", "🇷🇴"),
    "búlgaro": ("Búlgaro", "🇧🇬"),
    "bulgaro": ("Búlgaro", "🇧🇬"),
    "blúlgaro": ("Búlgaro", "🇧🇬"),
    "bulgarian": ("Búlgaro", "🇧🇬"),
    "catalan": ("Catalán", "🇪🇸"),
    "catalán": ("Catalán", "🇪🇸"),
    "basque": ("Euskera", "🇪🇸"),
    "galician": ("Gallego", "🇪🇸"),
    "slovak": ("Eslovaco", "🇸🇰"),
    "slovenian": ("Esloveno", "🇸🇮"),
    "croatian": ("Croata", "🇭🇷"),
    "serbian": ("Serbio", "🇷🇸"),
    "hindi": ("Hindi", "🇮🇳"),
    "hebrew": ("Hebreo", "🇮🇱"),
    "lithuanian": ("Lituano", "🇱🇹"),
    "latvian": ("Letón", "🇱🇻"),
    "estonian": ("Estonio", "🇪🇪"),
    "belarusian": ("Bielorruso", "🇧🇾"),
    "malay": ("Malayo", "🇲🇾"),
    "filipino": ("Filipino", "🇵🇭"),
    "persian": ("Persa", "🇮🇷"),
    "afrikaans": ("Afrikáans", "🇿🇦"),
    "icelandic": ("Islandés", "🇮🇸"),
}

@app.template_filter('idiomas_con_bandera')
def parsear_idiomas_con_bandera(texto_idiomas):
    """Convierte la cadena cruda de idiomas de Steam en una lista de dicts {'nombre', 'bandera'}."""
    if not texto_idiomas:
        return []
    limpio = str(texto_idiomas)
    limpio = re.sub(r'<br>.*$', '', limpio, flags=re.IGNORECASE)
    limpio = re.sub(r'languages with full audio support.*$', '', limpio, flags=re.IGNORECASE)
    limpio = re.sub(r'con soporte de audio completo.*$', '', limpio, flags=re.IGNORECASE)
    limpio = re.sub(r'^Idiomas\s+', '', limpio, flags=re.IGNORECASE)
    limpio = limpio.replace('<strong>*</strong>', '').replace('*', '')

    partes_crudas = [p.strip() for p in limpio.split(',') if p.strip()]
    resultado = []
    vistos = set()

    def agregar(nombre, bandera):
        if nombre not in vistos:
            vistos.add(nombre)
            resultado.append({"nombre": nombre, "bandera": bandera})

    for parte in partes_crudas:
        clave = parte.lower().strip()
        if "españa" in clave and "américa latina" in clave:
            agregar("Español (España)", "🇪🇸")
            agregar("Español (Latinoamérica)", "🇦🇷")
        elif "portugal" in clave and "brasil" in clave:
            agregar("Portugués (Portugal)", "🇵🇹")
            agregar("Portugués (Brasil)", "🇧🇷")
        elif clave in SINONIMOS_IDIOMAS:
            nom, ban = SINONIMOS_IDIOMAS[clave]
            agregar(nom, ban)
        else:
            agregar(parte[:1].upper() + parte[1:], "🌐")

    return resultado

def get_db():
    """Conexión a la base de datos SQLite."""
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Cierra la conexión al finalizar la petición."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def roles_requeridos(*roles):
    """Decorador para restringir rutas del ABM según el rol del usuario en sesión."""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            usuario = session.get('usuario')
            if not usuario:
                flash("Debés iniciar sesión para acceder a esta función.", "warning")
                return redirect(url_for('login'))
            if usuario.get('rol') not in roles:
                flash("No tenés permisos suficientes para realizar esta operación.", "danger")
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapped
    return decorator

def get_juegos_columns(db):
    """Detecta dinámicamente los nombres de las columnas en la tabla juegos."""
    cursor = db.execute("PRAGMA table_info(juegos)")
    cols = [row['name'] for row in cursor.fetchall()]
    
    # Buscar columna de nombre
    col_name = next((c for c in cols if c.lower() in ['name', 'nombre', 'title', 'juego', 'titulo']), cols[1] if len(cols) > 1 else 'id')
    
    # Buscar columna de precio
    col_price = next((c for c in cols if 'price' in c.lower() or 'precio' in c.lower()), None)
    
    return col_name, col_price, cols

def calcular_percentil(valores_ordenados, p):
    """Calcula el percentil p (0..100) sobre una lista ordenada de números."""
    if not valores_ordenados:
        return 0.0
    k = (len(valores_ordenados) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(valores_ordenados) - 1)
    if f == c:
        return round(valores_ordenados[int(k)], 2)
    d0 = valores_ordenados[f] * (c - k)
    d1 = valores_ordenados[c] * (k - f)
    return round(d0 + d1, 2)

@app.route('/')
def index():
    """Página principal con catálogo de juegos, búsqueda, filtro por categoría y ordenamiento."""
    db = get_db()
    col_name, col_price, all_cols = get_juegos_columns(db)
    
    # Parámetros de búsqueda, filtrado y ordenamiento
    q = request.args.get('q', '').strip()
    categoria = request.args.get('categoria', '').strip()
    max_price = request.args.get('max_price', type=float)
    orden = request.args.get('orden', 'ventas').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page

    select_cols = (
        'SELECT *, ID_Juego AS id, '
        'ROUND(CAST("Precio" AS REAL) / 100.0, 2) AS precio_usd, '
        'ROUND(CAST("Precio_Inicial" AS REAL) / 100.0, 2) AS precio_inicial_usd '
        'FROM juegos WHERE 1=1'
    )
    where_clauses = ""
    params = []

    if q and col_name:
        where_clauses += f' AND "{col_name}" LIKE ?'
        params.append(f"%{q}%")
    
    if categoria:
        where_clauses += ' AND ("Categorias" LIKE ? OR "Generos" LIKE ?)'
        params.extend([f"%{categoria}%", f"%{categoria}%"])

    if max_price is not None and col_price:
        where_clauses += f' AND (CAST("{col_price}" AS REAL) / 100.0) <= ?'
        if max_price > 0 and categoria.lower() != 'free to play':
            where_clauses += f' AND CAST("{col_price}" AS REAL) > 0'
        params.append(max_price)
    elif not q and categoria.lower() != 'free to play':
        # Por defecto en el catálogo general priorizamos juegos con precio comercial (> $0)
        where_clauses += f' AND CAST("{col_price}" AS REAL) > 0'

    # Consulta total de resultados para la paginación
    count_query = "SELECT COUNT(*) FROM juegos WHERE 1=1" + where_clauses
    total_juegos = db.execute(count_query, params).fetchone()[0]

    # Expresión SQL para convertir el rango de Propietarios (ej: '20,000,000 .. 50,000,000') en entero ordenable
    ventas_expr = "CAST(REPLACE(SUBSTR(Propietarios, 1, INSTR(Propietarios, ' ') - 1), ',', '') AS INTEGER)"
    is_f2p_filter = (categoria.lower() == 'free to play') or (max_price is not None and max_price == 0)
    paid_first = "" if is_f2p_filter else f'CASE WHEN CAST("{col_price}" AS REAL) > 0 THEN 0 ELSE 1 END ASC, '

    if orden == 'precio_asc':
        order_clause = f' ORDER BY {paid_first}CAST("{col_price}" AS REAL) ASC, CAST(Positiva AS INTEGER) DESC'
    elif orden == 'precio_desc':
        order_clause = f' ORDER BY CAST("{col_price}" AS REAL) DESC, CAST(Positiva AS INTEGER) DESC'
    elif orden == 'popularidad':
        order_clause = f' ORDER BY {paid_first}CAST(Positiva AS INTEGER) DESC, CAST(Jugadores_Simultaneos AS INTEGER) DESC'
    elif orden == 'nombre_asc':
        order_clause = f' ORDER BY {paid_first}"{col_name}" COLLATE NOCASE ASC'
    elif orden == 'nombre_desc':
        order_clause = f' ORDER BY {paid_first}"{col_name}" COLLATE NOCASE DESC'
    else:
        orden = 'ventas'
        order_clause = f' ORDER BY {paid_first}{ventas_expr} DESC, CAST(Positiva AS INTEGER) DESC'

    query = select_cols + where_clauses + order_clause + " LIMIT ? OFFSET ?"
    query_params = params + [per_page, offset]

    juegos = db.execute(query, query_params).fetchall()
    total_paginas = (total_juegos + per_page - 1) // per_page if total_juegos > 0 else 1

    return render_template(
        'index.html',
        juegos=juegos,
        q=q,
        categoria=categoria,
        max_price=max_price,
        orden=orden,
        generos_lista=GENEROS_PRINCIPALES,
        categorias_lista=CATEGORIAS_PRINCIPALES,
        page=page,
        total_paginas=total_paginas,
        total_juegos=total_juegos,
        usuario=session.get('usuario'),
        col_name=col_name,
        col_price=col_price
    )

@app.route('/juego/<int:juego_id>')
def detalle_juego(juego_id):
    """Ficha detallada de un juego."""
    db = get_db()
    juego = db.execute(
        'SELECT *, ID_Juego AS id, '
        'ROUND(CAST("Precio" AS REAL) / 100.0, 2) AS precio_usd, '
        'ROUND(CAST("Precio_Inicial" AS REAL) / 100.0, 2) AS precio_inicial_usd '
        'FROM juegos WHERE ID_Juego = ?',
        (juego_id,)
    ).fetchone()
    if not juego:
        flash("El juego solicitado no existe.", "warning")
        return redirect(url_for('index'))
    return render_template('detalle.html', juego=juego, usuario=session.get('usuario'))

_CAPTURAS_CACHE = {}

@app.route('/api/juego/<int:juego_id>/capturas')
def api_capturas_juego(juego_id):
    """Consulta asíncrona de capturas oficiales desde la API pública de la tienda de Steam."""
    if juego_id >= CUSTOM_ID_BASE:
        return jsonify({"ok": False, "capturas": []})

    if juego_id in _CAPTURAS_CACHE:
        return jsonify(_CAPTURAS_CACHE[juego_id])

    url = f"https://store.steampowered.com/api/appdetails?appids={juego_id}&l=spanish"
    try:
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) DevPrice/1.0'}
        )
        with urllib.request.urlopen(req, timeout=3.5) as resp:
            raw = json.loads(resp.read().decode('utf-8'))

        app_data = raw.get(str(juego_id), {})
        if not app_data.get('success'):
            res = {"ok": False, "capturas": []}
            _CAPTURAS_CACHE[juego_id] = res
            return jsonify(res)

        data = app_data.get('data', {})
        screenshots = data.get('screenshots', [])[:10]
        capturas = [
            {
                "id": s.get("id", idx),
                "thumb": s.get("path_thumbnail", ""),
                "full": s.get("path_full", "")
            }
            for idx, s in enumerate(screenshots)
            if s.get("path_thumbnail") and s.get("path_full")
        ]
        res = {
            "ok": len(capturas) > 0,
            "capturas": capturas,
            "background": data.get("background_raw") or data.get("background") or ""
        }
        _CAPTURAS_CACHE[juego_id] = res
        return jsonify(res)
    except Exception:
        return jsonify({"ok": False, "capturas": []})

# ==============================================================================
# MÓDULO ABM DE JUEGOS (Alta: Admin | Modificación: Admin y Moderador | Baja: Admin)
# ==============================================================================

@app.route('/juego/nuevo', methods=['GET', 'POST'])
@roles_requeridos('admin')
def nuevo_juego():
    """Alta de un nuevo juego en el catálogo (Solo Administrador)."""
    if request.method == 'POST':
        db = get_db()
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash("El nombre del juego es obligatorio.", "danger")
            return redirect(url_for('nuevo_juego'))

        desarrollador = request.form.get('desarrollador', '').strip() or 'Independiente'
        editor = request.form.get('editor', '').strip() or desarrollador
        precio_usd = request.form.get('precio_usd', 0.0, type=float) or 0.0
        descuento = request.form.get('descuento', 0, type=int) or 0
        descuento = max(0, min(100, descuento))

        precio_centavos = int(round(max(0.0, precio_usd) * 100))
        if descuento > 0 and precio_centavos > 0:
            precio_inicial_centavos = int(round(precio_centavos / (1.0 - descuento / 100.0)))
        else:
            precio_inicial_centavos = precio_centavos

        is_free = 1.0 if precio_centavos == 0 else 0.0
        release_date = request.form.get('release_date', '').strip() or 'Próximamente'
        required_age = request.form.get('required_age', 0.0, type=float) or 0.0
        metacritic = request.form.get('metacritic_score', type=float)
        short_desc = request.form.get('short_description', '').strip()
        idiomas_sel = [i.strip() for i in request.form.getlist('idiomas') if i.strip()]
        idiomas = ", ".join(idiomas_sel) if idiomas_sel else 'Español (Latinoamérica), Inglés'

        generos_sel = request.form.getlist('generos')
        generos_str = ", ".join(generos_sel) if generos_sel else "Independiente"

        categorias_sel = request.form.getlist('categorias')
        categorias_str = ", ".join(categorias_sel) if categorias_sel else "Un Jugador"

        plat_win = 1.0 if request.form.get('platforms_windows') else 0.0
        plat_mac = 1.0 if request.form.get('platforms_mac') else 0.0
        plat_linux = 1.0 if request.form.get('platforms_linux') else 0.0

        max_custom = db.execute(
            "SELECT MAX(ID_Juego) FROM juegos WHERE ID_Juego >= ?",
            (CUSTOM_ID_BASE,)
        ).fetchone()[0]
        nuevo_id = (int(max_custom) + 1) if max_custom is not None else CUSTOM_ID_BASE

        db.execute('''
            INSERT INTO juegos (
                ID_Juego, Nombre, Desarrollador, Editor,
                Positiva, Negativa, Propietarios,
                Average_Forever, Average_2Weeks, Median_Forever, Median_2Weeks,
                Precio, Precio_Inicial, Descuento, Jugadores_Simultaneos,
                Release_Date, Required_Age, Is_Free, Short_Description, "Idiomas ",
                Platforms_Windows, Platforms_Mac, Platforms_Linux,
                Metacritic_Score, Recommendations, Logros, Generos, Categorias
            ) VALUES (?, ?, ?, ?, 0, 0, '0 .. 20,000', 0, 0, 0, 0, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
        ''', (
            nuevo_id, nombre, desarrollador, editor,
            precio_centavos, precio_inicial_centavos, descuento,
            release_date, required_age, is_free, short_desc, idiomas,
            plat_win, plat_mac, plat_linux,
            metacritic, generos_str, categorias_str
        ))
        db.commit()
        flash(f"Juego '{nombre}' (#{nuevo_id}) dado de alta exitosamente en el catálogo.", "success")
        return redirect(url_for('detalle_juego', juego_id=nuevo_id))

    return render_template(
        'juego_form.html',
        modo='alta',
        juego=None,
        generos_lista=GENEROS_PRINCIPALES,
        categorias_lista=CATEGORIAS_PRINCIPALES,
        idiomas_lista=IDIOMAS_CATALOGO,
        usuario=session.get('usuario')
    )

@app.route('/juego/<int:juego_id>/editar', methods=['GET', 'POST'])
@roles_requeridos('admin', 'moderador')
def editar_juego(juego_id):
    """Modificación de un juego existente en el catálogo (Admin y Moderador)."""
    db = get_db()
    juego = db.execute(
        'SELECT *, ID_Juego AS id, '
        'ROUND(CAST("Precio" AS REAL) / 100.0, 2) AS precio_usd, '
        'ROUND(CAST("Precio_Inicial" AS REAL) / 100.0, 2) AS precio_inicial_usd '
        'FROM juegos WHERE ID_Juego = ?',
        (juego_id,)
    ).fetchone()

    if not juego:
        flash("El juego que intentás editar no existe.", "warning")
        return redirect(url_for('index'))

    if request.method == 'POST':
        nombre = request.form.get('nombre', '').strip()
        if not nombre:
            flash("El nombre del juego no puede quedar vacío.", "danger")
            return redirect(url_for('editar_juego', juego_id=juego_id))

        desarrollador = request.form.get('desarrollador', '').strip()
        editor = request.form.get('editor', '').strip()
        precio_usd = request.form.get('precio_usd', 0.0, type=float) or 0.0
        descuento = request.form.get('descuento', 0, type=int) or 0
        descuento = max(0, min(100, descuento))

        precio_centavos = int(round(max(0.0, precio_usd) * 100))
        if descuento > 0 and precio_centavos > 0:
            precio_inicial_centavos = int(round(precio_centavos / (1.0 - descuento / 100.0)))
        else:
            precio_inicial_centavos = precio_centavos

        is_free = 1.0 if precio_centavos == 0 else 0.0
        release_date = request.form.get('release_date', '').strip()
        required_age = request.form.get('required_age', 0.0, type=float) or 0.0
        metacritic = request.form.get('metacritic_score', type=float)
        short_desc = request.form.get('short_description', '').strip()
        idiomas_sel = [i.strip() for i in request.form.getlist('idiomas') if i.strip()]
        idiomas = ", ".join(idiomas_sel) if idiomas_sel else (juego['Idiomas '] or 'Español (Latinoamérica), Inglés')

        generos_sel = request.form.getlist('generos')
        generos_str = ", ".join(generos_sel) if generos_sel else (juego['Generos'] or '')

        categorias_sel = request.form.getlist('categorias')
        categorias_str = ", ".join(categorias_sel) if categorias_sel else (juego['Categorias'] or '')

        plat_win = 1.0 if request.form.get('platforms_windows') else 0.0
        plat_mac = 1.0 if request.form.get('platforms_mac') else 0.0
        plat_linux = 1.0 if request.form.get('platforms_linux') else 0.0

        db.execute('''
            UPDATE juegos
            SET Nombre = ?, Desarrollador = ?, Editor = ?,
                Precio = ?, Precio_Inicial = ?, Descuento = ?, Is_Free = ?,
                Release_Date = ?, Required_Age = ?, Metacritic_Score = ?,
                Short_Description = ?, "Idiomas " = ?,
                Platforms_Windows = ?, Platforms_Mac = ?, Platforms_Linux = ?,
                Generos = ?, Categorias = ?
            WHERE ID_Juego = ?
        ''', (
            nombre, desarrollador, editor,
            precio_centavos, precio_inicial_centavos, descuento, is_free,
            release_date, required_age, metacritic,
            short_desc, idiomas,
            plat_win, plat_mac, plat_linux,
            generos_str, categorias_str,
            juego_id
        ))
        db.commit()
        flash(f"Los datos de '{nombre}' fueron actualizados correctamente.", "success")
        return redirect(url_for('detalle_juego', juego_id=juego_id))

    return render_template(
        'juego_form.html',
        modo='edicion',
        juego=juego,
        generos_lista=GENEROS_PRINCIPALES,
        categorias_lista=CATEGORIAS_PRINCIPALES,
        idiomas_lista=IDIOMAS_CATALOGO,
        usuario=session.get('usuario')
    )

@app.route('/juego/<int:juego_id>/eliminar', methods=['POST'])
@roles_requeridos('admin')
def eliminar_juego(juego_id):
    """Baja de un juego del catálogo (Solo Administrador)."""
    db = get_db()
    juego = db.execute("SELECT Nombre FROM juegos WHERE ID_Juego = ?", (juego_id,)).fetchone()
    if not juego:
        flash("El juego que intentás eliminar no existe.", "warning")
        return redirect(url_for('index'))

    db.execute("DELETE FROM juegos WHERE ID_Juego = ?", (juego_id,))
    db.commit()
    flash(f"El juego '{juego['Nombre']}' (#{juego_id}) fue eliminado del catálogo.", "info")
    return redirect(url_for('index'))

# ==============================================================================
# HERRAMIENTA PRIVADA DEL PROGRAMADOR: SIMULADOR Y COMPARADOR DE PRECIOS
# ==============================================================================

@app.route('/comparador', methods=['GET', 'POST'])
def comparador():
    """
    Permite a un programador cargar los datos de su proyecto de videojuego de forma
    privada en su sesión (sin guardarlo en la base de datos pública) y compararlo
    en precio y rendimiento contra los juegos reales de su misma categoría en Steam.
    """
    db = get_db()

    if request.method == 'POST':
        accion = request.form.get('accion', 'simular')
        if accion == 'limpiar':
            session.pop('mi_juego_simulado', None)
            flash("Se limpiaron los datos de tu simulación privada.", "info")
            return redirect(url_for('comparador'))

        nombre_proyecto = request.form.get('nombre_proyecto', '').strip() or 'Mi Proyecto Indie'
        genero = request.form.get('genero', 'Independiente').strip()
        categoria = request.form.get('categoria', 'Un Jugador').strip()
        precio_propuesto = request.form.get('precio_propuesto', 14.99, type=float)
        if precio_propuesto is None or precio_propuesto < 0:
            precio_propuesto = 0.0

        plataformas = []
        if request.form.get('plat_win'):
            plataformas.append('Windows')
        if request.form.get('plat_mac'):
            plataformas.append('macOS')
        if request.form.get('plat_linux'):
            plataformas.append('Linux')
        if not plataformas:
            plataformas = ['Windows']

        descripcion = request.form.get('descripcion', '').strip()

        # Guardamos únicamente en la sesión privada del navegador (NO en SQLite)
        session['mi_juego_simulado'] = {
            'nombre': nombre_proyecto,
            'genero': genero,
            'categoria': categoria,
            'precio_propuesto': round(precio_propuesto, 2),
            'plataformas': plataformas,
            'descripcion': descripcion
        }

    mi_juego = session.get('mi_juego_simulado')
    analisis = None
    referentes = []

    if mi_juego:
        genero_filtro = mi_juego['genero']
        categoria_filtro = mi_juego['categoria']

        # Buscar todos los precios en USD de juegos pagos que coincidan con el género y categoría
        rows_precios = db.execute('''
            SELECT ROUND(CAST("Precio" AS REAL) / 100.0, 2) AS precio_usd
            FROM juegos
            WHERE CAST("Precio" AS REAL) > 0
              AND "Generos" LIKE ?
              AND "Categorias" LIKE ?
            ORDER BY CAST("Precio" AS REAL) ASC
        ''', (f"%{genero_filtro}%", f"%{categoria_filtro}%")).fetchall()

        # Si la combinación exacta tiene muy pocos resultados, ampliamos al género principal
        if len(rows_precios) < 10:
            rows_precios = db.execute('''
                SELECT ROUND(CAST("Precio" AS REAL) / 100.0, 2) AS precio_usd
                FROM juegos
                WHERE CAST("Precio" AS REAL) > 0
                  AND ("Generos" LIKE ? OR "Categorias" LIKE ?)
                ORDER BY CAST("Precio" AS REAL) ASC
            ''', (f"%{genero_filtro}%", f"%{categoria_filtro}%")).fetchall()

        precios = [r['precio_usd'] for r in rows_precios if r['precio_usd'] and r['precio_usd'] > 0]
        total_competidores = len(precios)

        if total_competidores > 0:
            promedio = round(sum(precios) / total_competidores, 2)
            mediana = calcular_percentil(precios, 50)
            p25 = calcular_percentil(precios, 25)
            p75 = calcular_percentil(precios, 75)
            min_p = precios[0]
            max_p = precios[-1]

            tu_precio = mi_juego['precio_propuesto']
            dif_mediana = round(tu_precio - mediana, 2)
            pct_vs_mediana = round(((tu_precio - mediana) / mediana) * 100, 1) if mediana > 0 else 0.0
            menores_o_iguales = sum(1 for p in precios if p <= tu_precio)
            percentil_usuario = round((menores_o_iguales / total_competidores) * 100, 1)

            # Posición porcentual visual dentro de una escala acotada (0 a máx entre P75*1.6 y tu_precio*1.15)
            escala_max = round(max(p75 * 1.6, tu_precio * 1.15, mediana * 2.0, 10.0), 2)
            pos_tu_precio = min(96.0, max(4.0, round((tu_precio / escala_max) * 100, 1)))
            pos_mediana = min(96.0, max(4.0, round((mediana / escala_max) * 100, 1)))
            pos_p25 = min(96.0, max(4.0, round((p25 / escala_max) * 100, 1)))
            pos_p75 = min(96.0, max(4.0, round((p75 / escala_max) * 100, 1)))

            if tu_precio < p25:
                segmento = "Económico / Entrada Agresiva"
                color_segmento = "info"
                recomendacion = (
                    f"Tu precio (${tu_precio:.2f}) está por debajo del 75% de los juegos de esta categoría. "
                    f"Es un valor agresivo para atraer volumen rápido de jugadores, aunque tenés margen para subirlo "
                    f"hacia el rango competitivo (${p25:.2f} a ${mediana:.2f})."
                )
            elif tu_precio <= p75:
                segmento = "Competitivo / Estándar del Mercado"
                color_segmento = "success"
                recomendacion = (
                    f"Tu precio (${tu_precio:.2f}) se ubica justo dentro de la franja estándar del mercado "
                    f"(${p25:.2f} a ${p75:.2f}) donde compite la mayoría de los lanzamientos exitosos de {genero_filtro}."
                )
            else:
                segmento = "Segmento Premium / Alto"
                color_segmento = "warning"
                recomendacion = (
                    f"Tu precio (${tu_precio:.2f}) supera al 75% de los títulos de {genero_filtro} ({categoria_filtro}). "
                    f"Para sostener este valor frente a una mediana de ${mediana:.2f}, el juego necesita mostrar alto "
                    f"valor de producción o podés evaluar lanzarlo cerca de ${p75:.2f}."
                )

            analisis = {
                'total_competidores': total_competidores,
                'promedio': promedio,
                'mediana': mediana,
                'p25': p25,
                'p75': p75,
                'min_p': min_p,
                'max_p': max_p,
                'dif_mediana': dif_mediana,
                'pct_vs_mediana': pct_vs_mediana,
                'percentil_usuario': percentil_usuario,
                'escala_max': escala_max,
                'pos_tu_precio': pos_tu_precio,
                'pos_mediana': pos_mediana,
                'pos_p25': pos_p25,
                'pos_p75': pos_p75,
                'segmento': segmento,
                'color_segmento': color_segmento,
                'recomendacion': recomendacion
            }

            # Obtener los 10 juegos referentes más populares de esa categoría para comparar mano a mano
            referentes = db.execute('''
                SELECT ID_Juego AS id, Nombre, Desarrollador, Propietarios, Positiva, Negativa,
                       Generos, Categorias, Release_Date, Short_Description,
                       ROUND(CAST("Precio" AS REAL) / 100.0, 2) AS precio_usd
                FROM juegos
                WHERE CAST("Precio" AS REAL) > 0
                  AND "Generos" LIKE ?
                  AND "Categorias" LIKE ?
                ORDER BY CAST(Positiva AS INTEGER) DESC
                LIMIT 10
            ''', (f"%{genero_filtro}%", f"%{categoria_filtro}%")).fetchall()

    return render_template(
        'comparador.html',
        mi_juego=mi_juego,
        analisis=analisis,
        referentes=referentes,
        generos_lista=GENEROS_PRINCIPALES,
        categorias_lista=CATEGORIAS_PRINCIPALES,
        usuario=session.get('usuario')
    )

def _listar_imagenes_powerbi():
    """Lista capturas estáticas de Power BI en static/assets_powerbi/ si existen."""
    carpeta = os.path.join(app.root_path, 'static', 'assets_powerbi')
    if not os.path.isdir(carpeta):
        return []
    extensiones = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
    return sorted(
        nombre for nombre in os.listdir(carpeta)
        if os.path.isfile(os.path.join(carpeta, nombre)) and nombre.lower().endswith(extensiones)
    )

_RE_ANIO = re.compile(r'\b(19\d{2}|20\d{2})\b')
_GRANDES_PUBLISHERS = (
    'electronic arts',
    'ubisoft',
    'square enix',
    'sega',
    'capcom',
    'bandai namco',
    '2k',
    'thq nordic',
)


def _normalizar_idiomas_juego(texto_idiomas):
    """Extrae el conjunto de idiomas normalizados presentes en la celda cruda de un juego."""
    if not texto_idiomas:
        return set()
    limpio = str(texto_idiomas)
    limpio = re.sub(r'<br>.*$', '', limpio, flags=re.IGNORECASE)
    limpio = re.sub(r'languages with full audio support.*$', '', limpio, flags=re.IGNORECASE)
    limpio = re.sub(r'con soporte de audio completo.*$', '', limpio, flags=re.IGNORECASE)
    limpio = re.sub(r'^Idiomas\s+', '', limpio, flags=re.IGNORECASE)
    limpio = limpio.replace('<strong>*</strong>', '').replace('*', '')

    idiomas_encontrados = set()
    for parte in limpio.split(','):
        clave = parte.strip().lower()
        if not clave:
            continue
        if "españa" in clave and "américa latina" in clave:
            idiomas_encontrados.add("Español (España)")
            idiomas_encontrados.add("Español (Latinoamérica)")
        elif "portugal" in clave and "brasil" in clave:
            idiomas_encontrados.add("Portugués (Portugal)")
            idiomas_encontrados.add("Portugués (Brasil)")
        elif clave in SINONIMOS_IDIOMAS:
            idiomas_encontrados.add(SINONIMOS_IDIOMAS[clave][0])
        else:
            idiomas_encontrados.add(parte.strip()[:1].upper() + parte.strip()[1:])
    return idiomas_encontrados


def _obtener_metricas_dashboard(db, monetizacion='todos', plataforma='todas', genero=''):
    """
    Calcula KPIs y las series de las 3 hojas del Dashboard BI (TP2) en vivo desde SQLite,
    aplicando opcionalmente los segmentadores de monetización, plataforma y género.
    """
    monetizacion = (monetizacion or 'todos').strip().lower()
    plataforma = (plataforma or 'todas').strip().lower()
    genero = (genero or '').strip()

    where_sql = " WHERE 1=1"
    params = []

    if monetizacion == 'pago':
        where_sql += ' AND COALESCE(CAST("Is_Free" AS REAL), 0) = 0'
    elif monetizacion == 'gratis':
        where_sql += ' AND COALESCE(CAST("Is_Free" AS REAL), 0) = 1'

    if plataforma == 'windows_only':
        where_sql += (
            ' AND COALESCE(CAST("Platforms_Mac" AS REAL), 0) = 0'
            ' AND COALESCE(CAST("Platforms_Linux" AS REAL), 0) = 0'
        )
    elif plataforma == 'multiplataforma':
        where_sql += (
            ' AND (COALESCE(CAST("Platforms_Mac" AS REAL), 0) > 0'
            ' OR COALESCE(CAST("Platforms_Linux" AS REAL), 0) > 0)'
        )

    if genero:
        where_sql += ' AND "Generos" LIKE ?'
        params.append(f"%{genero}%")

    filas = db.execute(f'''
        SELECT
            "Nombre",
            "Desarrollador",
            "Editor",
            CAST("Positiva" AS REAL) AS positiva,
            CAST("Precio" AS REAL) AS precio_centavos,
            CAST("Descuento" AS REAL) AS descuento,
            "Release_Date",
            CAST("Required_Age" AS REAL) AS required_age,
            COALESCE(CAST("Is_Free" AS REAL), 0) AS is_free,
            "Idiomas " AS idiomas_raw,
            COALESCE(CAST("Platforms_Windows" AS REAL), 0) AS plat_win,
            COALESCE(CAST("Platforms_Mac" AS REAL), 0) AS plat_mac,
            COALESCE(CAST("Platforms_Linux" AS REAL), 0) AS plat_linux,
            CAST("Metacritic_Score" AS REAL) AS metascore,
            "Generos"
        FROM juegos
        {where_sql}
    ''', params).fetchall()

    total_juegos = len(filas)
    gratis = 0
    pagos = 0
    exclusivos_win = 0
    multiplataforma = 0
    juegos_windows = 0
    juegos_mac = 0
    juegos_linux = 0

    suma_precio_centavos_todos = 0.0
    suma_precio_usd_pagos = 0.0
    cant_precio_positivo = 0
    max_precio_usd = 0.0
    suma_descuento = 0.0
    suma_positivas = 0.0
    suma_metascore = 0.0
    cant_metascore = 0

    rango_0 = 0
    rango_1_10 = 0
    rango_10_30 = 0
    rango_mas_30 = 0

    por_anio_cant = Counter()
    por_anio_suma_centavos = Counter()

    contador_generos_indiv = Counter()
    contador_generos_combo = Counter()
    contador_desarrolladores = Counter()

    por_edad_cant = Counter()
    por_edad_suma_centavos = Counter()

    # Hoja 2: dispersión Precio vs Metascore agrupada por combinación de Géneros
    scatter_grupos = {}

    # Hoja 3: Autopublicado vs Tradicional e Idiomas
    autopublicados = 0
    distribucion_tradicional = 0
    contador_idiomas_indiv = Counter()
    contador_idiomas_combo = Counter()

    candidatos_top_precio = []

    for f in filas:
        precio_c = f['precio_centavos'] or 0.0
        precio_u = precio_c / 100.0
        is_free_val = 1 if (f['is_free'] or 0) >= 1 else 0

        if is_free_val == 1:
            gratis += 1
        else:
            pagos += 1

        if precio_c <= 0:
            rango_0 += 1
        elif precio_c <= 1000:
            rango_1_10 += 1
        elif precio_c <= 3000:
            rango_10_30 += 1
        else:
            rango_mas_30 += 1

        suma_precio_centavos_todos += precio_c
        if precio_c > 0:
            suma_precio_usd_pagos += precio_u
            cant_precio_positivo += 1
            if precio_u > max_precio_usd:
                max_precio_usd = precio_u
            if f['Nombre']:
                candidatos_top_precio.append((precio_c, f['positiva'] or 0.0, f['Nombre'], round(precio_u, 2)))

        suma_descuento += (f['descuento'] or 0.0)
        suma_positivas += (f['positiva'] or 0.0)

        win = 1 if (f['plat_win'] or 0) > 0 else 0
        mac = 1 if (f['plat_mac'] or 0) > 0 else 0
        lin = 1 if (f['plat_linux'] or 0) > 0 else 0
        juegos_windows += win
        juegos_mac += mac
        juegos_linux += lin

        if mac == 0 and lin == 0:
            exclusivos_win += 1
        else:
            multiplataforma += 1

        # Evolución por año (1997-2026)
        rel = f['Release_Date']
        if rel:
            m_anio = _RE_ANIO.search(str(rel))
            if m_anio:
                anio = int(m_anio.group(1))
                if 1997 <= anio <= 2026:
                    por_anio_cant[anio] += 1
                    por_anio_suma_centavos[anio] += precio_c

        # Géneros (combinación exacta del TP2 e individuales)
        gen_raw = (f['Generos'] or '').strip()
        if gen_raw:
            contador_generos_combo[gen_raw] += 1
            for g_item in gen_raw.split(','):
                g_limpio = g_item.strip()
                if g_limpio:
                    contador_generos_indiv[g_limpio] += 1

        # Desarrollador
        dev_raw = (f['Desarrollador'] or '').strip()
        if dev_raw and dev_raw != '0':
            contador_desarrolladores[dev_raw] += 1

        # Clasificación por edad (Required_Age > 0, igual que en Power BI Hoja 1)
        edad_val = int(round(f['required_age'] or 0))
        if edad_val > 0:
            por_edad_cant[edad_val] += 1
            por_edad_suma_centavos[edad_val] += precio_c

        # Metascore (> 0) y agrupación para Hoja 2
        meta = f['metascore'] or 0.0
        if meta > 0:
            suma_metascore += meta
            cant_metascore += 1
            clave_gen = gen_raw if gen_raw else '(Sin género)'
            grp = scatter_grupos.get(clave_gen)
            if grp is None:
                scatter_grupos[clave_gen] = [1, precio_c, meta]
            else:
                grp[0] += 1
                grp[1] += precio_c
                grp[2] += meta

        # Hoja 3: Tipo de publicación (Autopublicado / Indie vs. Distribución Tradicional)
        ed_raw = (f['Editor'] or '').strip()
        ed_low = ed_raw.lower()
        dev_low = dev_raw.lower()
        es_gran_publisher = any(pub in ed_low for pub in _GRANDES_PUBLISHERS)
        if not es_gran_publisher and dev_low and (dev_low == ed_low or not ed_low or ed_low == 'independiente'):
            autopublicados += 1
        else:
            distribucion_tradicional += 1

        # Hoja 3: Idiomas
        idiomas_raw = (f['idiomas_raw'] or '').strip()
        if idiomas_raw:
            etiqueta_combo = re.sub(r'^Idiomas\s+', '', idiomas_raw, flags=re.IGNORECASE).strip()
            if len(etiqueta_combo) > 38:
                etiqueta_combo = etiqueta_combo[:35] + '...'
            if etiqueta_combo:
                contador_idiomas_combo[etiqueta_combo] += 1
            for idi in _normalizar_idiomas_juego(idiomas_raw):
                contador_idiomas_indiv[idi] += 1

    precio_promedio_centavos = round(suma_precio_centavos_todos / total_juegos, 2) if total_juegos > 0 else 0.0
    precio_promedio_general_usd = round(precio_promedio_centavos / 100.0, 2)
    precio_promedio_usd = round(suma_precio_usd_pagos / cant_precio_positivo, 2) if cant_precio_positivo > 0 else 0.0
    descuento_promedio_pct = round(suma_descuento / total_juegos, 2) if total_juegos > 0 else 0.0
    resenas_positivas_promedio = round(suma_positivas / total_juegos, 2) if total_juegos > 0 else 0.0
    metascore_promedio = round(suma_metascore / cant_metascore, 2) if cant_metascore > 0 else 0.0

    # Series Hoja 1: Evolución anual
    anios_ordenados = sorted(por_anio_cant.keys())
    evolucion_anual = {
        "anios": anios_ordenados,
        "lanzamientos": [por_anio_cant[a] for a in anios_ordenados],
        "precio_promedio_usd": [
            round((por_anio_suma_centavos[a] / por_anio_cant[a]) / 100.0, 2)
            for a in anios_ordenados
        ],
        "precio_promedio_centavos": [
            round(por_anio_suma_centavos[a] / por_anio_cant[a], 2)
            for a in anios_ordenados
        ],
    }

    pct_pagos = round((pagos / total_juegos) * 100, 2) if total_juegos > 0 else 0.0
    pct_gratis = round((gratis / total_juegos) * 100, 2) if total_juegos > 0 else 0.0
    pct_win_only = round((exclusivos_win / total_juegos) * 100, 2) if total_juegos > 0 else 0.0
    pct_multi = round((multiplataforma / total_juegos) * 100, 2) if total_juegos > 0 else 0.0

    top_gen_combo = contador_generos_combo.most_common(12)
    top_gen_indiv = contador_generos_indiv.most_common(12)
    top_devs = contador_desarrolladores.most_common(12)

    edades_ordenadas = sorted(por_edad_cant.keys())
    clasificacion_edad = {
        "edades": edades_ordenadas,
        "labels": [f"+{e} años" for e in edades_ordenadas],
        "cantidades": [por_edad_cant[e] for e in edades_ordenadas],
        "precio_promedio_usd": [
            round((por_edad_suma_centavos[e] / por_edad_cant[e]) / 100.0, 2)
            for e in edades_ordenadas
        ],
        "precio_promedio_centavos": [
            round(por_edad_suma_centavos[e] / por_edad_cant[e], 2)
            for e in edades_ordenadas
        ],
    }

    # Series Hoja 2: Dispersión Precio vs Metascore por género/combinación
    dispersion_precio_metascore = []
    for gen_nombre, (cant_g, suma_p_c, suma_m) in sorted(
        scatter_grupos.items(), key=lambda x: x[1][0], reverse=True
    ):
        prom_c = round(suma_p_c / cant_g, 2)
        prom_u = round(prom_c / 100.0, 2)
        prom_m = round(suma_m / cant_g, 2)
        gen_principal = gen_nombre.split(',')[0].strip() if gen_nombre else 'Otro'
        dispersion_precio_metascore.append({
            "x": prom_u,
            "x_centavos": prom_c,
            "y": prom_m,
            "genero": gen_nombre,
            "genero_principal": gen_principal,
            "cantidad": cant_g,
        })

    # Series Hoja 3: Publicación e Idiomas
    pct_auto = round((autopublicados / total_juegos) * 100, 2) if total_juegos > 0 else 0.0
    pct_trad = round((distribucion_tradicional / total_juegos) * 100, 2) if total_juegos > 0 else 0.0
    top_idi_indiv = contador_idiomas_indiv.most_common(15)
    top_idi_combo = contador_idiomas_combo.most_common(15)

    candidatos_top_precio.sort(key=lambda x: (x[0], x[1]), reverse=True)
    top_10_precios = candidatos_top_precio[:10]

    return {
        "filtros": {
            "monetizacion": monetizacion,
            "plataforma": plataforma,
            "genero": genero,
        },
        # KPIs principales (compatibles con plantilla previa y con los KPIs del TP2)
        "total_juegos": total_juegos,
        "gratis": gratis,
        "pagos": pagos,
        "precio_promedio_usd": precio_promedio_usd,
        "precio_promedio_general_usd": precio_promedio_general_usd,
        "precio_promedio_centavos": precio_promedio_centavos,
        "prom": f"{precio_promedio_usd:.2f}",
        "max_precio_usd": round(max_precio_usd, 2),
        "max_precio": f"{max_precio_usd:.2f}",
        "descuento_promedio_pct": descuento_promedio_pct,
        "resenas_positivas_promedio": resenas_positivas_promedio,
        "metascore_promedio": metascore_promedio,
        "juegos_con_metascore": cant_metascore,
        "juegos_windows": juegos_windows,
        "juegos_mac": juegos_mac,
        "juegos_linux": juegos_linux,
        # Hoja 1: Mercado General y Evolución
        "evolucion_anual": evolucion_anual,
        "monetizacion": {
            "labels": ["Juego Pago", "Juego Gratuito (F2P)"],
            "valores": [pagos, gratis],
            "porcentajes": [pct_pagos, pct_gratis],
        },
        "exclusividad": {
            "labels": ["Exclusivo Windows", "Multiplataforma (Mac / Linux)"],
            "valores": [exclusivos_win, multiplataforma],
            "porcentajes": [pct_win_only, pct_multi],
        },
        "top_generos": {
            "labels": [g for g, _ in top_gen_combo],
            "valores": [c for _, c in top_gen_combo],
            "individuales_labels": [g for g, _ in top_gen_indiv],
            "individuales_valores": [c for _, c in top_gen_indiv],
        },
        "top_desarrolladores": {
            "labels": [d for d, _ in top_devs],
            "valores": [c for _, c in top_devs],
        },
        "clasificacion_edad": clasificacion_edad,
        # Hoja 2: Precio vs. Calidad (Metacritic_Score)
        "dispersion_precio_metascore": dispersion_precio_metascore,
        # Hoja 3: Publicación e Idiomas
        "tipo_publicacion": {
            "labels": ["Autopublicado / Indie", "Distribución Tradicional / Publisher"],
            "valores": [autopublicados, distribucion_tradicional],
            "porcentajes": [pct_auto, pct_trad],
        },
        "top_idiomas": {
            "labels": [i for i, _ in top_idi_indiv],
            "valores": [c for _, c in top_idi_indiv],
            "combinaciones_labels": [i for i, _ in top_idi_combo],
            "combinaciones_valores": [c for _, c in top_idi_combo],
        },
        # Claves adicionales heredadas
        "rangos_valores": [rango_0, rango_1_10, rango_10_30, rango_mas_30],
        "generos_labels": [nombre for nombre, _ in top_gen_indiv[:10]],
        "generos_valores": [cantidad for _, cantidad in top_gen_indiv[:10]],
        "top_juegos_labels": [item[2] for item in top_10_precios],
        "top_juegos_valores": [item[3] for item in top_10_precios],
    }


@app.route('/api/dashboard/metricas')
def api_dashboard_metricas():
    """Endpoint JSON en vivo para actualizar los tableros BI al cambiar segmentadores."""
    db = get_db()
    monetizacion = request.args.get('monetizacion', 'todos')
    plataforma = request.args.get('plataforma', 'todas')
    genero = request.args.get('genero', '')
    metricas = _obtener_metricas_dashboard(
        db,
        monetizacion=monetizacion,
        plataforma=plataforma,
        genero=genero,
    )
    return jsonify(metricas)


@app.route('/dashboard')
def dashboard():
    """Panel analítico BI con las 3 hojas interactivas del TP2 en vivo desde SQLite."""
    db = get_db()
    monetizacion = request.args.get('monetizacion', 'todos')
    plataforma = request.args.get('plataforma', 'todas')
    genero = request.args.get('genero', '')
    metricas = _obtener_metricas_dashboard(
        db,
        monetizacion=monetizacion,
        plataforma=plataforma,
        genero=genero,
    )
    return render_template(
        'dashboard.html',
        imagenes_bi=_listar_imagenes_powerbi(),
        powerbi_embed_url=POWERBI_EMBED_URL,
        generos_lista=GENEROS_PRINCIPALES,
        metricas_json=metricas,
        usuario=session.get('usuario'),
        **metricas
    )

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Inicio de sesión con hash de contraseña de Werkzeug."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        db = get_db()
        user = db.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            session['usuario'] = {
                'id': user['id'],
                'email': user['email'],
                'rol': user['rol']
            }
            flash("¡Bienvenido al sistema DevPrice!", "success")
            return redirect(url_for('index'))
        else:
            flash("Email o contraseña incorrectos.", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    """Cierre de sesión."""
    session.pop('usuario', None)
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
