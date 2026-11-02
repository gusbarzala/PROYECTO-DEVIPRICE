import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'devprice_clave_secreta_fts18'
DATABASE = 'database.db'

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
        idiomas = request.form.get('idiomas', '').strip() or 'Español, Inglés'

        generos_sel = request.form.getlist('generos')
        generos_str = ", ".join(generos_sel) if generos_sel else "Independiente"

        categorias_sel = request.form.getlist('categorias')
        categorias_str = ", ".join(categorias_sel) if categorias_sel else "Un Jugador"

        plat_win = 1.0 if request.form.get('platforms_windows') else 0.0
        plat_mac = 1.0 if request.form.get('platforms_mac') else 0.0
        plat_linux = 1.0 if request.form.get('platforms_linux') else 0.0

        max_row = db.execute("SELECT COALESCE(MAX(ID_Juego), 3000000) FROM juegos").fetchone()
        nuevo_id = int(max_row[0]) + 10

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
        idiomas = request.form.get('idiomas', '').strip()

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
                       Generos, Categorias,
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
