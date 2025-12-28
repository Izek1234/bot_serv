import logging
from datetime import datetime, timedelta
from shop_bot.data_manager.database import add_new_key, get_setting
from shop_bot.modules.xui_api import create_or_update_key_on_host  # ✅ существует
import urllib.parse


logger = logging.getLogger(__name__)

# Замените это на ваш способ получения списка хостов
# Например: from shop_bot.data_manager.database import get_all_hosts
# Или импортируйте из конфига
from shop_bot.data_manager.database import get_all_hosts  # ← убедитесь, что она есть или создайте

from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

async def create_keys_on_all_hosts_and_get_links(user_id: int) -> list[str]:
    hosts = get_all_hosts()
    if not hosts:
        logger.warning("No hosts available for subscription.")
        return []

    links = []
    duration_days = int(get_setting("trial_duration_days") or 1)

    for host in hosts:
        host_name = host["host_name"]
        email = f"{user_id}_{int(datetime.now().timestamp())}@{host_name}"
        logger.error(hosts)
        try:
            result = await create_or_update_key_on_host(
                host_name=host_name,
                email=email,
                days_to_add=duration_days
            )
            logger.error(result)
            if not result:
                logger.error(f"Failed to create key on {host_name}")
                continue

            # Сохраняем в БД
            add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid=result["client_uuid"],
                key_email=email,
                expiry_timestamp_ms=result["expiry_timestamp_ms"]
            )

            if result["connection_string"]:
                links.append(result["connection_string"])

        except Exception as e:
            logger.error(f"Exception creating key on {host_name}: {e}")

    return links