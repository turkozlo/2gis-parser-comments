import json
from pathlib import Path

print("[LLM MODULE] offer_generator.py загружен")

# --- Загрузка конфигурации LLM ---
LLM_CONFIG_PATH = Path("newsendingbot/llm_config.json")
with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
    llm_conf = json.load(f)

llm_backend = llm_conf.get("llm_backend", 0)

# --- Инициализация клиента LLM ---
if llm_backend == 0:
    print("Используется OpenAI")
    from openai import OpenAI

    client = OpenAI(
        base_url=llm_conf["base_url_Open_AI"],
        api_key=llm_conf["api_key_Open_AI"],
    )
elif llm_backend == 1:
    print("Используется LangChain+Groq")
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage

    client = ChatGroq(
        model=llm_conf.get("model_LANGCHAIN", "llama3-8b-8192"),
        api_key=llm_conf["api_key_LANGCHAIN"]
    )
else:
    print("Используется LangChain+Mistral")
    from langchain_mistralai import ChatMistralAI
    from langchain_core.messages import HumanMessage

    client = ChatMistralAI(
        model_name=llm_conf.get("model_LANGCHAIN_mistral", "mistral-small-latest"),
        api_key=llm_conf["api_key_LANGCHAIN_mistral"]
    )

def generate_offer(news_text: str, system_prompt: str) -> str | None:
    """
    Генерирует текст оффера на основе новости через LLM.
    Возвращает строку (результат) или None при ошибке/недоступности LLM.
    """
    try:
        user_prompt = f"Вот текст новости:\n{news_text}"

        if llm_backend == 0:
            # OpenAI (оставляем как было)
            response = client.chat.completions.create(
                model=llm_conf["model_Open_AI"],
                extra_body={},
                max_tokens=512,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
            )
            result = response.choices[0].message.content.strip()
            print(f"[OFFER_GENERATOR][OpenAI] Сгенерирован оффер: {result}")
            return result

        # --- LangChain (Groq / Mistral) ---
        # Попытка импортировать SystemMessage и HumanMessage из разных модулей (без падения если не найдено)
        SystemMessage = None
        HumanMessage = None
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
        except Exception:
            try:
                # некоторые реализации используют другие модули/имена
                from langchain_core.schema import HumanMessage, SystemMessage
            except Exception:
                try:
                    from langchain_core.messages import HumanMessage
                except Exception:
                    # если вообще нет HumanMessage — падаем к простому fallback ниже
                    HumanMessage = None

        # Сформируем список сообщений для invoke
        messages = []
        if SystemMessage is not None and HumanMessage is not None:
            # Правильный вариант: системное + пользовательское сообщение
            messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        elif HumanMessage is not None:
            # Если есть только HumanMessage — вшиваем system_prompt в начало user_prompt
            messages = [HumanMessage(content=f"{system_prompt}\n\n{user_prompt}")]
        else:
            # Если не можем импортировать классы — делаем строковый invoke (fallback)
            # Многие реализации LangChain принимают простые строки или объекты, но если нет — пробуем передать строку
            messages = [f"SYSTEM: {system_prompt}\n\nUSER: {user_prompt}"]

        # Вызов клиента LangChain (Groq или Mistral): используем client.invoke
        resp = client.invoke(messages)
        # В разных реализациях resp может иметь разную структуру — пытаемся достать текст аккуратно
        if hasattr(resp, "content"):
            result = resp.content.strip()
        elif isinstance(resp, (list, tuple)) and len(resp) > 0:
            # иногда возвращается список с объектом
            first = resp[0]
            result = getattr(first, "content", str(first)).strip()
        else:
            # как крайний вариант — привести resp к строке
            result = str(resp).strip()

        print(f"[OFFER_GENERATOR][LangChain] Сгенерирован оффер: {result}")
        return result

    except Exception as e:
        # Логируем ошибку и возвращаем None — вызывающий код должен обработать это как "LLM недоступна"
        print(f"[OFFER_GENERATOR ERROR] {e}", flush=True)
        return None
