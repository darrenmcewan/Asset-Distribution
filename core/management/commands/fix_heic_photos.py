"""
One-time management command to convert broken HEIC files that were saved
as raw data (before pillow-heif was installed) into proper JPEGs.
"""

import logging
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from PIL import Image

from core.models import AssetPhoto

logger = logging.getLogger(__name__)

HEIC_MAGIC = b'ftyp'


class Command(BaseCommand):
    help = 'Convert previously-uploaded HEIC photos that were saved as raw data into JPEG'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only report which files would be converted without changing anything',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        converted = 0
        skipped = 0

        for photo in AssetPhoto.objects.all():
            if not photo.image:
                continue

            try:
                photo.image.open('rb')
                header = photo.image.read(12)
                photo.image.close()
            except Exception as e:
                self.stderr.write(f'  Could not read {photo.image.name}: {e}')
                skipped += 1
                continue

            # HEIC files have 'ftyp' at byte offset 4
            if len(header) >= 8 and header[4:8] == HEIC_MAGIC:
                self.stdout.write(f'  Found HEIC: {photo.image.name}')

                if dry_run:
                    converted += 1
                    continue

                try:
                    photo.image.open('rb')
                    raw_data = photo.image.read()
                    photo.image.close()

                    buf = BytesIO(raw_data)
                    img = Image.open(buf)
                    img.load()

                    # Strip EXIF by copying pixel data to a clean image
                    clean = Image.new(img.mode, img.size)
                    clean.putdata(list(img.getdata()))
                    clean = clean.convert('RGB')
                    clean.thumbnail(
                        (AssetPhoto.MAX_DIMENSION, AssetPhoto.MAX_DIMENSION)
                    )

                    out_buf = BytesIO()
                    clean.save(
                        out_buf, format='JPEG',
                        quality=AssetPhoto.JPEG_QUALITY, optimize=True,
                    )
                    out_buf.seek(0)

                    # Build new filename with .jpg extension
                    old_name = Path(photo.image.name).stem
                    new_name = f'assets/{old_name}.jpg'

                    # Delete old file
                    old_path = photo.image.path
                    photo.image.save(new_name, ContentFile(out_buf.read()), save=True)

                    # Remove the old raw HEIC file from disk
                    old_file = Path(old_path)
                    if old_file.exists():
                        old_file.unlink()

                    converted += 1
                    self.stdout.write(self.style.SUCCESS(
                        f'  Converted: {old_name} -> {photo.image.name}'
                    ))
                except Exception as e:
                    self.stderr.write(self.style.ERROR(
                        f'  Failed to convert {photo.image.name}: {e}'
                    ))
                    skipped += 1
            else:
                skipped += 1

        action = 'Would convert' if dry_run else 'Converted'
        self.stdout.write(self.style.SUCCESS(
            f'\nDone. {action} {converted} file(s), skipped {skipped}.'
        ))
