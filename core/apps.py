from django.apps import AppConfig
from django.db.models.signals import post_migrate

OWNER_GROUP = "Dueña"

# Lo que puede hacer la dueña: manejar servicios, productos, clientas y citas.
# No ve usuarios, grupos ni nada de configuración técnica.
OWNER_PERMISSIONS = [
    f"{action}_{model}"
    for model, actions in {
        "service": ("view", "add", "change", "delete"),
        "product": ("view", "add", "change", "delete"),
        "customer": ("view", "add", "change", "delete"),
        "appointment": ("view", "add", "change"),
    }.items()
    for action in actions
]


def ensure_owner_group(sender, **kwargs):
    """Crea el grupo "Dueña" con sus permisos la primera vez (y no pisa cambios posteriores)."""
    from django.contrib.auth.models import Group, Permission

    perms = Permission.objects.filter(
        content_type__app_label="core", codename__in=OWNER_PERMISSIONS
    )
    if perms.count() < len(OWNER_PERMISSIONS):
        return  # los permisos aún no existen; se reintenta en el próximo migrate
    group, created = Group.objects.get_or_create(name=OWNER_GROUP)
    if created:
        group.permissions.set(perms)


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Salón"

    def ready(self):
        post_migrate.connect(ensure_owner_group, sender=self)
