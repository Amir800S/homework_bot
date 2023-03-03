class CannotGetAPIresponse(Exception):
    """Не получатеся получить ответ от API."""
    pass


class EmptyAPIResponse(Exception):
    """Пустой ответ от API."""
    pass


class CantSendTheMessage(Exception):
    """Не удалось отправить сообщение."""
    pass
