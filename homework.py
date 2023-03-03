import logging
import os
import sys
from http import HTTPStatus
import time

import requests
import telegram
from dotenv import load_dotenv

import exceptions

logger = logging.getLogger(__name__)

load_dotenv()

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверка переменных."""
    token_vars = (
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID),
    )
    check_token = True
    for name, token in token_vars:
        if token is None:
            logging.critical(f'Не найден токен {name}')
            check_token = False
    return check_token


def send_message(bot, message):
    """Отправляем сообщение."""
    try:
        logging.info('Отправка сообщения...')
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.debug(f'Сообщение {message} отправлено')
        return True
    except telegram.error.TelegramError as error:
        logging.error(f'Сообщение не удалось отправить - {error}')
        return False


def get_api_answer(timestamp):
    """Получить ответ от API."""
    req_data = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp},
    }
    logger.info(
        'Начинается запрос к API {url},{headers},{params}'.format(**req_data)
    )
    try:
        homework_statuses = requests.get(**req_data)
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.CannotGetAPIresponse(
                'Не удалось получить ответ от API'
                f'Код ответа - {homework_statuses.status_code}'
                f'Причина - {homework_statuses.reason}'
                f'Текст - {homework_statuses.text}')
        return homework_statuses.json()
    except Exception as error:
        raise ConnectionError(
            f'Возникла ошибка {error}'
            'url = {url},'
            'headers = {headers},'
            'params = {params}'.format(**req_data)
        )


def check_response(response):
    """Проверка валидности ответа от API."""
    if not isinstance(response, dict):
        raise TypeError('Ошибка - ответ от API не dict')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Ошибка - ключ homeworks - не список')
    if 'homeworks' not in response:
        raise exceptions.EmptyAPIResponse('Получен пустой ответ от сервера')
    return homeworks


def parse_status(homework):
    """Инфо о статусе домашней работы."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise KeyError('Не найден ключ homework_name в ответе API')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError('Статус домашки неизвестен')
    return (f'Изменился статус проверки работы "{homework_name}". '
            f'{HOMEWORK_VERDICTS[homework_status]}')


def main():
    """Основная логика работы бота."""
    logger.debug('Бот начал работу!')
    if not check_tokens():
        logging.critical('Не все токены на месте')
        raise KeyError('Не все токены на месте')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    prev_report = {
        'name_messages': '',
        'output': ''
    }
    current_report = {
        'name_messages': '',
        'output': ''
    }
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                homework = homeworks[0]
                current_report['name_messages'] = homework.get('homework_name')
                current_report['output'] = parse_status(homework)
            else:
                current_report['output'] = 'Нет новых статусов.'
            if current_report != prev_report:
                if send_message(bot, current_report['output']):
                    prev_report = current_report.copy()
                    timestamp = response.get('current_date', timestamp)
            else:
                logging.debug('Нет новых статусов')
        except exceptions.EmptyAPIResponse as error:
            logger.error(f'Пустой ответ от API: {error}', exc_info=True)
        except Exception as error:
            error_str = f'Сбой в работе программы: {error}'
            logger.error(error_str, exc_info=True)
            current_report['output'] = error_str
            if current_report != prev_report:
                send_message(bot, error_str)
                prev_report = current_report.copy()
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s, %(levelname)s, %(message)s,'
               ' %(lineno)d, %(funcName)s',
        level=logging.INFO,
    )
    handler_stream = logging.StreamHandler(sys.stdout)
    handler_file = logging.FileHandler(
        os.path.join(f'{BASE_DIR}/main.log'),
        encoding='UTF-8',
    )
    logger.addHandler(handler_stream)
    logger.addHandler(handler_file)
    main()
