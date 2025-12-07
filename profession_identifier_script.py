import json
from typing import Dict, List, Optional
from openai import AsyncOpenAI
import holland_prompt
import holland_user_prompt

class DynamicCareerAssistant:
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.sessions: Dict[str, TestSession] = {}
        
    async def start_session(self, user_id: str) -> Dict:
        """Начало новой сессии"""
        session_id = f"sess_{user_id}_{int(time.time())}"
        
        self.sessions[session_id] = TestSession(
            session_id=session_id,
            stage="demographic",
            demographic_data={},
            holland_scores={"R": 0, "I": 0, "A": 0, "S": 0, "E": 0, "C": 0},
            history=[],
            questions_asked=0
        )
        # Первый вопрос – пол
        return {
            "stage": "demographic",
            "question_type": "gender",
            "question": "Укажите ваш пол",
            "options": ["Мужской", "Женский"],
            "question_number": 1,
            "total_questions": 14 
        }
    
    async def process_answer(self, session_id: str, answer: Dict) -> Dict:
        """Обработка ответа и генерация следующего вопроса"""
        session = self.sessions[session_id]
        
        # Сохраняем ответ
        session.history.append({
            "question_type": answer.get("question_type"),
            "answer": answer.get("answer"),
            "timestamp": time.time()
        })
        
        # Обработка в зависимости от этапа
        if session.stage == "demographic":
            return await self._process_demographic(session, answer)
        elif session.stage == "holland":
            return await self._process_holland(session, answer)
        elif session.stage == "complete":
            return await self._generate_results(session)
    
    async def _process_demographic(self, session: TestSession, answer: Dict) -> Dict:
        """Обработка демографических данных"""
        question_type = answer.get("question_type")
        user_answer = answer.get("answer")
        
        # Сохраняем демографические данные
        if question_type == "gender":
            session.demographic_data["gender"] = user_answer
            # Возраст 
            return {
                "stage": "demographic",
                "question_type": "age",
                "question": "Сколько вам полных лет?",
                "options": [],  
                "question_number": 2,
                "total_questions": 14
            }
            
        elif question_type == "age":
            try:
                age = int(user_answer)
                if 14 <= age <= 70:
                    session.demographic_data["age"] = age
                    session.stage = "holland"
                    return await self._generate_holland_question(session)
                else:
                    return {
                        "error": "Возраст должен быть от 14 до 70 лет",
                        "retry_question": True
                    }
            except ValueError:
                return {
                    "error": "Пожалуйста, введите число",
                    "retry_question": True
                }
    
    async def _generate_holland_question(self, session: TestSession) -> Dict:
        # Формируем контекст для промпта
        context = {
            "questions_asked": session.questions_asked,
            "current_scores": session.holland_scores,
            "user_age": session.demographic_data.get("age", 25),
            "user_gender": session.demographic_data.get("gender", "Мужской"),
            "history_summary": self._summarize_history(session.history[-5:])
        }
        
        # Определяем, на какой тип нужно задать вопрос
        focus_type = self._determine_focus_type(session)
        
        # Генерируем вопрос через LLM
        system_prompt = holland_prompt.format(**context) 
        user_prompt = holland_user_prompt.format(**context)
        
        response = await self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        result["question_number"] = session.questions_asked + 3  # +2 демо вопроса
        
        return result
    
    def _determine_focus_type(self, session: TestSession) -> str:
        """Определение типа для следующего вопроса"""
        scores = session.holland_scores
        questions_by_type = self._count_questions_by_type(session.history)
        
        # Этап 1: Исследование всех типов (первые 6 вопросов)
        if session.questions_asked < 6:
            types_order = ["R", "I", "A", "S", "E", "C"]
            return types_order[session.questions_asked]
        
        # Этап 2: Найти типы с наименьшим количеством вопросов
        min_questions = min(questions_by_type.values())
        under_explored = [
            t for t, count in questions_by_type.items() 
            if count == min_questions
        ]
        
        if under_explored:
            # Предпочитать типы с низкими баллами
            for t in under_explored:
                if scores[t] < 3:
                    return t
            return under_explored[0]
        
        # Этап 3: Уточнение доминирующих типов
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_types) >= 2:
            # Если два типа близки по баллам - уточняем
            if sorted_types[0][1] - sorted_types[1][1] <= 2:
                return sorted_types[0][0]
        
        return sorted_types[0][0]  # Самый высокий балл
    
    # Подсчет баллов
    async def _process_holland(self, session: TestSession, answer: Dict) -> Dict:
        question_type = answer.get("question_type")
        user_answer = answer.get("answer")
        
        # Преобразуем ответ в балл (1-5)
        score = self._map_answer_to_score(user_answer, question_type)
        
        # Обновляем баллы
        if question_type in session.holland_scores:
            session.holland_scores[question_type] += score
        
        session.questions_asked += 1
        
        # Проверяем завершение теста
        if session.questions_asked >= 12:
            session.stage = "complete"
            return await self._generate_results(session)
        
        # Генерируем следующий вопрос
        return await self._generate_holland_question(session)
    
    # Формирование результатов
    async def _generate_results(self, session: TestSession) -> Dict:
        # Определяем доминирующие типы
        sorted_scores = sorted(
            session.holland_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        dominant_types = [sorted_scores[0][0]]
        if len(sorted_scores) > 1 and sorted_scores[1][1] >= sorted_scores[0][1] - 2:
            dominant_types.append(sorted_scores[1][0])
        
        # Подбираем профессии
        recommended = self.profession_matcher.find_professions(
            holland_codes=dominant_types,
            age=session.demographic_data.get("age", 25),
            gender=session.demographic_data.get("gender")
        )
        
        # Генерируем описание профиля
        profile_desc = self._generate_profile_description(
            dominant_types,
            session.holland_scores,
            session.demographic_data.get("age")
        )
        
        return {
            "stage": "result",
            "user_profile": {
                "gender": session.demographic_data.get("gender", "Мужской"),
                "age": session.demographic_data.get("age", 25),
                "holland_codes": dominant_types,
                "scores": session.holland_scores
            },
            "recommended_professions": recommended,
            "personality_description": profile_desc,
            "total_questions": session.questions_asked + 2  # +2 – это вопросы на пол и возраст
        }
    
    def _map_answer_to_score(self, answer: str, question_type: str) -> int:
        """Преобразование ответа в балл (1-5)"""
        score_map = {
            "Определенно да": 5,
            "Скорее да": 4,
            "Нейтрально": 3,
            "Скорее нет": 2,
            "Определенно нет": 1
        }
        return score_map.get(answer, 3)