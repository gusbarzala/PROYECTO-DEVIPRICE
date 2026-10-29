import sqlite3
import pandas as pd
from werkzeug.security import generate_password_hash

def poblar_base_datos():
    # 1. Conectar a la base de datos (se crea automáticamente si no existe)
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    print("Creando tablas...")

    # 2. Crear tabla de usuarios
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL
        )
    ''')

    # 3. Insertar los 3 usuarios del proyecto (Admin, Moderador, Programador)
    usuarios = [
        ('admin@devprice.com', generate_password_hash('123'), 'admin'),
        ('moderador@devprice.com', generate_password_hash('123'), 'moderador'),
        ('programador@devprice.com', generate_password_hash('123'), 'programador')
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO usuarios (email, password_hash, rol) 
        VALUES (?, ?, ?)
    ''', usuarios)

    # 4. Leer el Excel de Steam Games y cargarlo en la tabla 'juegos'
    try:
        # Ajustá el nombre/ruta de tu archivo Excel si está en una subcarpeta
        df = pd.read_excel('steam_games.xlsx', sheet_name=0) 
        
        # Cargar los 23.100 registros en SQLite
        df.to_sql('juegos', conn, if_exists='replace', index=False)
        print("¡Éxito! Se cargaron los juegos del Excel en la tabla 'juegos'.")
    except Exception as e:
        print(f"Aviso: No se pudo leer el Excel directamente ({e}). Se crearon las tablas de usuarios.")

    conn.commit()
    conn.close()
    print("Base de datos generada exitosamente.")

if __name__ == '__main__':
    poblar_base_datos()