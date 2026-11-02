# 🎮 DevPrice - Plataforma Web de Catálogo y Precios de Juegos de Steam

## 📝 Descripción del Proyecto
DevPrice es una aplicación web interactiva desarrollada en **Python (Flask)** y **SQLite** que procesa y gestiona un catálogo de 23.100 juegos de la plataforma Steam. La plataforma permite la búsqueda dinámica de productos, filtrado por precio máximo, navegación paginada y autenticación de usuarios.

---

## 🛠️ Tecnologías Utilizadas
* **Backend:** Python, Flask, SQLite3, Werkzeug (criptografía y hash de contraseñas).
* **Frontend:** HTML5, Bootstrap 5 (diseño responsivo estilo Steam), Jinja2.
* **Procesamiento de Datos:** Pandas, OpenPyXL.

---

## 🚀 Funcionalidades
* 🔍 **Búsqueda de juegos:** Filtrado directo por nombre de título.
* 💰 **Filtro por precio:** Selección por valor máximo ordenado de menor a mayor costo.
* 📄 **Paginación:** Manejo ágil de 20 juegos por página sobre 23.100 registros.
* 🔐 **Seguridad:** Inicio y cierre de sesión con validación de credenciales en base de datos.

---

## 📁 Estructura del Proyecto
```text
PROYECTO_DEVPRICE/
├── templates/
│   ├── index.html
│   ├── login.html
│   └── detalle.html
├── app.py
├── seed.py
├── database.db
└── steam_games.xlsx
