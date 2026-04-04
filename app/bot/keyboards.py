from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Customers", callback_data="menu_customers"),
                InlineKeyboardButton("📝 Quotations", callback_data="menu_quotations"),
            ],
            [
                InlineKeyboardButton("💰 Invoices", callback_data="menu_invoices"),
                InlineKeyboardButton("📅 Calendar", callback_data="menu_calendar"),
            ],
            [
                InlineKeyboardButton("📊 Reports", callback_data="menu_reports"),
                InlineKeyboardButton("⚙️ Settings", callback_data="menu_settings"),
            ],
        ]
    )


def back_button(callback_data: str = "back_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("« Back to Menu", callback_data=callback_data)]]
    )


def confirm_cancel_keyboard(
    confirm_data: str = "confirm", cancel_data: str = "cancel"
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Confirm", callback_data=confirm_data),
                InlineKeyboardButton("❌ Cancel", callback_data=cancel_data),
            ]
        ]
    )


def customer_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔍 Search Customer", callback_data="cust_search"),
                InlineKeyboardButton("➕ New Customer", callback_data="cust_new"),
            ],
            [
                InlineKeyboardButton("📋 All Customers", callback_data="cust_list"),
            ],
            [
                InlineKeyboardButton("« Back to Menu", callback_data="back_main"),
            ],
        ]
    )


def quotation_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ New Quotation", callback_data="quot_new"),
            ],
            [
                InlineKeyboardButton("📋 All Quotations", callback_data="quot_list"),
                InlineKeyboardButton("📊 By Status", callback_data="quot_by_status"),
            ],
            [
                InlineKeyboardButton("« Back to Menu", callback_data="back_main"),
            ],
        ]
    )


def invoice_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Create from Quotation", callback_data="inv_from_quot"
                ),
            ],
            [
                InlineKeyboardButton("💳 Record Payment", callback_data="inv_payment"),
                InlineKeyboardButton("📋 All Invoices", callback_data="inv_list"),
            ],
            [
                InlineKeyboardButton("« Back to Menu", callback_data="back_main"),
            ],
        ]
    )


def calendar_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📅 View Schedule", callback_data="cal_view"),
                InlineKeyboardButton("➕ Book Slot", callback_data="cal_book"),
            ],
            [
                InlineKeyboardButton("« Back to Menu", callback_data="back_main"),
            ],
        ]
    )
