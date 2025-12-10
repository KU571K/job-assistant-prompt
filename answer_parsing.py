# Условный скрипт для парсинга ответов
def parse_demographics_response(response: str) -> tuple:
    """Парсить ответ с демографическими данными
    
    Returns:
        tuple: (age, gender, education)
    """
    lines = [line.strip() for line in response.split('\n') if line.strip()]
    
    age = None
    gender = None
    education = None
    
    for line in lines:
        # Ищем возраст (число)
        if any(char.isdigit() for char in line):
            words = line.split()
            for word in words:
                if word.isdigit():
                    age_num = int(word)
                    if 14 <= age_num <= 70:
                        age = age_num
                        break
        
        # Ищем пол
        if "муж" in line.lower() or "мужской" in line.lower():
            gender = "Мужской"
        elif "жен" in line.lower() or "женский" in line.lower():
            gender = "Женский"
        
        # Ищем образование
        educ_options = ["среднее", "высшее", "средне-специальное", 
                       "высшее неоконченное", "среднее неоконченное", 
                       "средне-специальное неоконченное"]
        
        for educ in educ_options:
            if educ in line.lower():
                education = educ.capitalize()
                break
    
    return age, gender, education

def parse_answer_score(answer_text: str) -> int:
    """Парсить текстовый ответ в балл
    
    Returns:
        int: балл от -2 до 2
    """
    answer_lower = answer_text.lower().strip()
    
    if "определенно да" in answer_lower:
        return 2
    elif "скорее да" in answer_lower:
        return 1
    elif "нейтрально" in answer_lower or "затрудняюсь" in answer_lower:
        return 0
    elif "скорее нет" in answer_lower:
        return -1
    elif "определенно нет" in answer_lower:
        return -2
    else:
        # Попробуем определить по другим ключевым словам
        if "да" in answer_lower and "нет" not in answer_lower:
            return 1
        elif "нет" in answer_lower and "да" not in answer_lower:
            return -1
        else:
            return 0