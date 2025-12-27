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

async def create_keys_on_all_hosts_and_get_clash_proxies(user_id: int) -> list[dict]:
    hosts = get_all_hosts()
    if not hosts:
        logger.warning("No hosts available.")
        return []

    proxies = []
    duration_days = int(get_setting("trial_duration_days") or 1)
    expiry_timestamp = int((datetime.now() + timedelta(days=duration_days)).timestamp())

    for host in hosts:
        host_name = host.get("host_name")
        if not host_name:
            continue

        email = f"{user_id}_{int(datetime.now().timestamp())}@{host_name}"

        try:
            result = await create_or_update_key_on_host(
                host_name=host_name,
                email=email,
                days_to_add=duration_days
            )

            if not result or not result.get("connection_string"):
                logger.error(f"No connection_string for {host_name}")
                continue

            # Парсим URI → Clash-прокси
            proxy = parse_vless_uri_to_clash(result["connection_string"])
            if not proxy:
                logger.error(f"Failed to parse connection_string for {host_name}")
                continue

            # Сохраняем в БД
            add_new_key(
                user_id=user_id,
                host_name=host_name,
                xui_client_uuid=result["client_uuid"],
                key_email=email,
                expiry_timestamp_ms=int(expiry_timestamp * 1000)
            )

            proxies.append(proxy)

        except Exception as e:
            logger.error(f"Error on {host_name}: {e}", exc_info=True)

    return proxies

def parse_vless_uri_to_clash(uri: str) -> dict | None:
    if not uri or not uri.startswith("vless://"):
        return None

    try:
        # Убираем схему
        s = uri[8:]

        # Извлекаем имя (после #)
        if "#" in s:
            s, name = s.split("#", 1)
            name = urllib.parse.unquote(name)
        else:
            name = "VLESS"

        # Разделяем UUID@host:port и параметры
        if "?" in s:
            main_part, query_part = s.split("?", 1)
        else:
            main_part, query_part = s, ""

        # UUID и адрес
        uuid, host_port = main_part.split("@", 1)
        if ":" in host_port:
            server, port_str = host_port.rsplit(":", 1)
            port = int(port_str)
        else:
            server = host_port
            port = 443

        # Парсим параметры
        params = urllib.parse.parse_qs(query_part, keep_blank_values=True)
        param = lambda key, default=None: params.get(key, [default])[0]

        network = param("type", "tcp")
        security = param("security", "")
        sni = param("sni", server)
        fp = param("fp", "chrome")
        flow = param("flow", "")

        proxy = {
            "name": name,
            "type": "vless",
            "server": server,
            "port": port,
            "uuid": uuid,
            "network": network,
            "udp": True,
            "skip-cert-verify": True,
        }

        if security == "reality":
            proxy["reality"] = True
            proxy["fingerprint"] = fp
            proxy["server"] = server
            proxy["port"] = port

            pbk = param("pbk")
            if pbk:
                proxy["public-key"] = pbk

            sid = param("sid")
            if sid:
                proxy["short-id"] = sid

            spx = param("spx")
            if spx:
                proxy["spider-x"] = urllib.parse.unquote(spx)

            if sni:
                proxy["servername"] = sni

        elif security == "tls":
            proxy["tls"] = True
            proxy["fingerprint"] = fp
            proxy["servername"] = sni

        else:
            # Без шифрования (небезопасно, но возможно)
            pass

        if flow:
            proxy["flow"] = flow

        # WebSocket (если network=ws)
        if network == "ws":
            proxy["ws-opts"] = {
                "path": param("path", "/"),
                "headers": {"Host": param("host", sni)}
            }

        return proxy

    except Exception as e:
        logger.error(f"Failed to parse VLESS URI: {e}")
        return None