import os
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import zipfile
import rarfile
import json
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from tqdm import tqdm
import time

# Путь к файлу конфигурации для хранения настроек
config_file = "DisassemblySettings.json"

# Получаем имя текущего пользователя
current_user = os.getlogin()

def load_config():
    """Загружает сохранённые настройки из файла."""
    if os.path.exists(config_file):
        with open(config_file, "r") as file:
            return json.load(file)
    return {}

def save_config(config):
    """Сохраняет настройки в файл."""
    with open(config_file, "w") as file:
        json.dump(config, file)

def wait_for_file_complete(file_path, timeout=60):
    """Ожидает, пока файл полностью загрузится (не изменяется размер)."""
    previous_size = -1
    elapsed_time = 0
    while elapsed_time < timeout:
        current_size = os.path.getsize(file_path)
        if current_size == previous_size:
            return True
        previous_size = current_size
        time.sleep(1)
        elapsed_time += 1
    print(f"Файл {file_path} не завершил загрузку за {timeout} секунд.")
    return False

def extract_archive(file_path, extract_to):
    """Распаковывает архив (zip или rar) с отображением прогресса."""
    try:
        if file_path.endswith(".zip"):
            with zipfile.ZipFile(file_path, 'r') as archive:
                file_list = archive.namelist()
                with tqdm(total=len(file_list), desc="Распаковка ZIP") as progress:
                    for file in file_list:
                        archive.extract(file, extract_to)
                        progress.update(1)
        elif file_path.endswith(".rar"):
            with rarfile.RarFile(file_path, 'r') as archive:
                file_list = archive.namelist()
                with tqdm(total=len(file_list), desc="Распаковка RAR") as progress:
                    for file in file_list:
                        archive.extract(file, extract_to)
                        progress.update(1)
        else:
            raise ValueError("Формат файла не поддерживается для распаковки.")
        
        return True
    except Exception as e:
        print(f"Ошибка при распаковке архива: {e}")
        return False

def scan_and_process(base_path, folder_name, target_path):
    """Сканирует указанную папку, распаковывает архивы и перемещает папку."""
    source_path = os.path.join(base_path, folder_name)

    if os.path.exists(source_path):
        # Ожидание завершения загрузки файла
        if not os.path.isdir(source_path) and not wait_for_file_complete(source_path):
            print(f"Файл {folder_name} не завершил загрузку. Пропуск.")
            return

        # Если это архив, распаковать его
        if source_path.endswith(".zip") or source_path.endswith(".rar"):
            extract_to = os.path.join(base_path, os.path.splitext(folder_name)[0])  # Убираем расширение для папки распаковки
            if extract_archive(source_path, extract_to):
                print(f"Архив {folder_name} успешно распакован в {extract_to}.")
                source_path = extract_to  # Обновляем путь для перемещения
            else:
                print(f"Не удалось распаковать архив {folder_name}.")
                return

        # Перемещение папки или распакованного содержимого
        if not os.path.exists(target_path):
            os.makedirs(target_path)
        destination_folder = os.path.join(target_path, os.path.basename(source_path))
        try:
            shutil.move(source_path, destination_folder)
            print(f"Папка {folder_name} успешно перемещена в {target_path}.")
        except Exception as e:
            print(f"Ошибка при перемещении папки: {e}")
    else:
        print(f"Папка или архив {folder_name} не найдена в {base_path}.")

class WatcherHandler(FileSystemEventHandler):
    """Обработчик для отслеживания изменений в директории."""
    def __init__(self, base_path, folder_name, target_path):
        self.base_path = base_path
        self.folder_name = folder_name
        self.target_path = target_path

    def on_created(self, event):
        """Вызывается при создании нового файла или папки."""
        created_path = event.src_path
        if os.path.basename(created_path) == self.folder_name:
            # Проверяем, является ли созданный файл архивом
            if created_path.endswith(".zip") or created_path.endswith(".rar"):
                if wait_for_file_complete(created_path):
                    extract_to = os.path.join(self.base_path, os.path.splitext(self.folder_name)[0])
                    if extract_archive(created_path, extract_to):
                        print(f"Архив {self.folder_name} успешно распакован в {extract_to}.")
                        scan_and_process(self.base_path, os.path.basename(extract_to), self.target_path)
            else:
                scan_and_process(self.base_path, self.folder_name, self.target_path)

def start_watcher(base_path, folder_name, target_path):
    """Запускает мониторинг изменений в исходной папке."""
    event_handler = WatcherHandler(base_path, folder_name, target_path)
    observer = Observer()
    observer.schedule(event_handler, base_path, recursive=False)
    observer.start()
    try:
        while True:
            pass  # Непрерывный мониторинг
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

# Создание интерфейса
config = load_config()

root = tk.Tk()
root.title("Перемещение и распаковка папок")

source_folder_var = tk.StringVar(value=config.get("source_folder", f"C:/Users/{current_user}/Desktop"))
target_folder_var = tk.StringVar(value=config.get("target_folder", f"C:/Users/{current_user}/Documents"))
folder_name_var = tk.StringVar(value=config.get("folder_name", ""))

def select_source_folder():
    folder = filedialog.askdirectory(title="Выберите папку для поиска")
    if folder:
        source_folder_var.set(folder)

def select_target_folder():
    folder = filedialog.askdirectory(title="Выберите целевую папку")
    if folder:
        target_folder_var.set(folder)

def start_process():
    base_path = source_folder_var.get()
    folder_name = folder_name_var.get().strip()
    target_path = target_folder_var.get()

    if not base_path or not folder_name or not target_path:
        messagebox.showwarning("Предупреждение", "Заполните все поля.")
        return

    config.update({
        "source_folder": base_path,
        "folder_name": folder_name,
        "target_folder": target_path
    })
    save_config(config)

    threading.Thread(target=start_watcher, args=(base_path, folder_name, target_path), daemon=True).start()

# Элементы интерфейса
tk.Label(root, text="Исходная папка:").grid(row=0, column=0, padx=5, pady=5)
tk.Entry(root, textvariable=source_folder_var, width=50).grid(row=0, column=1, padx=5, pady=5)
tk.Button(root, text="Выбрать", command=select_source_folder).grid(row=0, column=2, padx=5, pady=5)

tk.Label(root, text="Имя папки или архива:").grid(row=1, column=0, padx=5, pady=5)
tk.Entry(root, textvariable=folder_name_var, width=50).grid(row=1, column=1, padx=5, pady=5)

tk.Label(root, text="Целевая папка:").grid(row=2, column=0, padx=5, pady=5)
tk.Entry(root, textvariable=target_folder_var, width=50).grid(row=2, column=1, padx=5, pady=5)
tk.Button(root, text="Выбрать", command=select_target_folder).grid(row=2, column=2, padx=5, pady=5)

tk.Button(root, text="Запустить", command=start_process).grid(row=3, column=0, columnspan=3, pady=10)

root.mainloop()
