import os
import time
import aiohttp
from urllib.parse import urlparse

async def download_file(url: str, dest_dir: str) -> str:
    """
    Асинхронно завантажує файл за посиланням.
    Повертає повний шлях до збереженого файлу.
    """
    # Створюємо папку, якщо немає
    os.makedirs(dest_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                raise Exception(f"HTTP Error: {response.status} while downloading")

            # Спробуємо отримати ім'я файлу з заголовків (Content-Disposition)
            filename = None
            if "Content-Disposition" in response.headers:
                cd = response.headers["Content-Disposition"]
                if "filename=" in cd:
                    # Витягуємо ім'я (простий парсинг)
                    filename = cd.split("filename=")[1].strip('"').strip("'")
            
            # Якщо заголовок пустий, пробуємо взяти з URL
            if not filename:
                path = urlparse(url).path
                filename = os.path.basename(path)

            # Якщо все ще немає імені (наприклад, корінь сайту), генеруємо своє
            if not filename or len(filename) < 3:
                filename = f"import_{int(time.time())}.xlsx"

            # Очищаємо ім'я від сміття та шляхів
            filename = os.path.basename(filename)
            filepath = os.path.join(dest_dir, filename)

            # Записуємо файл шматками по 64KB (Memory Safe)
            with open(filepath, 'wb') as f:
                async for chunk in response.content.iter_chunked(64 * 1024):
                    f.write(chunk)

            return filepath