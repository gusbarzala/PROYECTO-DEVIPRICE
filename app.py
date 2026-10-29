import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'devprice_clave_secreta_fts18'
DATABASE = 'database.db'

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
    """Página principal con catálogo de juegos, búsqueda y filtros."""
    db = get_db()
    col_name, col_price, all_cols = get_juegos_columns(db)
    
    # Parámetros de búsqueda y filtrado
    q = request.args.get('q', '').strip()
    max_price = request.args.get('max_price', type=float)
    page = request.args.get('page', 1, type=int)
    per_page = 20
    offset = (page - 1) * per_page

    query = "SELECT * FROM juegos WHERE 1=1"
    params = []

    if q and col_name:
        query += f' AND "{col_name}" LIKE ?'
        params.append(f"%{q}%")
    
    if max_price is not None and col_price:
        query += f' AND CAST("{col_price}" AS REAL) <= ?'
        params.append(max_price)

    # Consulta total de resultados para la paginación
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    total_juegos = db.execute(count_query, params).fetchone()[0]

    # Ordenar según la columna detectada
    if col_price:
        query += f' ORDER BY CAST("{col_price}" AS REAL) ASC LIMIT ? OFFSET ?'
    else:
        query += " ORDER BY id ASC LIMIT ? OFFSET ?"
    
    params.extend([per_page, offset])

    juegos = db.execute(query, params).fetchall()
    total_paginas = (total_juegos + per_page - 1) // per_page if total_juegos > 0 else 1

    return render_template(
        'index.html',
        juegos=juegos,
        q=q,
        max_price=max_price,
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
    juego = db.execute("SELECT * FROM juegos WHERE id = ?", (juego_id,)).fetchone()
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