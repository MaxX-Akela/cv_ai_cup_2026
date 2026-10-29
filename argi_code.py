import io
import sys
import time
import pymurapi as mur

def setup():
    """
    Подключение к подводному роботу.

    Returns:
        auv: объект для управления роботом
    """
    # Русские буквы в print: без этого программа под службой робота падает с ошибкой
    if (sys.stdout.encoding or "").lower().replace("-", "") != "utf8":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)

    auv = mur.mur_init()

    # Исправление библиотеки: без этого связь с роботом обрывается через минуту
    class NoSend:
        def send(self, *args, **kwargs):
            pass

        def poll(self, *args, **kwargs):
            return 0
    auv.control_v2_socket = NoSend()

    time.sleep(1)
    return auv

def move(auv, forward, turn, up, duration):
    """
    Движение, потом остановка моторов.

    Args:
        forward: вперёд (плюс) или назад (минус)
        turn: поворот, плюс вправо, минус влево
        up: вверх (плюс) или вниз (минус)
        duration: сколько секунд
    """
    # Моторы 1 и 2: задние горизонтальные (1 правый, 2 левый), плюс толкает назад
    # Моторы 0 и 3: передние вертикальные, плюс толкает вверх
    m_up = int(up)
    m_right = int(-forward + turn)
    m_left = int(-forward - turn)

    # Ограничения системы: мощность каждого мотора от -50 до 50 (робот допускает до 100)
    m_up = max(-50, min(50, m_up))
    m_right = max(-50, min(50, m_right))
    m_left = max(-50, min(50, m_left))

    auv.set_motor_power(0, m_up)
    auv.set_motor_power(1, m_right)
    auv.set_motor_power(2, m_left)
    auv.set_motor_power(3, m_up)
    time.sleep(duration)
    for i in range(4):
        auv.set_motor_power(i, 0)
    time.sleep(0.2)

# Основная программа: здесь работаете вы
# Запуск только через службу робота: python3 mur_ws_run.py water_control.py
# Окно с mur_ws_run.py не закрывайте, пока программа работает
if __name__ == "__main__":
    auv = setup()
    print("Start")

    try:
        auv.set_rgb_color(0, 50, 0)       # подсветка зелёная: программа работает

        # Погружение 3 секунды
        move(auv, forward=0, turn=0, up=-30, duration=3)

        # Вперёд 2 секунды
        move(auv, forward=30, turn=0, up=0, duration=2)

        # Поворот вправо 2 секунды
        move(auv, forward=0, turn=30, up=0, duration=2)

        # Показания датчиков
        print("Глубина:", auv.get_depth(), "Курс:", auv.get_yaw())

        # Как поменять, чтобы получить другое:
        # глубже: up=-40 или duration=5
        # назад: forward=-30
        # поворот влево: turn=-30
        # держаться под водой и плыть: move(auv, forward=30, turn=0, up=-20, duration=3)
        # цвет подсветки: auv.set_rgb_color(50, 0, 0) красный, (0, 0, 50) синий
    finally:
        # Остановка в конце программы и при ошибке: моторы в ноль, подсветка выключена
        for i in range(4):
            auv.set_motor_power(i, 0)
        auv.set_rgb_color(0, 0, 0)
        time.sleep(0.5)