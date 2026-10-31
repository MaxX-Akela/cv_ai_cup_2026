import argparse
import json
import signal
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from llm import ask
from parser import answer, check_steps, parse


def send(car, path, data):
    request = urllib.request.Request(car.rstrip("/") + path, json.dumps(data).encode(),{"Content-Type": "application/json"})

    with urllib.request.urlopen(request, timeout=40) as response:

        result = json.load(response)

    if not result["ok"]:

        raise ValueError(result["message"])
    
    return result["message"]


def server(port):

    import control
    control.setup()
    busy = threading.Lock()
    motor = threading.Lock()
    cancelled = threading.Event()

    def move(skill):

        print("Навык:", skill, flush=True)

        control.move(skill)

    class Handler(BaseHTTPRequestHandler):

        def log_message(self, *args):

            pass

        def do_POST(self):
            result = {"ok": True, "message": "Выполнено"}
            try:

                if self.path == "/stop":
                    with motor:
                        cancelled.set()
                        move("stop")
                    result["message"] = "Стоп"

                elif self.path == "/plan":
                    self.connection.settimeout(3)
                    size = int(self.headers.get("Content-Length", "0"))

                    if not 0 < size <= 8192:
                        raise ValueError("Пустой или слишком")
                    
                    steps = check_steps(json.loads(self.rfile.read(size)))

                    with motor:
                        if not busy.acquire(blocking=False):
                            raise ValueError("Машинка занята")
                        cancelled.clear()

                    try:

                        for step in steps:

                            with motor:

                                if cancelled.is_set():
                                    raise ValueError("План остановлен")
                                move(step["skill"])

                            if cancelled.wait(step["seconds"]):
                                raise ValueError("План остановлен")
                            
                            with motor:

                                move("stop")
                            print("Выполнено:", step, flush=True)

                            if cancelled.wait(0.2):
                                raise ValueError("План остановлен")
                    finally:

                        try:

                            with motor:

                                move("stop")

                        finally:

                            busy.release()
                else:
                    raise ValueError("Неизвестная команда")
            except Exception as error:
                result = {"ok": False, "message": str(error)}
            body = json.dumps(result, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    print(f"EyeCar слушает порт {port}", flush=True)
    try:
        with ThreadingHTTPServer(("0.0.0.0", port), Handler) as http:
            http.daemon_threads = True
            http.serve_forever()
    finally:
        with motor:
            cancelled.set()
            move("stop")
        control.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--car")
    parser.add_argument("--rules", action="store_true")
    parser.add_argument("--ai", action="store_true")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--llama-url", default="http://127.0.0.1:8080", help="Адрес llama-server")
    parser.add_argument("--model", default="eyecar", help="Имя модели из --alias llama-server")
    args = parser.parse_args()
    def interrupt(*args):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupt)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, interrupt)
    try:
        if args.server:
            server(args.port)
            return
        if args.stop:
            if not args.car:
                parser.error("Укажи --car http://IP:8765")
            print(send(args.car, "/stop", {}))
            return
        print(f"Машинка: {args.car}" if args.car else "Показываю только план: машинка не подключена.")
        print("Выход: exit. Стоп: Ctrl+C.")
        while True:
            text = input("Команда > ")
            if text.lower().strip() == "exit":
                break
            try:

                result = parse(text)
                need_ai = result is None or (args.ai and result["status"] == "execute" and result["steps"] != [{"skill": "stop", "seconds": 0}])

                if need_ai:

                    print("Разбор:", "правила" if args.rules else "llama.cpp")
                    expected = result
                    result = answer("clarify", "Укажи направление и действия понятнее") if args.rules else ask(text, args.llama_url, args.model)

                    if (not args.rules and expected is not None and expected["status"] == "execute" and result["status"] == "execute" and result["steps"] != expected["steps"]):
                        result = expected
                else:
                    print("Разбор: правила")
                print(result["message"])

                for step in result["steps"]:

                    print(step["skill"], step["seconds"], "сек.")
                    
                if result["status"] == "execute" and args.car:

                    path = "/stop" if result["steps"] == [{"skill": "stop", "seconds": 0}] else "/plan"

                    print(send(args.car, path, result["steps"]))

                    for step in result["steps"]:

                        print("Выполнено:", step["skill"])

            except Exception as error:

                print("Не выполнено:", error)

                if args.car:

                    try:

                        send(args.car, "/stop", {})

                    except Exception:

                        print("Не удалось доставить стоп")

    except (KeyboardInterrupt, EOFError):

        print("Выход")

    finally:

        if args.car and not args.server:

            try:

                send(args.car, "/stop", {})

            except Exception:

                print("Связи нет.")


if __name__ == "__main__":
    main()


