import re

def transform_drive_url(url: str) -> str | None:
    """
    Перетворює посилання на перегляд Google Drive у пряме посилання на завантаження.
    Підтримує формати:
    - https://drive.google.com/file/d/FILE_ID/view...
    - https://drive.google.com/open?id=FILE_ID
    """
    # Патерн для пошуку ID файлу (довгий рядок літер, цифр, дефісів)
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
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

    # Формуємо лінк для експорту (завантаження)
    return f"https://drive.google.com/uc?export=download&id={file_id}"

def clean_filename(name: str) -> str:
    """
    Очищає назву файлу від спецсимволів, щоб безпечно зберегти на диск.
    'My File/Name' -> 'My_File_Name'
    """
    # Замінюємо пробіли на підкреслення
    clean = name.strip().replace(' ', '_')
    # Видаляємо все, крім букв, цифр, дефіса і підкреслення
    clean = re.sub(r'[^\w\s.-]', '', clean)
    return clean