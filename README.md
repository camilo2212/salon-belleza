# Salón de Belleza

Página web del salón: catálogo de servicios y productos, y reserva de citas en línea.

- **Backend** (carpeta raíz): Django + Django REST Framework. Incluye el panel de administración.
- **Frontend** (`frontend/`): React + Vite. Es la página que ven las clientas.

## Qué hace

- Panel de administración en `/admin/` para servicios, productos, clientas y citas.
- Página pública con servicios, productos y reserva sin crear cuenta (nombre + WhatsApp).
- Una sola agenda (la dueña atiende sola), de 8 am a 8 pm, sin cruces de citas.
  Horario y días cerrados: `config/settings.py` (`SALON_OPEN`, `SALON_CLOSE`, `SALON_CLOSED_WEEKDAYS`).
- API: `GET /api/services/`, `GET /api/products/`, `GET /api/availability/?service=1&date=2026-12-01`,
  `POST /api/appointments/` (`name`, `phone`, `service`, `start`).

## Puesta en marcha

Requisitos: Python 3.11 o superior, Node.js 20.19 o superior (o 22.12+), Git y VS Code.
Se usan **dos terminales**: una para el backend y otra para el frontend.

### Terminal 1: backend

```bash
python -m venv .venv
source .venv/Scripts/activate    # Git Bash en Windows (en Linux/Mac: .venv/bin/activate)
                                 # PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo       # servicios y productos de ejemplo (opcional)
winpty python manage.py createsuperuser   # en Git Bash; en otras terminales sin "winpty"
python manage.py runserver
```

Panel: http://127.0.0.1:8000/admin/

### Terminal 2: frontend

```bash
cd frontend
npm install
npm run dev
```

Página: http://localhost:5173/ (Vite reenvía `/api` al backend, no hay que configurar nada más).

### Personalizar la página

Nombre del salón, WhatsApp, dirección y horario se cambian en `frontend/src/config.js`.
- Reglas de la reserva pública: no se aceptan fechas pasadas, solo horas de la cuadrícula
  (cada `SALON_SLOT_STEP_MINUTES`) y cada teléfono puede tener como máximo
  `SALON_MAX_OPEN_BOOKINGS_PER_PHONE` citas pendientes/confirmadas a la vez.
Colores y tipografías, en `frontend/src/styles.css` (variables al inicio del archivo).

## Panel de administración (la agenda)

En `/admin/` → **Citas** se abre directamente en las citas de hoy en adelante. Arriba a la derecha hay
filtros rápidos: Próximas, Hoy, Mañana, Próximos 7 días, Pasadas y Todas. Cada cita muestra su estado
en color y un enlace **Confirmar por WhatsApp** que abre el chat con el mensaje ya escrito.
Acciones masivas: confirmar, cancelar, marcar como realizada o como "No asistió".

## Acceso de la dueña (precios, productos y clientas)

Al hacer `python manage.py migrate` se crea el grupo **Dueña**: puede manejar servicios, productos,
clientas y citas, y **no** ve usuarios ni configuración. Para darle acceso a la dueña:

1. Entra a `/admin/` con tu usuario administrador → **Usuarios** → **Añadir usuario**.
2. Escribe usuario y contraseña → **Guardar y continuar editando**.
3. Marca **Es staff** y, en **Grupos**, pasa **Dueña** a la columna de la derecha → **Guardar**.

Ella entra por la misma dirección (`/admin/`) y solo ve lo suyo:
- **Servicios**: cambia precio, duración y si se muestra, directo en la lista (casilla y botón "Guardar" al final).
- **Productos**: foto, precio y existencias en la lista; filtros "Agotados" y "Pocas".
- **Clientas**: visitas, última cita, veces que no asistió, WhatsApp y el historial dentro de cada ficha.
- **Citas**: la agenda del día.

## Aviso de reservas nuevas por correo

Define estas variables de entorno (en desarrollo, sin `EMAIL_HOST`, el correo se imprime en la terminal del backend):

| Variable | Ejemplo |
|---|---|
| `SALON_NOTIFY_EMAILS` | `duena@gmail.com` (varios, separados por coma) |
| `EMAIL_HOST` | `smtp.gmail.com` |
| `EMAIL_HOST_USER` | `duena@gmail.com` |
| `EMAIL_HOST_PASSWORD` | contraseña de aplicación de Google (no la normal) |
| `SALON_NAME` | `Salón Mi Nombre` (sale en los mensajes de WhatsApp) |

## Doble reserva

Con PostgreSQL (producción) la base de datos misma impide que dos citas activas se crucen, aunque dos
personas reserven a la vez. Con SQLite (desarrollo) se valida en el código, que alcanza para una sola persona probando.
Los teléfonos se guardan sin indicativo (`+57 300 123 4567` y `3001234567` son la misma clienta).

## Pruebas del backend

```bash
python manage.py test
```

## Variables de entorno (producción)

Backend:

| Variable | Para qué |
|---|---|
| `DEBUG` | `0` en producción |
| `SECRET_KEY` | clave secreta larga y aleatoria |
| `DATABASE_URL` | conexión a PostgreSQL |
| `ALLOWED_HOSTS` | dominio del backend, separado por comas |
| `CSRF_TRUSTED_ORIGINS` | `https://tu-backend.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | dominio del frontend |

Frontend: `VITE_API_URL` con la dirección del backend (ver `frontend/.env.example`).

## Hoja de ruta

1. Backend base (hecho)
2. Frontend: catálogo y reserva (hecho)
3. Despliegue en la nube
4. Caja diaria, historial de clientas, recordatorios por WhatsApp
