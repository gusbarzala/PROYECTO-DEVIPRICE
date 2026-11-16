# 🎮 DevPrice - Plataforma web de catálogo, análisis BI y referencia de precios de juegos de Steam

## 📝 Descripción del Proyecto
**DevPrice** es una aplicación web interactiva desarrollada en **Python (Flask)** y **SQLite** sobre un catálogo de **23.100 registros** de videojuegos de Steam (`22.608` `ID_Juego` distintos). La plataforma unifica la exploración del mercado, un módulo **ABM** con control de acceso por roles (**RBAC**), un **simulador/comparador de precios** por percentiles y un **dashboard BI interactivo** conectado en vivo a la base de datos.

---

## 🛠️ Tecnologías Utilizadas
* **Backend:** Python, Flask, Werkzeug, SQLite (`database.db`).
* **Frontend:** HTML5, Jinja2, Bootstrap, CSS (`transitions.css`), Chart.js.
* **Procesamiento de Datos y BI:** Pandas, openpyxl (`seed.py` sobre `steam_games.xlsx`) y Power BI (reporte en Power BI Service + láminas de respaldo).

---

## 🚀 Funcionalidades
* 🔍 **Catálogo y búsqueda paginada (`/`):** Filtrado por título, precio máximo y ordenamiento dinámico con paginación sobre 23.100 registros.
* 🎮 **Ficha de detalle (`/juego/<id>`):** Información completa del título y galería de capturas HD consultada vía `/api/juego/<id>/capturas` (Steam `appdetails` para IDs reales).
* 📊 **Dashboard BI interactivo (`/dashboard`):** 3 hojas analíticas reconstruidas en Chart.js conectadas en vivo a `database.db` mediante `GET /api/dashboard/metricas`, con segmentadores dinámicos (`Monetización`, `Plataforma`, `Género`), 8 tarjetas KPI, enlace a Power BI Service (con soporte opcional `POWERBI_EMBED_URL`) y láminas de respaldo con zoom.
* ⚖️ **Simulador / Comparador de precios (`/comparador`):** Evaluación de precios con percentiles (`P25`–`P75`) y títulos referentes del mercado almacenados en sesión.
* 🛠️ **Módulo ABM con RBAC (`/juego/nuevo`, `/juego/<id>/editar`, `/juego/<id>/eliminar`):** Alta, baja y modificación de juegos (IDs propios `>= 90000000`) con permisos diferenciados por rol.
* 🔐 **Autenticación y roles (`/login`, `/logout`):** Validación contra hashes en SQLite (`admin`, `moderador`, `programador`).

---

## 📁 Estructura del Proyecto
```text
PROYECTO-DEVIPRICE/
├── static/
│   ├── assets_powerbi/
│   │   ├── powerbi-tablero-1.png
│   │   ├── powerbi-tablero-2.png
│   │   └── powerbi-tablero-3.png
│   ├── css/
│   │   └── transitions.css
│   ├── img/
│   │   ├── favicon.png
│   │   ├── logo.png
│   │   └── logo_with_bg.png
│   └── favicon.ico
├── templates/
│   ├── _navbar.html
│   ├── comparador.html
│   ├── dashboard.html
│   ├── detalle.html
│   ├── index.html
│   ├── juego_form.html
│   └── login.html
├── app.py
├── database.db
├── README.md
├── requirements.txt
├── seed.py
└── steam_games.xlsx
```

---

## ▶️ Instalación y Ejecución
1. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```
2. *(Opcional)* Regenerar `database.db` desde `steam_games.xlsx` (el repositorio ya incluye la base poblada):
   ```bash
   python seed.py
   ```
3. Ejecutar la aplicación:
   ```bash
   python app.py
   ```
4. Abrir en el navegador `http://127.0.0.1:5000` (el dashboard BI está en `http://127.0.0.1:5000/dashboard`).

### Usuarios demo (RBAC)
| Rol | Email | Contraseña | Permisos principales |
| :--- | :--- | :--- | :--- |
| `admin` | `admin@devprice.com` | `123` | Acceso total (Alta, Baja y Modificación) |
| `moderador` | `moderador@devprice.com` | `123` | Edición de juegos existentes |
| `programador` | `programador@devprice.com` | `123` | Consulta, comparador y dashboard BI |
