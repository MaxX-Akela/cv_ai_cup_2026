import math
import re

WORDS = {
    "forward": ["вперед", "прямо", "едь прямо", "езжай прямо", "езжай вперед", "едь вперед", "проедь вперед", "выдвигайся вперед"],
    "backward": ["назад", "езжай назад", "едь назад", "сдай назад"],
    "left": ["налево", "влево", "поверни налево", "сверни налево", "поверни влево"],
    "right": ["направо", "вправо", "поверни направо", "сверни направо", "поверни вправо"],
    "circle": ["круг", "сделай круг", "проедь круг"],
    "stop": ["стоп", "стой", "остановись", "тормози"],
}


def answer(status, message, steps=None):

    return {"status": status, "message": message, "steps": steps or []}


def check_steps(steps):
    if not isinstance(steps, list) or not 1 <= len(steps) <= 8:
        raise ValueError("Нужно от 1 до 8 действий")
    
    for step in steps:

        if not isinstance(step, dict) or set(step) != {"skill", "seconds"}:

            raise ValueError("s")
        
        skill, seconds = step["skill"], step["seconds"]

        if not isinstance(skill, str) or skill not in WORDS:

            raise ValueError("")
        
        if type(seconds) not in (int, float) or not math.isfinite(seconds):

            raise ValueError("")
        
        if skill == "stop" and not 0 <= seconds <= 30:

            raise ValueError("")
        
        if skill != "stop" and not 0.1 <= seconds <= 10:

            raise ValueError("")
        
    if sum(step["seconds"] for step in steps) > 30:

        raise ValueError("")
    
    return steps


def parse(text):

    text = text.lower().replace("ё", "е").strip(" .!?")
    text = re.sub(r"\bвпережд\b", "вперед", text)
    text = re.sub(r"^(машинка|eyecar|ровер)[ ,:]*", "", text)

    if not text:
        return answer("clarify", "Что нужно сделать")
    
    if len(text) > 2000:
        return answer("refuse", "Слишком длинно")
    
    bad = ["лети", "летай", "прыг", "взлет", "обрыв", "человек", "люд", "ребен","стен", "вреж", "огонь", "дорог", "препятств", "бесконеч", "полной скорост","игнорир", "отключи защит", "без останов"]
    
    if any(word in text for word in bad):
        return answer("refuse", "Это опасно или такого навыка нет. Отказ")
    
    if re.search(r"\b(туда|сюда|там|не|если|пока|или)\b", text):
        return answer("clarify", "Укажи точно направление и порядок действий без условий и отрицаний.")
    
    if re.search(r"\b(метр\w*|сантиметр\w*|градус\w*)\b|\d\s*(м|см)\b|°", text):
        return answer("clarify", "Не умею измерять расстояние и углы. Укажи время в секундах.")
    
    text = re.sub(r"(\b(?:секунд[уы]?|сек|с))\s+(?!(?:и|затем|потом)\b)(?=[а-я])", r"\1, ", text)
    steps = []

    for part in re.split(r"\s*(?:,?\s+(?:и|затем|потом)\s+|[,;]|\s+(?=(?:стоп|стой|остановись|тормози)\b))\s*", text):

        match = re.fullmatch(r"(.+?)(?: (?:на )?(\d+(?:\.\d+)?) (?:секунд[уы]?|сек|с))?", part)

        if not match:
            return None
        
        phrase, seconds = match.groups()
        skill = None

        for name, variants in WORDS.items():

            if phrase in variants:
                skill = name

        if skill is None:

            return None
        
        default = 0 if skill == "stop" else 6 if skill == "circle" else 1

        steps.append({"skill": skill, "seconds": float(seconds) if seconds else default})

    check_steps(steps)

    return answer("execute", steps)





