from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from api.ampc import default_greenhouse
from api.models import Alert, Device, DeviceCommand, DeviceState, SensorData


class Command(BaseCommand):
    help = 'Khởi tạo thiết bị và seed một ít dữ liệu cho hôm nay, tất cả trước 15:00.'

    def handle(self, *args, **options):
        now_local = timezone.localtime()
        today = now_local.date()
        tz = timezone.get_current_timezone()
        greenhouse = default_greenhouse()

        controller, _ = Device.objects.get_or_create(
            greenhouse=greenhouse,
            code='esp32-main',
            defaults={
                'name': 'ESP32 Main',
                'device_type': Device.DeviceType.CONTROLLER,
                'status': Device.DeviceStatus.ONLINE,
            },
        )
        fan, _ = Device.objects.get_or_create(
            greenhouse=greenhouse,
            code='fan-1',
            defaults={
                'name': 'Quạt thông gió',
                'device_type': Device.DeviceType.FAN,
                'status': Device.DeviceStatus.OFFLINE,
            },
        )
        pump, _ = Device.objects.get_or_create(
            greenhouse=greenhouse,
            code='pump-1',
            defaults={
                'name': 'Máy bơm tưới',
                'device_type': Device.DeviceType.PUMP,
                'status': Device.DeviceStatus.OFFLINE,
            },
        )
        light, _ = Device.objects.get_or_create(
            greenhouse=greenhouse,
            code='light-1',
            defaults={
                'name': 'Đèn chiếu sáng',
                'device_type': Device.DeviceType.LIGHT,
                'status': Device.DeviceStatus.OFFLINE,
            },
        )
        mist, _ = Device.objects.get_or_create(
            greenhouse=greenhouse,
            code='mist-1',
            defaults={
                'name': 'Máy phun sương',
                'device_type': Device.DeviceType.MIST,
                'status': Device.DeviceStatus.OFFLINE,
            },
        )

        for device, is_on in [
            (controller, True),
            (fan, False),
            (pump, False),
            (light, False),
            (mist, False),
        ]:
            DeviceState.objects.update_or_create(
                device=device,
                defaults={
                    'is_on': is_on,
                    'desired_on': is_on,
                    'last_command': '',
                    'last_value': 'on' if is_on else 'off',
                },
            )

        Alert.objects.all().delete()
        DeviceCommand.objects.all().delete()
        SensorData.objects.all().delete()

        samples = [
            ("08:10", Decimal("27.8"), Decimal("74.0"), Decimal("32.0"), Decimal("48.0"), 180),
            ("09:00", Decimal("28.4"), Decimal("72.5"), Decimal("38.0"), Decimal("46.5"), 220),
            ("09:50", Decimal("29.1"), Decimal("70.8"), Decimal("44.0"), Decimal("44.0"), 260),
            ("10:40", Decimal("30.0"), Decimal("68.0"), Decimal("55.0"), Decimal("41.5"), 320),
            ("11:30", Decimal("31.0"), Decimal("65.5"), Decimal("67.0"), Decimal("39.0"), 410),
            ("12:20", Decimal("31.8"), Decimal("62.0"), Decimal("78.0"), Decimal("36.5"), 520),
            ("13:10", Decimal("32.2"), Decimal("60.0"), Decimal("83.0"), Decimal("34.0"), 610),
            ("14:00", Decimal("31.6"), Decimal("61.8"), Decimal("76.0"), Decimal("33.0"), 560),
            ("14:50", Decimal("30.9"), Decimal("63.5"), Decimal("69.0"), Decimal("31.5"), 470),
        ]

        created = []
        for hhmm, temp, hum, light_pct, soil, mq135_ppm in samples:
            hour, minute = map(int, hhmm.split(":"))
            dt = timezone.make_aware(datetime.combine(today, time(hour, minute)), tz)

            reading = SensorData.objects.create(
                greenhouse=greenhouse,
                temperature=temp,
                humidity=hum,
                light=light_pct,
                soil_moisture=soil,
                payload={
                    'source': 'seed_demo',
                    'mq135_ppm': mq135_ppm,
                },
                recorded_at=dt,
                received_at=dt,
            )
            created.append(reading)

        latest = created[-1]

        controller.status = Device.DeviceStatus.ONLINE
        controller.last_seen_at = latest.recorded_at
        controller.save(update_fields=['status', 'last_seen_at', 'updated_at'])

        self.stdout.write(
            self.style.SUCCESS(
                f'Đã seed {len(created)} bản ghi cho ngày {today.isoformat()}, bản ghi cuối lúc 14:50.'
            )
        )
