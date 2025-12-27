import logging
from datetime import datetime, timedelta
from shop_bot.data_manager.database import add_key_to_db, get_setting
from shop_bot.modules.xui_api import create_client_on_host

logger = logging.getLogger(__name__)

# Замените это на ваш способ получения списка хостов
# Например: from shop_bot.data_manager.database import get_all_hosts
# Или импортируйте из конфига
from shop_bot.data_manager.database import get_all_hosts  # ← убедитесь, что она есть или создайте

async def create_keys_on_all_hosts_and_get_links(user_id: int) -> list[str]:
    """
    Создаёт по одному новому ключу на КАЖДОМ хосте для пользователя.
    Возвращает список connection_string.
    НЕ проверяет существующие ключи — создаёт всегда новые.
    """
    hosts = get_all_hosts()  # ← эта функция ДОЛЖНА быть определена где-то у вас
    if not hosts:
        logger.warning("No hosts found for subscription!")
        return []

    links = []
    now = datetime.now()

    # Настройки ключа
    duration_days = int(get_setting("trial_duration_days") or 1)
    traffic_gb = int(get_setting("trial_traffic_gb") or 1)
    expiry = now + timedelta(days=duration_days)
    traffic_limit = traffic_gb * (1024 ** 3)  # в байтах

    for host in hosts:
        host_name = host["host_name"]
        try:
            email = f"{user_id}_{int(now.timestamp())}@{host_name}"  # уникальный email

            # Создаём клиента на хосте
            client_id, link = await create_client_on_host(
                host_name=host_name,
                user_id=user_id,
                email=email,
                expiry=expiry,
                traffic_limit=traffic_limit
            )

            # Сохраняем в БД
            add_key_to_db(
                user_id=user_id,
                host_name=host_name,
                client_id=client_id,
                expiry_date=expiry.isoformat(),
                total_gb=traffic_gb,
                price=0,
                is_trial=True
            )

            if link:
                links.append(link)
            else:
                logger.warning(f"Пустая ссылка для {host_name}")

        except Exception as e:
            logger.error(f"Ошибка создания ключа на {host_name} для {user_id}: {e}")

    return links