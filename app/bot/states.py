from enum import IntEnum, auto


class CustomerStates(IntEnum):
    SEARCH_INPUT = auto()
    SELECT_RESULT = auto()
    VIEW_DETAIL = auto()
    CREATE_NAME = auto()
    CREATE_PHONE = auto()
    CREATE_ADDRESS = auto()
    CREATE_EMAIL = auto()
    CREATE_NOTES = auto()
    CONFIRM_CREATE = auto()
    EDIT_FIELD = auto()
    EDIT_VALUE = auto()


class QuotationStates(IntEnum):
    SELECT_CUSTOMER = auto()
    SEARCH_CUSTOMER = auto()
    CREATE_CUSTOMER_NAME = auto()
    CREATE_CUSTOMER_PHONE = auto()
    CREATE_CUSTOMER_ADDRESS = auto()
    ENTER_JOB_LOCATION = auto()
    SELECT_PATTERN = auto()
    ENTER_RATE = auto()
    ENTER_AREA = auto()
    ENTER_LUMPSUM = auto()
    CUSTOM_DESCRIPTION = auto()
    CUSTOM_UNIT = auto()
    CUSTOM_QTY = auto()
    CUSTOM_PRICE = auto()
    ADD_MORE_OR_DONE = auto()
    ENTER_DISCOUNT = auto()
    ADD_NOTES = auto()
    CONFIRM = auto()


class InvoiceStates(IntEnum):
    SELECT_QUOTATION = auto()
    SET_DUE_DAYS = auto()
    CONFIRM = auto()
    SELECT_INVOICE = auto()
    ENTER_PAYMENT = auto()


class CalendarStates(IntEnum):
    SELECT_CUSTOMER = auto()
    SEARCH_CUSTOMER = auto()
    SELECT_DATE = auto()
    ENTER_TIME = auto()
    ENTER_DETAILS = auto()
    CONFIRM_BOOKING = auto()


class SettingsStates(IntEnum):
    MENU = auto()
    ADD_PATTERN_NAME = auto()
    ADD_PATTERN_RATE = auto()
    EDIT_PATTERN_SELECT = auto()
    EDIT_PATTERN_RATE = auto()
    CONFIRM_TOGGLE = auto()
