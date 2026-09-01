from anthropic import Anthropic
import os

api_key = os.getenv("ANTHROPIC_API_KEY")
client = Anthropic(api_key=api_key) if api_key else None

SYSTEM_PROMPT = """Ты - финансовый ассистент в приложении Cash Compass для студентов.
Твоя задача - дать короткий (1-2 предложения) комментарий о бюджете пользователя.
Тон: дружелюбный, поддерживающий, без нравоучений.
Отвечай только текстом комментария, без вступлений типа "Конечно, вот..."."""

FALLBACK_MESSAGE = "Не удалось получить персональный комментарий от ИИ прямо сейчас, но ваш бюджет под контролем."

def generate_dynamic_comment(context: dict) -> str:
    if client is None:
        return FALLBACK_MESSAGE

    user_message = (
        f"Месячный бюджет: {context['monthly_amount']} руб. "
        f"Потрачено: {context['spent']} руб. "
        f"Использовано {context['percent_used']}% бюджета. "
        f"Осталось: {context['remaining']} руб."
    )

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=150,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
    except Exception as e:
        print(f"Claude API error: {e}")
        return FALLBACK_MESSAGE

import base64
import json

RECEIPT_SYSTEM_PROMPT = """Ты распознаёшь чеки из магазинов. Проанализируй изображение чека и верни СТРОГО JSON без каких-либо пояснений, вступлений или markdown-разметки.

Формат ответа:
{
  "items": [
    {"name": "название товара", "amount": число, "suggested_category": "Еда/Транспорт/Жильё/Развлечения/Здоровье/Прочее"},
    ...
  ],
  "total": число
}

Если на фото не чек или невозможно распознать — верни {"items": [], "total": 0}."""

def parse_receipt_image(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    if client is None:
        return {"items": [], "total": 0, "source": "unavailable"}

    encoded_image = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            system=RECEIPT_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": encoded_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Распознай этот чек и верни JSON, как указано в инструкции."
                    }
                ]
            }],
        )
        raw_text = response.content[0].text.strip()
        # на случай, если модель всё же обернёт ответ в markdown-блок кода
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(raw_text)
        parsed["source"] = "claude_vision"
        return parsed

    except json.JSONDecodeError as e:
        print(f"Receipt parsing JSON error: {e}")
        return {"items": [], "total": 0, "source": "parse_error"}
    except Exception as e:
        print(f"Claude Vision API error: {e}")
        return {"items": [], "total": 0, "source": "unavailable"}