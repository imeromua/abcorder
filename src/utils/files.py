import os
import time
import asyncio
import gdown
from urllib.parse import urlparse
from loguru import logger

async def download_file(url: str, dest_dir: str) -> str:
    """
    Асинхронно завантажує файл, використовуючи gdown.
    Це найнадійніший спосіб для Google Drive.
    """
    os.makedirs(dest_dir, exist_ok=True)

    # Генеруємо тимчасове ім'я, бо gdown визначить справжнє сам (або використає це)
    # gdown вміє брати ім'я з метаданих файлу
    timestamp = int(time.time())
    temp_name = f"import_{timestamp}.xlsx"
    output_path = os.path.join(dest_dir, temp_name)

    logger.info(f"⬇️ Починаю завантаження через gdown: {url}")

    try:
        # Запускаємо gdown в окремому потоці, щоб не блокувати бота
        # fuzzy=True допомагає розпізнати ID файлу, навіть якщо URL трохи кривий
        saved_path = await asyncio.to_thread(
            gdown.download, 
            url=url, 
            output=output_path, 
            quiet=True, 
            fuzzy=True
        )
        
        if not saved_path:
            raise Exception("gdown не зміг завантажити файл (повернув None).")
            
        logger.info(f"✅ Файл успішно завантажено: {saved_path}")
        return saved_path

    except Exception as e:
        logger.error(f"❌ Помилка gdown: {e}")
        # Часто помилка виникає через права доступу
        if "permission" in str(e).lower() or "denied" in str(e).lower():
            raise Exception("Google Drive: Доступ заборонено. Перевірте, чи файл відкритий для 'Anyone with the link'.")
        raise e