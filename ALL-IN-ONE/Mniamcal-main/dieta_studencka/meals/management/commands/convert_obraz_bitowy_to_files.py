import base64
import binascii
import re

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from meals.models import ProjektInflacjaMobilePosilki


BASE64_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")


def detect_extension(raw: bytes) -> str:
    if raw.startswith(b"\xFF\xD8\xFF"):
        return "jpg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if raw.startswith(b"GIF8"):
        return "gif"
    if raw.startswith(b"BM"):
        return "bmp"
    if raw.startswith(b"RIFF") and b"WEBP" in raw[:16]:
        return "webp"
    return "bin"


def looks_like_base64(value: str) -> bool:
    if not value or len(value) < 100:
        return False
    if value.startswith(("posilki/", "/media/", "http://", "https://")):
        return False
    if value.startswith("data:image/"):
        return True
    return bool(BASE64_RE.match(value))


def decode_base64_image(value: str) -> bytes | None:
    payload = value.strip()
    if payload.startswith("data:image/"):
        payload = payload.split(",", 1)[1]
    payload = re.sub(r"\s+", "", payload)
    try:
        return base64.b64decode(payload, validate=False)
    except (binascii.Error, ValueError):
        return None


class Command(BaseCommand):
    help = "Convert base64 values from ProjektInflacjaMobilePosilki.obraz_bitowy into files under media/posilki/."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Show what would be changed without saving files.")
        parser.add_argument("--limit", type=int, default=0, help="Maximum number of rows to process (0 = all).")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        qs = ProjektInflacjaMobilePosilki.objects.exclude(obraz_bitowy__isnull=True).exclude(obraz_bitowy="")
        if limit and limit > 0:
            qs = qs[:limit]

        converted = 0
        skipped = 0
        failed = 0

        for meal in qs:
            value = str(meal.obraz_bitowy or "")

            if not looks_like_base64(value):
                skipped += 1
                continue

            raw = decode_base64_image(value)
            if not raw:
                failed += 1
                self.stdout.write(self.style.WARNING(f"[WARN] id={meal.pk}: decode failed"))
                continue

            ext = detect_extension(raw)
            target = f"posilki/posilek_{meal.pk}.{ext}"

            if dry_run:
                converted += 1
                self.stdout.write(f"[DRY] id={meal.pk} -> {target}")
                continue

            if default_storage.exists(target):
                default_storage.delete(target)

            saved_path = default_storage.save(target, ContentFile(raw))
            meal.obraz_bitowy = saved_path
            meal.save(update_fields=["obraz_bitowy"])
            converted += 1
            self.stdout.write(self.style.SUCCESS(f"[OK] id={meal.pk} -> {saved_path}"))

        summary = f"Converted: {converted}, skipped: {skipped}, failed: {failed}, dry_run: {dry_run}"
        self.stdout.write(self.style.SUCCESS(summary))
