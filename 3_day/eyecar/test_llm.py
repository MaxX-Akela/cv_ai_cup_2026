import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from llm import ask
from parser import check_steps, parse


class LlamaServerTests(unittest.TestCase):
    def test_timed_stop(self):
        for seconds in (0, 0.5, 3, 5, 30):
            steps = [{"skill": "stop", "seconds": seconds}]
            self.assertEqual(check_steps(steps), steps)
            self.assertEqual(self.call({"status": "execute", "message": "Жду", "steps": steps})["steps"], steps)
        for seconds in (-1, 31, True, float('inf')):
            with self.assertRaises(ValueError):
                check_steps([{"skill": "stop", "seconds": seconds}])
        with self.assertRaises(ValueError):
            check_steps([{"skill": "stop", "seconds": 30}, {"skill": "forward", "seconds": 1}])

    def test_timed_stop_sequence(self):
        expected = [{"skill": "stop", "seconds": 3}, {"skill": "forward", "seconds": 3}]
        for text in ('стоп 3 секунды вперёжд 3 секунды',
                     'стоп 3 секунды вперёд 3 секунды',
                     'стоп 3 секунды и вперед 3 секунды'):
            self.assertEqual(parse(text)["steps"], expected)
        self.assertEqual(parse('стоп')["steps"], [{"skill": "stop", "seconds": 0}])

    def call(self, plan, finish="stop"):
        response = io.BytesIO(json.dumps({"choices": [{
            "finish_reason": finish, "message": {"content": json.dumps(plan)}
        }]}).encode())
        with patch("urllib.request.urlopen", return_value=response) as request:
            result = ask("Дай задний ход на две секунды и замри", "http://localhost:8081/", "eyecar")
            sent = request.call_args.args[0]
            self.assertEqual(sent.full_url, "http://localhost:8081/v1/chat/completions")
            self.assertIsNone(sent.get_header("Authorization"))
            self.assertEqual(json.loads(sent.data)["model"], "eyecar")
            return result

    def test_plan(self):
        plan = {"status": "execute", "message": "План готов", "steps": [
            {"skill": "backward", "seconds": 2}, {"skill": "stop", "seconds": 0}]}
        self.assertEqual(self.call(plan), plan)

    def test_refuse_and_clarify(self):
        for status in ("refuse", "clarify"):
            plan = {"status": status, "message": "Нужны уточнения или такого навыка нет", "steps": []}
            self.assertEqual(self.call(plan), plan)

    def test_invalid_plans(self):
        for steps in ([{"skill": "fly", "seconds": 1}],
                      [{"skill": "forward", "seconds": 100}],
                      [{"skill": "forward", "seconds": True}]):
            with self.assertRaises(ValueError):
                self.call({"status": "execute", "message": "План", "steps": steps})
        with self.assertRaises(ValueError):
            self.call({"status": "refuse", "message": "Отказ", "steps": [
                {"skill": "forward", "seconds": 1}]})

    def test_incomplete_and_invalid_json(self):
        with self.assertRaisesRegex(ValueError, "не закончила"):
            self.call({}, finish="length")
        response = io.BytesIO(b'{"choices":[{"finish_reason":"stop","message":{"content":"oops"}}]}')
        with patch("urllib.request.urlopen", return_value=response), \
                self.assertRaisesRegex(ValueError, "неверный формат"):
            ask("Команда")

    def test_model_loading(self):
        error = urllib.error.HTTPError("http://localhost:8080", 503, "loading", {}, None)
        with patch("urllib.request.urlopen", side_effect=error), \
                self.assertRaisesRegex(ValueError, "ещё загружается"):
            ask("Команда")


if __name__ == "__main__":
    unittest.main()
