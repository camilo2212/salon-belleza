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
