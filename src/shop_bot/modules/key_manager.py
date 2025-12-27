import logging
from datetime import datetime, timedelta
from shop_bot.data_manager.database import add_new_key, get_setting
from shop_bot.modules.xui_api import create_or_update_key_on_host  # ✅ существует

logger = logging.getLogger(__name__)

# Замените это на ваш способ получения списка хостов
# Например: from shop_bot.data_manager.database import get_all_hosts
# Или импортируйте из конфига
from shop_bot.data_manager.database import get_all_hosts  # ← убедитесь, что она есть или создайте

from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

async def create_keys_on_all_hosts_and_get_clash_proxies(user_id: int) -> list[dict]:
    hosts = get_all_hosts()
    if not hosts:
        logger.warning("No hosts found for subscription!")
        return []

    proxies = []
    now = datetime.now()
    duration_days = int(get_setting("trial_duration_days") or 1)
    expiry_timestamp = int((now + timedelta(days=duration_days)).timestamp())

    for host in hosts:
        host_name = host["host_name"]
        try:
            email = f"{user_id}_{int(now.timestamp())}@{host_name}"

            # Предполагаем, что эта функция теперь возвращает СТРУКТУРУ, а не URI
            proxy_config = await create_or_update_key_on_host(
                host_name=host_name,
                email=email,
                days_to_add=duration_days
            )

            if not proxy_config or not proxy_config.get("uuid"):
                logger.error(f"Failed to create key on {host_name}")
                continue

            # Формируем Clash Meta-совместимый прокси (VLESS over TCP+TLS или WS)
            proxy = {
                "name": f"{host.get('display_name', host_name)}",
                "type": "vless",
                "server": host["address"],          # IP или домен
                "port": host["port"],               # порт инбаунда
                "uuid": proxy_config["uuid"],
                "network": host.get("network", "tcp"),
                "tls": host.get("tls", True),
                "udp": True,
                "skip-cert-verify": True,
            }

            # Дополнительные параметры для TLS
            if proxy["tls"]:
                sni = host.get("sni") or host["address"]
                proxy["servername"] = sni  # Clash Meta использует 'servername', не 'sni'
                fp = host.get("fingerprint", "chrome")
                proxy["fingerprint"] = fp

            # WebSocket
            if proxy["network"] == "ws":
                proxy["ws-opts"] = {
                    "path": host.get("path", "/"),
                    "headers": {"Host": host.get("host_header", sni) if proxy["tls"] else host.get("host_header", host["address"])}
                }

            # Flow (xtls-rprx-vision и т.п.) — только если поддерживается Clash Meta
            if host.get("flow"):
                proxy["flow"] = host["flow"]

            # Сохраняем в БД (можно использовать те же данные)
            add_new_key(
                user_id=user_id,
                host_name=host_name,
                client_id=proxy_config["uuid"],
                email=email,
                expiry=int(expiry_timestamp * 1000)
            )

            proxies.append(proxy)

        except Exception as e:
            logger.error(f"Error creating key on {host_name} for {user_id}: {e}", exc_info=True)

    return proxies