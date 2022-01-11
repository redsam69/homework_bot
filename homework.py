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

RETRY_TIME = 5  # 600
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
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def get_api_answer(current_timestamp):
    """Получение данных от сервера."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    homework_statuses = requests.get(ENDPOINT, headers=HEADERS, params=params)
    if homework_statuses.status_code != 200:
        raise Exception('Сервер не доступен')
    logger.info('Сервер отвечает')
    return homework_statuses.json()


def check_response(response):
    """Проверка информации."""
    resp_homework = response['homeworks']
    if not isinstance(response, dict):
        raise Exception('Ошибка homeworks не dict')
    # resp_homework = response.get('homeworks') - не проходит pytest
    if resp_homework is None:
        raise Exception('Ошибка homeworks none')
    if (type(resp_homework) != list):
        raise Exception('Ошибка в homeworks отсутствует list')
    return resp_homework


def parse_status(homework):
    """Обрабока домашней работы."""
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    verdict = HOMEWORK_STATUSES[homework_status]
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
                # send_message(bot, parse_status_update)
                print(parse_status_update)
            current_timestamp = response.get('current_date', current_timestamp)
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if str(error) != str(error_temp):
                error_temp = error
                send_message(bot, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
