# Salón de Belleza - Backend

API y panel de administración para el salón. Django + Django REST Framework.

## Qué hace (Fase 1)

- Panel de administración en `/admin/` para servicios, productos, clientas y citas.
- API pública para el frontend:
  - `GET /api/services/` servicios activos
  - `GET /api/products/` productos visibles
  - `GET /api/availability/?service=1&date=2026-12-01` horas libres
  - `POST /api/appointments/` reservar (`name`, `phone`, `service`, `start`)
- Una sola agenda (la dueña atiende sola), de 8 am a 8 pm, sin cruces de citas.
  El horario se cambia en `config/settings.py` (`SALON_OPEN`, `SALON_CLOSE`, `SALON_CLOSED_WEEKDAYS`).

## Puesta en marcha en VS Code

Requisitos: Python 3.11 o superior, Git y VS Code.

```bash
# 1. Entorno virtual
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1

# 2. Dependencias
pip install -r requirements.txt

# 3. Base de datos y usuario administrador
python manage.py migrate
python manage.py createsuperuser

# 4. Datos de ejemplo (opcional) y servidor
python manage.py seed_demo
python manage.py runserver
```

Abre http://127.0.0.1:8000/admin/ para el panel y http://127.0.0.1:8000/api/services/ para la API.

En VS Code: instala las extensiones recomendadas cuando te las sugiera, elige el intérprete
`.venv` (Ctrl+Shift+P > "Python: Select Interpreter"), y usa F5 para depurar el servidor
o `Terminal > Run Task` para migrar y crear el admin.

## Pruebas

```bash
python manage.py test
```

## Variables de entorno (producción)

| Variable | Para qué |
|---|---|
| `DEBUG` | `0` en producción |
| `SECRET_KEY` | clave secreta larga y aleatoria |
| `DATABASE_URL` | conexión a PostgreSQL |
| `ALLOWED_HOSTS` | dominio del backend, separado por comas |
| `CSRF_TRUSTED_ORIGINS` | `https://tu-backend.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | dominio del frontend |

## Hoja de ruta

1. Backend base (esta fase)
2. Frontend en React: catálogo y reserva
3. Despliegue en la nube
4. Caja diaria, historial de clientas, recordatorios por WhatsApp
