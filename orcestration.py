# Условный оркестратор

from typing import Dict, Tuple
from holland_system_prompt import SYSTEM_PROMPT
from holland_user_prompt import (
    generate_demographics_prompt,
    generate_type_question_prompt,
    generate_clarification_prompt,
    analyze_profile_for_clarification
)
from recomendation_prompt import generate_recommendation_prompt
from professions_list import format_professions_for_prompt, get_professions_for_types
from answer_parsing import parse_demographics_response, parse_answer_score

class CARAOrchestrator:
    # Инициализация оркестратора
    def __init__(self, llm_client):
        self.llm = llm_client
        #self.session = HollandTestSession() -- условный пайплайн тестовой сессии
        self.current_prompt = None  
        self.last_question = None
        self.recommendation_mode = False
        
    def initialize_session(self) -> str:
        """Инициализировать сессию и получить первое сообщение"""
        # Отправляем системный промпт
        self.llm.set_system_prompt(SYSTEM_PROMPT)
        
        # Генерируем первый промпт (для демографии)
        self.current_prompt = generate_demographics_prompt()
        
        # Получаем ответ от LLM
        response = self.llm.generate_response(self.current_prompt)
        self.last_question = response
        
        return response
    
    def process_user_response(self, user_response: str) -> Tuple[str, Dict]:
        """
        Обработать ответ пользователя
        Returns:
            tuple: (следующий_вопрос, информация_о_состоянии)
        """
        state_info = {}
        
        if self.session.stage == "demographics":
            return self._process_demographics_response(user_response, state_info)
        elif self.session.stage == "basic_test":
            return self._process_basic_test_response(user_response, state_info)
        elif self.session.stage == "clarification":
            return self._process_clarification_response(user_response, state_info)
        
        return "Произошла ошибка обработки ответа.", {}
    
    def _process_demographics_response(self, user_response: str, state_info: Dict) -> Tuple[str, Dict]:
        """Обработать ответ на демографические вопросы"""
        age, gender, education = parse_demographics_response(user_response)
        
        if age and gender and education:
            self.session.set_demographics(age, gender, education)
            
            # Переходим к первому вопросу по типам
            next_type = self.session.get_next_type()
            if next_type:
                demographics = self.session.demographics
                history_summary = self.session.get_type_history_summary()
                
                self.current_prompt = generate_type_question_prompt(
                    age=demographics['age'],
                    gender=demographics['gender'],
                    education=demographics['education'],
                    type_code=next_type,
                    history_summary=history_summary
                )
                
                response = self.llm.generate_response(self.current_prompt)
                self.last_question = response
                
                state_info = {
                    "stage": "basic_test",
                    "current_type": next_type,
                    "demographics": self.session.demographics
                }
                return response, state_info
        else:
            # Не все данные получены, просим уточнить
            return "Пожалуйста, укажите все три параметра: пол, возраст и образование.", {}
        
        return "Ошибка при обработке демографических данных.", {}
    
    def _process_basic_test_response(self, user_response: str, state_info: Dict) -> Tuple[str, Dict]:
        """Обработать ответ на вопрос базового теста"""
        score = parse_answer_score(user_response)
        
        # Определяем текущий тип (последний из запрошенных)
        if self.session.history:
            current_type = self.session.history[-1]["type"]
        else:
            current_type = "R"
        
        # Добавляем ответ в историю
        self.session.add_answer(
            type_code=current_type,
            score=score,
            question=self.last_question,
            answer=user_response
        )
        
        # Проверяем, нужно ли продолжать базовый тест
        next_type = self.session.get_next_type()
        if next_type:
            demographics = self.session.demographics
            history_summary = self.session.get_type_history_summary()
            
            self.current_prompt = generate_type_question_prompt(
                age=demographics['age'],
                gender=demographics['gender'],
                education=demographics['education'],
                type_code=next_type,
                history_summary=history_summary
            )
            
            response = self.llm.generate_response(self.current_prompt)
            self.last_question = response
            
            state_info = {
                "stage": "basic_test",
                "current_type": next_type,
                "scores": self.session.scores,
                "questions_asked": self.session.questions_asked
            }
            return response, state_info
        else:
            # Базовый тест завершен, переходим к уточнениям
            self.session.stage = "clarification"
            return self._generate_first_clarification_question(state_info)
    
    def _process_clarification_response(self, user_response: str, state_info: Dict) -> Tuple[str, Dict]:
        # Для уточняющих вопросов можно обновлять баллы или просто собирать информацию
        self.session.increment_clarification_count()
        # Проверяем, нужно ли задавать еще уточняющие вопросы
        if self.session.should_ask_clarification():
            return self._generate_clarification_question(state_info)
        else:
            # Тест завершен
            final_profile = self.session.get_initial_profile()
            completion_message = f"""Тестирование завершено!

Ваш профиль по методике Холланда:
{final_profile}

На основе этого профиля система сформирует персональные рекомендации по профессиям."""

            state_info = {
                "stage": "completed",
                "final_scores": self.session.scores,
                "final_profile": final_profile,
                "total_questions": self.session.questions_asked + self.session.clarification_questions_asked
            }
            
            return completion_message, state_info
    
    def _generate_first_clarification_question(self, state_info: Dict) -> Tuple[str, Dict]:
        """Сгенерировать первый уточняющий вопрос"""
        demographics = self.session.demographics
        profile = self.session.get_initial_profile()
        analysis = analyze_profile_for_clarification(self.session.scores)
        
        self.current_prompt = generate_clarification_prompt(
            age=demographics['age'],
            gender=demographics['gender'],
            education=demographics['education'],
            profile=profile,
            analysis=analysis
        )
        
        response = self.llm.generate_response(self.current_prompt)
        self.last_question = response
        self.session.increment_clarification_count()
        
        state_info = {
            "stage": "clarification",
            "scores": self.session.scores,
            "profile": profile,
            "clarification_question": 1
        }
        return response, state_info
    
    def _generate_clarification_question(self, state_info: Dict) -> Tuple[str, Dict]:
        """Сгенерировать очередной уточняющий вопрос"""
        demographics = self.session.demographics
        profile = self.session.get_initial_profile()
        analysis = analyze_profile_for_clarification(self.session.scores)
        
        self.current_prompt = generate_clarification_prompt(
            age=demographics['age'],
            gender=demographics['gender'],
            education=demographics['education'],
            profile=profile,
            analysis=analysis
        )
        
        response = self.llm.generate_response(self.current_prompt)
        self.last_question = response
        
        state_info = {
            "stage": "clarification",
            "clarification_question": self.session.clarification_questions_asked + 1,
            "scores": self.session.scores
        }
        return response, state_info
    
    def get_session_summary(self) -> Dict:
        """Получить сводку по текущей сессии"""
        return self.session.get_current_progress()
    
    def generate_profession_recommendations(self) -> str:
        """
        Сгенерировать рекомендации профессий на основе результатов теста
        
        Returns:
            str: рекомендации профессий
        """
        # Определяем наиболее выраженные типы
        sorted_scores = sorted(self.session.scores.items(), key=lambda x: x[1], reverse=True)
        
        # Выбираем типы с положительными баллами (>= 0)
        recommended_types = [t for t, s in sorted_scores if s >= 0]
        
        # Если все баллы отрицательные, берем наименее отрицательные
        if not recommended_types:
            recommended_types = [sorted_scores[0][0]]
        
        # Ограничиваем 2-3 наиболее выраженными типами
        if len(recommended_types) > 3:
            recommended_types = recommended_types[:3]
        
        # Получаем профессии для рекомендованных типов
        professions_by_type = get_professions_for_types(recommended_types, limit_per_type=10)
        professions_text = format_professions_for_prompt(professions_by_type)
        
        # Генерируем промпт для рекомендаций
        recommendation_prompt = generate_recommendation_prompt(
            scores=self.session.scores,
            demographics=self.session.demographics,
            professions_data=professions_text
        )
        
        # Получаем рекомендации от LLM
        recommendations = self.llm.generate_response(recommendation_prompt)
        
        # Добавляем заголовок
        formatted_recommendations = f"""🎯 РЕКОМЕНДАЦИИ ПРОФЕССИЙ НА ОСНОВЕ ВАШЕГО ПРОФИЛЯ

{recommendations}

📊 ВАШ ПРОФИЛЬ ПО ХОЛЛАНДУ:
{chr(10).join([f'- {t}: {s:+d}' for t, s in sorted(self.session.scores.items(), key=lambda x: x[1], reverse=True)])}

💡 СОВЕТ: Эти рекомендации основаны на ваших склонностях. 
Рассмотрите каждую профессию подробнее, изучите требования и возможности роста."""
        
        return formatted_recommendations
    
    def get_detailed_report(self) -> Dict:
        """
        Получить детальный отчет по результатам теста
        
        Returns:
            Dict: полный отчет с рекомендациями
        """
        # Генерируем рекомендации
        recommendations = self.generate_profession_recommendations()
        
        # Собираем полный отчет
        report = {
            "session_summary": self.session.get_current_progress(),
            "profile_analysis": self._analyze_profile(),
            "recommendations": recommendations,
            "top_types": self._get_top_types(3),
            "career_paths": self._suggest_career_paths()
        }
        
        return report
    
    def _analyze_profile(self) -> str:
        """Проанализировать профиль пользователя"""
        scores = self.session.scores
        
        # Определяем сильные и слабые стороны
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        strong = sorted_types[:2]
        weak = sorted_types[-2:]
        
        analysis = []
        
        if strong:
            strong_desc = ", ".join([f"{t}({s:+d})" for t, s in strong])
            analysis.append(f"Сильные стороны: {strong_desc}")
        
        if weak:
            weak_desc = ", ".join([f"{t}({s:+d})" for t, s in weak])
            analysis.append(f"Области для развития: {weak_desc}")
        
        # Анализируем комбинации
        type_names = {
            "R": "Реалистический", "I": "Исследовательский", 
            "A": "Артистический", "S": "Социальный",
            "E": "Предприимчивый", "C": "Конвенциальный"
        }
        
        # Проверяем популярные комбинации
        if scores.get("I", 0) > 2 and scores.get("C", 0) > 2:
            analysis.append("Комбинация I-C характерна для научных и аналитических профессий")
        elif scores.get("E", 0) > 2 and scores.get("S", 0) > 2:
            analysis.append("Комбинация E-S хорошо подходит для менеджмента и работы с людьми")
        elif scores.get("R", 0) > 2 and scores.get("I", 0) > 2:
            analysis.append("Комбинация R-I идеальна для инженерных и технических специальностей")
        
        return "\n".join(analysis)
    
    def _get_top_types(self, n: int = 3) -> list:
        """Получить топ-N типов по баллам"""
        sorted_types = sorted(self.session.scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_types[:n]
    
    def _suggest_career_paths(self) -> list:
        """Предложить карьерные пути на основе профиля"""
        scores = self.session.scores
        age = self.session.demographics.get('age', 25)
        education = self.session.demographics.get('education', '')
        
        paths = []
        
        # Определяем доминирующие типы
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        main_type = sorted_types[0][0] if sorted_types else None
        
        type_paths = {
            "R": ["Технические специальности", "Производство", "Сельское хозяйство", "Транспорт"],
            "I": ["Наука и исследования", "Аналитика", "IT-разработка", "Консалтинг"],
            "A": ["Творческие профессии", "Дизайн", "Искусство", "Медиа"],
            "S": ["Образование", "Медицина", "Социальная работа", "Психология"],
            "E": ["Менеджмент", "Продажи", "Предпринимательство", "Маркетинг"],
            "C": ["Финансы", "Администрирование", "Бухгалтерия", "Логистика"]
        }
        
        if main_type and main_type in type_paths:
            for path in type_paths[main_type]:
                paths.append({
                    "область": path,
                    "рекомендации": self._get_path_recommendations(main_type, path, age, education)
                })
        
        return paths[:3]  # Ограничиваем 3 путями
    
    def _get_path_recommendations(self, type_code: str, path: str, age: int, education: str) -> str:
        """Получить рекомендации для карьерного пути"""
        if age < 20:
            return "Рекомендуется получить профильное образование и начать с практики/стажировки"
        elif age < 30:
            return "Можно начинать карьеру с позиции junior-специалиста и расти до middle/senior"
        else:
            return "Рассмотрите возможности переквалификации или карьерного роста в смежных областях"