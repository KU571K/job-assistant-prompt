# Это условные штуки, но для более наглядного представления интеграция промпта
from holland_types_description import get_type_description

def generate_demographics_prompt() -> str:
    """Сгенерировать промпт для сбора демографии"""
    return """Поприветствуй пользователя и представься как CARA, помощник по профориентации.
Задай пользователю следующие три вопроса подряд (в одном сообщении), чтобы собрать демографические данные:
1. Укажите ваш пол (Мужской/Женский).
2. Сколько вам полных лет? (Число от 14 до 70)
3. Укажите ваш уровень образования. (Среднее, Высшее, Средне-специальное, Высшее неоконченное, Среднее неоконченное, Средне-специальное неоконченное)

Не переходи к следующим этапам, пока не получишь все три ответа."""

def generate_type_question_prompt(
    age: int,
    gender: str,
    education: str,
    type_code: str,
    history_summary: str
) -> str:
    """Сгенерировать промпт для вопроса по конкретному типу"""
    type_description = get_type_description(type_code)
    
    return f"""ДЕМОГРАФИЯ ПОЛЬЗОВАТЕЛЯ:
- Возраст: {age}
- Пол: {gender}
- Образование: {education}

ОПИСАНИЕ ТИПА [{type_code}]:
{type_description}

ИСТОРИЯ: {history_summary}

ТВОЯ ЗАДАЧА:
Сформулируй ОДИН вопрос для выявления склонности к типу [{type_code}]. Вопрос должен:
1. Быть адаптирован под возраст, образование и (косвенно) пол пользователя
2. Касаться реальных жизненных ситуаций или предпочтений
3. Быть понятным и однозначным
4. Естественным образом вытекать из описания типа выше

После вопроса предложи шкалу ответов из 5 вариантов (от "Определенно да" до "Определенно нет")."""

def generate_clarification_prompt(
    age: int,
    gender: str,
    education: str,
    profile: str,
    analysis: str
) -> str:
    """Сгенерировать промпт для уточняющего вопроса"""
    return f"""ДЕМОГРАФИЯ ПОЛЬЗОВАТЕЛЯ:
- Возраст: {age}
- Пол: {gender}
- Образование: {education}

ПЕРВОНАЧАЛЬНЫЙ ПОРТРЕТ ПОЛЬЗОВАТЕЛЯ:
{profile}

АНАЛИЗ ДЛЯ УТОЧНЕНИЯ: {analysis}

ТВОЯ ЗАДАЧА:
На основе этого портрета задай 1 уточняющий вопрос. Вопрос должен:
1. Помочь прояснить наиболее важные противоречия или неясности в профиле
2. Углубить понимание наиболее выраженных склонностей
3. Быть адаптирован под демографию пользователя
4. Учитывать контекст предыдущих ответов

После вопроса предложи соответствующую шкалу ответов (может быть дифференцированной).

Пример хорошего уточняющего вопроса:
"В вашей учебе что привлекает больше: глубокая проработка одной теоретической проблемы или поиск практического применения знаний для быстрого результата?"""

# Анализ профиля для определения уточняющих вопросов
def analyze_profile_for_clarification(scores: dict) -> str:
    # Найти наиболее выраженные типы
    sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_types = sorted_types[:2]
    bottom_types = sorted_types[-2:]
    
    # Найти противоречия (близкие баллы)
    contradictions = []
    types_list = list(scores.keys())
    for i in range(len(types_list)):
        for j in range(i+1, len(types_list)):
            if abs(scores[types_list[i]] - scores[types_list[j]]) <= 1:
                contradictions.append(f"{types_list[i]}({scores[types_list[i]]}) и {types_list[j]}({scores[types_list[j]]})")
    
    analysis_parts = []
    
    if top_types:
        analysis_parts.append(f"Наиболее выраженные типы: {top_types[0][0]}({top_types[0][1]}) и {top_types[1][0]}({top_types[1][1]})")
    if contradictions:
        analysis_parts.append(f"Требуют уточнения противоречия между: {', '.join(contradictions)}")  
    if bottom_types:
        analysis_parts.append(f"Наименее выраженные типы: {bottom_types[0][0]}({bottom_types[0][1]}) и {bottom_types[1][0]}({bottom_types[1][1]})")
    return "; ".join(analysis_parts) if analysis_parts else "Профиль достаточно ясный, уточнить сильные стороны."