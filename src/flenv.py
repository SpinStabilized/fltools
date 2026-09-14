"""
Functions for retrieving the FLDigi environmental variables that are exported
when the EXEC macro is invoked.
"""
import os

# FLDigi Env Prefix
# Define the prefix you are looking for
prefix = "FLDIGI_"

# Maps the FLDigi macro environment variable names to the ADIF field names
# expected by the QRZ Logbook API.
FLENV_KEY_MAP: dict[str, str] = {
    'FLDIGI_LOGBOOK_ARRL_SECT_IN': 'arrl_sect',
    'FLDIGI_LOGBOOK_BAND': 'band',
    'FLDIGI_LOGBOOK_CALL': 'call',
    'FLDIGI_LOGBOOK_CLASS_IN': 'class',
    'FLDIGI_LOGBOOK_CONTINENT': 'cont',
    'FLDIGI_LOGBOOK_COUNTRY': 'country',
    'FLDIGI_LOGBOOK_COUNTY': 'cnty',
    'FLDIGI_LOGBOOK_CQZ': 'cqz',
    'FLDIGI_LOGBOOK_DATE_OFF': 'qso_date_off',
    'FLDIGI_LOGBOOK_DATE': 'qso_date',
    'FLDIGI_LOGBOOK_DXCC': 'dxcc',
    'FLDIGI_LOGBOOK_FREQUENCY': 'freq',
    'FLDIGI_LOGBOOK_IOTA': 'iota',
    'FLDIGI_LOGBOOK_ITUZ': 'ituz',
    'FLDIGI_LOGBOOK_LOCATOR': 'gridsquare',
    'FLDIGI_LOGBOOK_MODE': 'mode',
    'FLDIGI_LOGBOOK_NAME': 'name',
    'FLDIGI_LOGBOOK_NOTES': 'notes',
    'FLDIGI_LOGBOOK_QSL_VIA': 'qsl_via',
    'FLDIGI_LOGBOOK_QTH': 'qth',
    'FLDIGI_LOGBOOK_RST_IN': 'rst_rcvd',
    'FLDIGI_LOGBOOK_RST_OUT': 'rst_sent',
    'FLDIGI_LOGBOOK_SERNO_IN': 'srx',
    'FLDIGI_LOGBOOK_SERNO_OUT': 'stx',
    'FLDIGI_LOGBOOK_STATE': 'state',
    'FLDIGI_LOGBOOK_TIME_OFF': 'time_off',
    'FLDIGI_LOGBOOK_TIME_ON': 'time_on',
    'FLDIGI_LOGBOOK_TX_PWR': 'tx_pwr',
    'FLDIGI_LOGBOOK_VE_PROV': 've_prov',
}

# ADIF fields QRZ's logbook API needs at minimum to accept a QSO record.
QRZ_REQUIRED_ADIF_FIELDS: list[str] = [
        'call', 'qso_date', 'time_on', 'band', 'mode',
    ]

def get_env() -> dict[str, str]:
    # Filter the environment variables
    filtered_env: dict[str, str] = {
        key: value.strip()
        for key, value in os.environ.items() 
        if key.startswith(prefix)
    }
    return filtered_env