import serial
import threading
import time
import fcntl
import os
import signal
import sys
from typing import Dict, List
from flask import Flask
from flask_socketio import SocketIO
import json

# Параметры UART
SERIAL_PORT = '/dev/ttyS5'
BAUD_RATE = 115200
SEND_INTERVAL = 1.0
LOCK_FILE = "/tmp/drone_communication.lock"

# Параметры сервера
HOST = '0.0.0.0'
PORT = 5000

# Данные текущего дрона
DRONE_ID = "001"
drone_data = {
    "id": DRONE_ID,
    "x": 55.755864,
    "y": 37.617698
}

# Список для хранения данных соседних дронов
neighbors: Dict[str, Dict] = {}

# Флаг для завершения потоков
running = True

# Путь к файлу JSON
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
except NameError:
    SCRIPT_DIR = os.getcwd()  # Fallback to current working directory
JSON_FILE = os.path.join(SCRIPT_DIR, "drone_data.json")

# Инициализация Flask и SocketIO
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# Проверка и установка блокировки
lock_fd = None
try:
    lock_fd = open(LOCK_FILE, 'w')
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except IOError:
    print("Another instance of the script is already running. Exiting.")
    sys.exit(1)

# Инициализация UART
ser = None
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.2)
    ser.setDTR(False)
    ser.setRTS(False)
    ser.flushInput()
    ser.flushOutput()
    print(f"Opened serial port: {ser.name}")
except serial.SerialException as e:
    print(f"Failed to open serial port: {e}")
    if lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
    sys.exit(1)

# Функция для сохранения данных в JSON файл
def save_drone_data():
    data = get_drone_data()
    try:
        with open(JSON_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Saved drone data to {JSON_FILE} at {time.time()}")
    except Exception as e:
        print(f"Error saving JSON: {e}")

# Функция для отправки данных через UART
def send_data():
    while running:
        try:
            ser.flushOutput()
            message = f"S{drone_data['id']};{drone_data['x']};{drone_data['y']}E"
            ser.write(message.encode('utf-8'))
            print(f"Sent: {message} at {time.time()}")
            time.sleep(SEND_INTERVAL)
            time.sleep(0.01)
        except serial.SerialException as e:
            print(f"Error sending data: {e} at {time.time()}")
            time.sleep(1)

# Функция для приёма данных через UART
def receive_data():
    buffer = ""
    processed_messages = set()
    while running:
        try:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting).decode('utf-8', errors='ignore')
                buffer += data
                print(f"Raw data received: {data} at {time.time()}")

                while True:
                    start_idx = buffer.find('S')
                    end_idx = buffer.find('E', start_idx + 1)

                    if start_idx == -1 or end_idx == -1:
                        break

                    message = buffer[start_idx:end_idx + 1]
                    buffer = buffer[end_idx + 1:]

                    # Для избежания дубликатов используем хеш без dBm, если он есть
                    content = message[1:-1]
                    parts_for_hash = content.split(';')[:3]  # Берем только первые 3 части для хеша
                    message_for_hash = 'S' + ';'.join(parts_for_hash) + 'E'
                    message_hash = hash(message_for_hash)
                    if message_hash in processed_messages:
                        print(f"Duplicate message skipped: {message} at {time.time()}")
                        continue
                    processed_messages.add(message_hash)

                    if message.startswith('S') and message.endswith('E'):
                        try:
                            parts = content.split(';')
                            if len(parts) >= 3:
                                drone_id = parts[0]
                                x = float(parts[1])
                                y = float(parts[2])
                                dBm = None
                                if len(parts) > 3:
                                    try:
                                        dBm = float(parts[3])  # Сохраняем dBm, если нужно
                                        print(f"Received dBm from {drone_id}: {dBm}")
                                    except ValueError:
                                        print(f"Invalid dBm in: {message}")
                                
                                if drone_id != DRONE_ID:
                                    neighbors[drone_id] = {
                                        "id": drone_id,
                                        "x": x,
                                        "y": y,
                                        "timestamp": time.time(),
                                        "dBm": dBm  # Добавляем поле для dBm, если оно есть
                                    }
                                    print(f"Received from {drone_id}: {neighbors[drone_id]} at {time.time()}")
                                    socketio.emit('drone_data', get_drone_data())
                                    save_drone_data()  # Сохраняем JSON при получении новой информации
                                else:
                                    print(f"Ignored own message: {message} at {time.time()}")
                            else:
                                print(f"Invalid format: {message} at {time.time()}")
                        except ValueError:
                            print(f"Invalid coordinates in: {message} at {time.time()}")
                    else:
                        print(f"Invalid message received: {message} at {time.time()}")

            else:
                # Отладка: сообщаем, если не поступают данные
                time.sleep(0.1)
                # print(f"No data in UART buffer at {time.time()}")  # Раскомментируйте для отладки

        except serial.SerialException as e:
            print(f"Error receiving data: {e} at {time.time()}")
            time.sleep(1)

# Функция для формирования JSON с данными дронов
def get_drone_data():
    return {
        "self": drone_data,
        "neighbors": list(neighbors.values())
    }

# Функция для отображения списка соседей (консоль)
def print_neighbors():
    while running:
        print(f"Neighbors at {time.time()}:")
        if neighbors:
            for drone_id, data in neighbors.items():
                dBm_str = f", dBm={data.get('dBm', 'N/A')}" if data.get('dBm') is not None else ""
                print(f"  {drone_id}: x={data['x']}, y={data['y']}, last seen={data['timestamp']}{dBm_str}")
        else:
            print("  No neighbors detected.")
        time.sleep(10)

# WebSocket: отправка данных при подключении клиента
@socketio.on('connect')
def handle_connect():
    print(f"Client connected at {time.time()}")
    socketio.emit('drone_data', get_drone_data())

# Обработчик сигнала для корректного завершения
def signal_handler(sig, frame):
    global running
    print("\nShutting down...")
    running = False
    if ser:
        ser.close()
        print("Serial port closed.")
    if lock_fd:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    sys.exit(0)

# Регистрируем обработчик сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Запуск потоков
try:
    send_thread = threading.Thread(target=send_data, daemon=True)
    receive_thread = threading.Thread(target=receive_data, daemon=True)
    neighbors_thread = threading.Thread(target=print_neighbors, daemon=True)

    send_thread.start()
    receive_thread.start()
    neighbors_thread.start()

    # Запуск Flask-SocketIO сервера
    print(f"Starting WebSocket server on http://{HOST}:{PORT}")
    socketio.run(app, host=HOST, port=PORT, allow_unsafe_werkzeug=True)

except KeyboardInterrupt:
    signal_handler(signal.SIGINT, None)

except Exception as e:
    print(f"Unexpected error: {e}")
    signal_handler(signal.SIGTERM, None)