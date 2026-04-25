"""Intent router with keyword classification and domain dispatch."""

from __future__ import annotations

from app.modules.chatbot.schemas import ConversationEvent, IntentRoute, IntentType

_HR_KEYWORDS = ("отпуск", "зарплат", "час", "справк", "оклад", "начислен", "отработан")
_ONBOARDING_KEYWORDS = ("адаптац", "первый день", "план", "задач", "обучен", "онбординг")
_SURVEY_KEYWORDS = ("опрос", "feedback", "exit", "анкет", "обратная связь")


class IntentRouter:
    """Keyword-based router. Extended by domain handlers via `handle()`."""

    def route(self, event: ConversationEvent) -> IntentRoute:
        text = event.text.lower()

        if any(w in text for w in _HR_KEYWORDS):
            return IntentRoute(
                intent=IntentType.HR_SELF_SERVICE,
                confidence=0.80,
                reason="Matched HR self-service keywords.",
            )

        if any(w in text for w in _ONBOARDING_KEYWORDS):
            return IntentRoute(
                intent=IntentType.ONBOARDING,
                confidence=0.75,
                reason="Matched onboarding keywords.",
            )

        if any(w in text for w in _SURVEY_KEYWORDS):
            return IntentRoute(
                intent=IntentType.SURVEY,
                confidence=0.70,
                reason="Matched survey keywords.",
            )

        if event.text.strip():
            return IntentRoute(
                intent=IntentType.KNOWLEDGE,
                confidence=0.60,
                reason="Default to knowledge/RAG for non-empty message.",
            )

        return IntentRoute(
            intent=IntentType.UNKNOWN,
            confidence=0.0,
            reason="Empty message.",
        )

    async def handle(self, route: IntentRoute, event: ConversationEvent, user_id: str) -> str:
        """Dispatch to domain handlers and return a response string."""
        if route.intent == IntentType.KNOWLEDGE:
            return await self._handle_knowledge(event.text)
        if route.intent == IntentType.ONBOARDING:
            return await self._handle_onboarding(user_id)
        if route.intent == IntentType.HR_SELF_SERVICE:
            return (
                "Это кадровый запрос. Я выполню его через защищённый HR-tool "
                "с проверкой прав доступа. Интеграция с 1C будет доступна в Phase 4."
            )
        if route.intent == IntentType.SURVEY:
            return "Это запрос по опросу. Модуль опросов будет доступен в Phase 5."
        return None  # escalate

    async def _handle_knowledge(self, question: str) -> str:
        """Search knowledge base and return answer with citation stub."""
        import httpx
        try:
            from urllib.parse import quote
            q = quote(question[:200])
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"http://127.0.0.1:8000/api/knowledge/search?q={q}&limit=3")
            if r.status_code == 200:
                data = r.json()
                results = data.get("results", [])
                if results:
                    excerpts = "\n".join(f"• {res['text'][:200]}" for res in results[:2])
                    return f"Нашёл в базе знаний:\n{excerpts}"
        except Exception:
            pass
        return "По вашему вопросу информация пока не найдена в базе знаний. Хотите отправить вопрос HR-администратору?"

    async def _handle_onboarding(self, user_id: str) -> str:
        """Fetch employee's onboarding plan summary."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"http://127.0.0.1:8000/api/onboarding/my/{user_id}")
            if r.status_code == 200:
                plan = r.json()
                tasks = plan.get("tasks", [])
                pending = [t for t in tasks if t["status"] == "pending"]
                done = [t for t in tasks if t["status"] == "done"]
                return (
                    f"Ваш план адаптации «{plan['title']}» (этап: {plan['stage']}).\n"
                    f"Выполнено задач: {len(done)} из {len(tasks)}.\n"
                    + (f"Следующая задача: {pending[0]['title']}" if pending else "Все задачи выполнены!")
                )
        except Exception:
            pass
        return "Для вас ещё не создан план адаптации. Обратитесь к HR-менеджеру."

