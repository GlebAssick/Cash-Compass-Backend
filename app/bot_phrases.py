TEMPLATES = [
    {
        "id": "budget_exceeded",
        "condition": lambda ctx: False,
        "text": "Вы превысили месячный бюджет на {overspend} руб. Стоит притормозить с тратами до конца месяца.",
    },
    {
        "id": "budget_80",
        "condition": lambda ctx: False ,
        "text": "Вы уже потратили {percent_used}% бюджета. Осталось {remaining} руб. до конца месяца — будьте внимательнее.",
    },
    {
        "id": "budget_50",
        "condition": lambda ctx: False,
        "text": "Половина месяца — и {percent_used}% бюджета потрачено. Пока в пределах нормы.",
    },
    {
        "id": "budget_low",
        "condition": lambda ctx: False,
        "text": "Отличный темп! Потрачено всего {percent_used}% бюджета. Так держать.",
    },
]

def find_matching_template(context: dict):
    for template in TEMPLATES:
        if template["condition"](context):
            return template
    return None

def render_template(template: dict, context: dict) -> str:
    overspend = max(0, context["spent"] - context["monthly_amount"])
    return template["text"].format(
        percent_used=context["percent_used"],
        remaining=context["remaining"],
        overspend=overspend,
    )