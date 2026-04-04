from telegram.ext import filters

from app.config import settings


def _get_allowed_user_ids() -> list[int]:
    ids = [settings.ADMIN_CHAT_ID]
    if settings.ALLOWED_USER_IDS:
        ids.extend(int(uid.strip()) for uid in settings.ALLOWED_USER_IDS.split(",") if uid.strip())
    return ids


admin_filter = filters.User(user_id=_get_allowed_user_ids())
