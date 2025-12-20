import re

def transform_drive_url(url: str) -> str | None:
    """
    Перетворює посилання Google Drive у пряме посилання на завантаження.
    Підтримує:
    1. Звичайні файли (Drive) -> /uc?export=download
    2. Google Таблиці (Sheets) -> /export?format=xlsx
    """
    # Патерни для пошуку ID
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"/spreadsheets/d/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)"
    ]

    file_id = None
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            file_id = match.group(1)
            break

    if not file_id:
        return None

    # Якщо це Google Таблиця — формуємо лінк на експорт в Excel
    if "spreadsheets" in url:
        return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"

    # Якщо звичайний файл — додаємо confirm=t (це допомагає для середніх файлів)
    return f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"

def clean_filename(name: str) -> str:
    """Очищає назву файлу"""
    clean = name.strip().replace(' ', '_')
    clean = re.sub(r'[^\w\s.-]', '', clean)
    return clean