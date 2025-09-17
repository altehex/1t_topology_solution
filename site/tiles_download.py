#!/usr/bin/env python3
import os
import requests
import time
import math
from urllib.parse import urlparse


class TileDownloader:
    def __init__(self, base_url="https://tile.openstreetmap.org"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Drone Mesh Dashboard/1.0 (Educational Use)'
        })

    def deg2num(self, lat_deg, lon_deg, zoom):
        """Конвертация координат в номера тайлов"""
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (xtile, ytile)

    def download_tile(self, z, x, y, output_dir="tiles"):
        """Загрузка одного тайла"""
        url = f"{self.base_url}/{z}/{x}/{y}.png"

        # Создание директорий
        tile_dir = os.path.join(output_dir, str(z), str(x))
        os.makedirs(tile_dir, exist_ok=True)

        file_path = os.path.join(tile_dir, f"{y}.png")

        # Если файл уже существует, пропускаем
        if os.path.exists(file_path):
            print(f"Тайл {z}/{x}/{y} уже существует")
            return True

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            with open(file_path, 'wb') as f:
                f.write(response.content)

            print(f"Загружен: {z}/{x}/{y}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"Ошибка загрузки {z}/{x}/{y}: {e}")
            return False

    def download_region(self, lat_min, lat_max, lon_min, lon_max,
                        zoom_min=1, zoom_max=15, output_dir="tiles"):
        """Загрузка региона карты"""

        print(f"Загрузка региона:")
        print(f"  Широта: {lat_min} до {lat_max}")
        print(f"  Долгота: {lon_min} до {lon_max}")
        print(f"  Зум: {zoom_min} до {zoom_max}")

        total_tiles = 0
        downloaded = 0

        for zoom in range(zoom_min, zoom_max + 1):
            # Вычисляем границы тайлов для данного зума
            x_min, y_max = self.deg2num(lat_min, lon_min, zoom)
            x_max, y_min = self.deg2num(lat_max, lon_max, zoom)

            for x in range(x_min, x_max + 1):
                for y in range(y_min, y_max + 1):
                    if self.download_tile(zoom, x, y, output_dir):
                        downloaded += 1
                    total_tiles += 1

                    # Небольшая задержка чтобы не перегружать сервер
                    time.sleep(0.1)

        print(f"\nЗагрузка завершена: {downloaded}/{total_tiles} тайлов")


def main():
    downloader = TileDownloader()

    # Пример: Загрузка Московской области
    # Измените координаты под вашу область
    lat_center = 55.7558  # Москва
    lon_center = 37.6176

    # Радиус в градусах (примерно 50км)
    radius = 0.5

    downloader.download_region(
        lat_min=lat_center - radius,
        lat_max=lat_center + radius,
        lon_min=lon_center - radius,
        lon_max=lon_center + radius,
        zoom_min=14,  # Мелкий масштаб
        zoom_max=20,  # Крупный масштаб
        output_dir="tiles"
    )


if __name__ == "__main__":
    main()