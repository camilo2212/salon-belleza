from django.core.management.base import BaseCommand

from core.models import Product, Service


class Command(BaseCommand):
    help = "Crea servicios y productos de ejemplo para probar la app."

    def handle(self, *args, **options):
        services = [
            ("Corte de cabello", 45, 25000),
            ("Tinte completo", 120, 90000),
            ("Manicure", 60, 30000),
            ("Pedicure", 60, 35000),
            ("Peinado", 60, 40000),
        ]
        for name, minutes, price in services:
            Service.objects.get_or_create(
                name=name, defaults={"duration_minutes": minutes, "price": price}
            )
        products = [
            ("Shampoo reparador", 28000, 10),
            ("Acondicionador", 26000, 8),
            ("Esmalte", 9000, 25),
        ]
        for name, price, stock in products:
            Product.objects.get_or_create(name=name, defaults={"price": price, "stock": stock})
        self.stdout.write(self.style.SUCCESS("Datos de ejemplo creados."))
