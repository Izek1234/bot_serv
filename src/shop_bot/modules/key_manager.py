import logging
from datetime import datetime, timedelta
from shop_bot.data_manager.database import add_new_key, get_setting
from shop_bot.modules.xui_api import create_or_update_key_on_host  # ✅ существует

logger = logging.getLogger(__name__)

# Замените это на ваш способ получения списка хостов
# Например: from shop_bot.data_manager.database import get_all_hosts
# Или импортируйте из конфига
from shop_bot.data_manager.database import get_all_hosts  # ← убедитесь, что она есть или создайте

async def create_keys_on_all_hosts_and_get_links(user_id: int) -> list[str]:

    hosts = get_all_hosts()  # ← эта функция ДОЛЖНА быть определена где-то у вас
    if not hosts:
        logger.warning("No hosts found for subscription!")
        return []

    links = []
    now = datetime.now()

    # Настройки ключа
    duration_days = int(get_setting("trial_duration_days") or 1)
    expiry = now + timedelta(days=duration_days)

    for host in hosts:
        host_name = host["host_name"]
        try:
            email = f"{user_id}_{int(now.timestamp())}@{host_name}"  # уникальный email

            # Создаём клиента на хосте
            result = await create_or_update_key_on_host(
                host_name=host_name,
                email=email,
                days_to_add=duration_days  # ← передаём количество дней, а не дату
            )

            if result:
                client_id = result["client_uuid"]
                link = result["connection_string"]
            else:
                logger.error(f"Не удалось создать ключ на {host_name}")
                continue

            # Сохраняем в БД
            add_new_key(user_id, host_name, client_id, email, int(expiry.timestamp() * 1000))

            if link:
                links.append(link)
            else:
                logger.warning(f"Пустая ссылка для {host_name}")

        except Exception as e:
            logger.error(f"Ошибка создания ключа на {host_name} для {user_id}: {e}")

    return links