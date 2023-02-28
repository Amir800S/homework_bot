import logging
import os
from http import HTTPStatus
import exceptions
import time
import requests
import telegram
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
PAYLOAD = {'from_date': 100000}

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка переменных."""
    token_vars = [
        PRACTICUM_TOKEN,
        TELEGRAM_TOKEN,
        TELEGRAM_CHAT_ID
    ]
    for token in token_vars:
        if token is None:
            return logging.critical('Не найден токен {token}')
        else:
            return True


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.debug('Сообщение отправлено')
    except Exception as error:
        logging.error(f'Сообщение не удалось отправить - {error}')
        raise exceptions.CannotSendMessage(
            f'Не вышло отправить сообщение {error}')


def get_api_answer(timestamp):
    """Получить ответ от API."""
    req_data = {
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    try:
        homework_statuses = requests.get(data=req_data, url=ENDPOINT)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.CannotGetAPIresponse(
                'Не удалось получить ответ от API, '
                f'Код ошибки: {homework_statuses.status_code}')
    except Exception as error:
        raise exceptions.CannotGetAPIresponse(
            f'Не удалось отправить данные API{error}')
    return homework_statuses.json()


def check_response(response):
    """Проверка валидности ответа от API."""
    if not isinstance(response, dict):
        raise TypeError('Ошибка - ответ от API не dict')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Ошибка - ключ homeworks - не список')
    if 'homeworks' not in response:
        raise KeyError('Не найден ключ homeworks')
    return homeworks


def parse_status(homework):
    """Инфо о статусе домашней работы."""
    if not homework.get('homework_name'):
        raise KeyError('Не найден ключ homework_name в ответе API')
    else:
        homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS.keys():
        raise exceptions.UnknownStatus(f'Статус домашки неизвестен'
                                       f' {HOMEWORK_VERDICTS}')
    else:
        return (f'Изменился статус проверки работы "{homework_name}". '
                f'{HOMEWORK_VERDICTS[homework_status]}')


def main():
    """Основная логика работы бота."""
    logger.debug('Бот начал работу!')
    if not check_tokens():
        return logging.critical('Не все токены на месте')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(timestamp)
            if check_response(response):
                notification = parse_status(
                    response.get('homeworks')[0]
                )
                send_message(bot, notification)
        except Exception as error:
            logger.error(f'Сбой в работе программы: {error}')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
