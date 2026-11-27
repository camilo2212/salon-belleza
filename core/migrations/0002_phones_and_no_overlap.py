from django.db import migrations

CONSTRAINT = "core_no_overlapping_appointments"


def normalize_existing_phones(apps, schema_editor):
    """Unifica números escritos de formas distintas (+57300..., 300...) y fusiona duplicadas."""
    from core.phone import normalize_phone

    Customer = apps.get_model("core", "Customer")
    Appointment = apps.get_model("core", "Appointment")
    kept = {}
    for customer in Customer.objects.order_by("id"):
        phone = normalize_phone(customer.phone)
        if phone in kept:
            Appointment.objects.filter(customer=customer).update(customer=kept[phone])
            customer.delete()
            continue
        kept[phone] = customer
        if customer.phone != phone:
            customer.phone = phone
            customer.save(update_fields=["phone"])


def add_overlap_constraint(apps, schema_editor):
    """Solo PostgreSQL: la base de datos misma impide dos citas activas que se crucen."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        f"ALTER TABLE core_appointment ADD CONSTRAINT {CONSTRAINT} "
        "EXCLUDE USING gist (tstzrange(\"start\", \"end\") WITH &&) "
        "WHERE (status IN ('pending', 'confirmed', 'completed'))"
    )


def drop_overlap_constraint(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(f"ALTER TABLE core_appointment DROP CONSTRAINT IF EXISTS {CONSTRAINT}")


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.RunPython(normalize_existing_phones, migrations.RunPython.noop),
        migrations.RunPython(add_overlap_constraint, drop_overlap_constraint),
    ]
