import os
import sys
import time
import logging
from logging import StreamHandler
import requests
import telegram

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(stream=sys.stdout)
formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELEGRAM_RETRY_TIME = 600

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка в боттелеграмм."""
    logger.info(f'message send {message}')
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error as exc:
        raise exc('Сбой отправки в телеграмм')


def get_api_answer(current_timestamp):
    """Получение данных от сервера."""
    logging.debug('Получение ответа от сервера')
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(ENDPOINT,
                                         headers=HEADERS,
                                         params=params)
    except requests.exceptions.RequestException:
        logger.error('Ошибка запроса от сервера', exc_info=True)
        return {}
    if homework_statuses.status_code != 200:
        raise Exception('Сервер не доступен')
    logger.info('Сервер отвечает')
    try:
        py_request = homework_statuses.json()
    except ValueError:
        logger.error('Ответ сервера не в json ', exc_info=True)
        return {}
    logging.debug('Получен ответ от сервера')
    return py_request


def check_response(response):
    """Проверка информации."""
    logging.debug('Проверка ответа API на корректность')
    if not isinstance(response, dict):
        raise TypeError('Ошибка homeworks не dict')
    if not isinstance(response['homeworks'], list):
        raise Exception('response["homeworks"] не является списком')
    if 'homeworks' not in response:
        raise KeyError(
            'Отсутствует ключ homeworks в response'
        )
    if len(response['homeworks']) == 0:
        logger.debug('Нет новых заданий')
        raise ValueError('Нет новых заданий')
    logging.debug('API проверен на корректность')
    return response['homeworks']


def parse_status(homework):
    """Обрабока домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError(
            'Отсутствует ключ homework_name в homework'
        )
    homework_name = homework.get('homework_name')
    if 'status' not in homework:
        raise KeyError(
            'Отсутствует ключ status в homework'
        )
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_STATUSES:
        raise KeyError(
            'Обнаружен новый статус, отсутствующий в списке!'
        )
    verdict = HOMEWORK_STATUSES.get(homework_status)
    logger.info(f'Вердикт проекта {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных."""
    if PRACTICUM_TOKEN is None:
        logger.critical('Отсутствует обязательная переменная окружения: '
                        '"PRACTICUM_TOKEN"')
        return False
    if TELEGRAM_TOKEN is None:
        logger.critical('Отсутствует обязательная переменная окружения: '
                        '"TELEGRAM_TOKEN"')
        return False
    if TELEGRAM_CHAT_ID is None:
        logger.critical('Отсутствует обязательная переменная окружения: '
                        '"TELEGRAM_CHAT_ID"')
        return False
    return True


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    error_temp = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            check_response_result = check_response(response)
            if check_response_result:
                parse_status_update = parse_status(check_response_result[0])
                send_message(bot, parse_status_update)
            current_timestamp = response.get('current_date', current_timestamp)
            time.sleep(TELEGRAM_RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message, exc_info=True)
            if str(error) != str(error_temp):
                error_temp = error
                send_message(bot, message)
            time.sleep(TELEGRAM_RETRY_TIME)


if __name__ == '__main__':
    if check_tokens():
        main()
