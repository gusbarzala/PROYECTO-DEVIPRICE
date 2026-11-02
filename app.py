import sqlite3
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

def get_juegos_columns(db):
    """Detecta dinámicamente los nombres de las columnas en la tabla juegos."""
    cursor = db.execute("PRAGMA table_info(juegos)")
    cols = [row['name'] for row in cursor.fetchall()]
    
    # Buscar columna de nombre
    col_name = next((c for c in cols if c.lower() in ['name', 'nombre', 'title', 'juego', 'titulo']), cols[1] if len(cols) > 1 else 'id')
    
    # Buscar columna de precio
    col_price = next((c for c in cols if 'price' in c.lower() or 'precio' in c.lower()), None)
    
    return col_name, col_price, cols

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
