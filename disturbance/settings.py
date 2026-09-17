import hashlib
import logging
import os
import sys

from confy import env

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("BASE_DIR", BASE_DIR)

from ledger_api_client.settings_base import *  # noqa: F403

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ROOT_URLCONF = "disturbance.urls"
SITE_ID = 1
DEPT_DOMAINS = env("DEPT_DOMAINS", ["dpaw.wa.gov.au", "dbca.wa.gov.au"])
SUPERVISOR_STOP_CMD = env("SUPERVISOR_STOP_CMD")
SYSTEM_MAINTENANCE_WARNING = env("SYSTEM_MAINTENANCE_WARNING", 24)  # hours
DISABLE_EMAIL = env("DISABLE_EMAIL", False)
SHOW_DEBUG_TOOLBAR = env("SHOW_DEBUG_TOOLBAR", False)
MEDIA_APP_DIR = env("MEDIA_APP_DIR", "das")
MEDIA_APIARY_DIR = env("MEDIA_APIARY_DIR", "apiary")
SPATIAL_DATA_DIR = env("SPATIAL_DATA_DIR", "spatial_data")
ANNUAL_RENTAL_FEE_GST_EXEMPT = True
FILE_UPLOAD_MAX_MEMORY_SIZE = env("FILE_UPLOAD_MAX_MEMORY_SIZE", 15728640)
DATA_UPLOAD_MAX_MEMORY_SIZE = env("DATA_UPLOAD_MAX_MEMORY_SIZE", 10 * 1024 * 1024)  # 10MB
APIARY_MIGRATED_LICENCES_APPROVER = env("APIARY_MIGRATED_LICENCES_APPROVER", "jacinta.overman@dbca.wa.gov.au")
SHOW_API_ROOT = env("SHOW_API_ROOT", False)
SSO_SETTING_URL = env("SSO_SETTING_URL", "")
PRIVACY_POLICY_URL = env("PRIVACY_POLICY_URL", "")
TIME_ZONE = "Australia/Perth"

INSTALLED_APPS += [
    "reversion",
    "reversion_compare",
    "disturbance",
    "taggit",
    "rest_framework",
    "rest_framework_datatables",
    "rest_framework_gis",
    "reset_migrations",
    "ckeditor",
    "smart_selects",
    "ledger_api_client",
    "webtemplate_dbca",
    "django_vite",
    "appmonitor_client",
    "wagov_utils.components.sri_utils",
]

ADD_REVERSION_ADMIN = True

# maximum number of days allowed for a booking
WSGI_APPLICATION = "disturbance.wsgi.application"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": (
        "disturbance.renderers.ORJSONRenderer",
        "rest_framework_datatables.renderers.DatatablesRenderer",
    ),
    "EXCEPTION_HANDLER": "disturbance.exceptions.custom_exception_handler",
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 10,
}
GDAL_LIBRARY_PATH = os.environ.get(
    "GDAL_LIBRARY_PATH",
)
GEOS_LIBRARY_PATH = os.environ.get(
    "GEOS_LIBRARY_PATH",
)
USE_DJANGO_JQUERY = True

MIDDLEWARE_CLASSES += [
    "disturbance.middleware.FirstTimeNagScreenMiddleware",
    "disturbance.middleware.RevisionOverrideMiddleware",
    "disturbance.middleware.CacheControlMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "disturbance.middleware.PaymentSessionMiddleware",
]

# add the gzip middleware as the first entry in the list of middleware classes
MIDDLEWARE_CLASSES.insert(0, "django.middleware.gzip.GZipMiddleware")
MIDDLEWARE_CLASSES.insert(1, "disturbance.middleware.PerRequestCacheMiddleware")

TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "disturbance", "templates"))
TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "disturbance", "components", "ap_payments", "templates"))
TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "disturbance", "components", "approvals", "templates"))
TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "disturbance", "components", "compliances", "templates"))
TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "disturbance", "components", "emails", "templates"))
TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "disturbance", "components", "organisations", "templates"))
TEMPLATES[0]["DIRS"].append(os.path.join(BASE_DIR, "disturbance", "components", "proposals", "templates"))
TEMPLATES[0]["OPTIONS"]["context_processors"].append("disturbance.context_processors.apiary_url")

if "css_url" in BOOTSTRAP3:
    del BOOTSTRAP3["css_url"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": os.path.join(BASE_DIR, "disturbance", "cache"),
    }
}

CACHE_TIMEOUT_2_HOURS = 60 * 60 * 2
CACHE_KEY_FILE_EXTENSION_WHITELIST = "file-extension-whitelist"
FILE_SIZE_LIMIT_BYTES = env("FILE_SIZE_LIMIT_BYTES", 128000000)
MAX_NUM_ROWS_MODEL_EXPORT = 100000
NUMBER_OF_QUEUE_JOBS = 5

STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS.append(os.path.join(os.path.join(BASE_DIR, "disturbance", "static")))
STATICFILES_DIRS.append(os.path.join(os.path.join(BASE_DIR, "disturbance", "static", "disturbance_vue")))
DATA_UPLOAD_MAX_NUMBER_FIELDS = None
STATIC_URL = "/static/"

# Department details
SYSTEM_NAME = env("SYSTEM_NAME", "Apiary System")
SYSTEM_NAME_SHORT = env("SYSTEM_NAME_SHORT", "Apiary")
SITE_PREFIX = env("SITE_PREFIX")
SITE_DOMAIN = env("SITE_DOMAIN")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", SYSTEM_NAME_SHORT.lower() + "@" + SITE_DOMAIN).lower()
DEP_URL = env("DEP_URL", "www." + SITE_DOMAIN)
DEP_PHONE = env("DEP_PHONE", "(08) 9219 9000")
DEP_PHONE_SUPPORT = env("DEP_PHONE_SUPPORT", "(08) 9219 9000")
DEP_FAX = env("DEP_FAX", "(08) 9423 8242")
DEP_POSTAL = env("DEP_POSTAL", "Locked Bag 104, Bentley Delivery Centre, Western Australia 6983")
DEP_NAME = env("DEP_NAME", "Department of Biodiversity, Conservation and Attractions")
DEP_NAME_SHORT = env("DEP_NAME_SHORT", "DBCA")
SITE_URL = env("SITE_URL", "https://" + ".".join([SITE_PREFIX, SITE_DOMAIN]).strip("."))
PUBLIC_URL = env("PUBLIC_URL", SITE_URL)
EMAIL_FROM = env("EMAIL_FROM", "no-reply@" + SITE_DOMAIN).lower()
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "no-reply@" + SITE_DOMAIN).lower()
APIARY_ADMIN_GROUP = "Apiary Admin"
APIARY_PAYMENTS_OFFICERS_GROUP = "Apiary Payments Officers"
APPROVED_APIARY_EXTERNAL_USERS_GROUP = env("APPROVED_APIARY_EXTERNAL_USERS_GROUP", "Apiary Approved External Users")
CRON_EMAIL = env("CRON_EMAIL", "cron@" + SITE_DOMAIN).lower()
TENURE_SECTION = env("TENURE_SECTION", None)
ASSESSMENT_REMINDER_DAYS = env("ASSESSMENT_REMINDER_DAYS", 15)
OSCAR_BASKET_COOKIE_OPEN = "das_basket"
PAYMENT_SYSTEM_ID = env("PAYMENT_SYSTEM_ID", "S517")
PS_PAYMENT_SYSTEM_ID = PAYMENT_SYSTEM_ID
PAYMENT_SYSTEM_PREFIX = env("PAYMENT_SYSTEM_PREFIX", PAYMENT_SYSTEM_ID.replace("S", "0"))  # '0517'
os.environ["LEDGER_PRODUCT_CUSTOM_FIELDS"] = (
    "('ledger_description','quantity','price_incl_tax','price_excl_tax','oracle_code')"
)
APIARY_URL = env("APIARY_URL", [])
CRON_NOTIFICATION_EMAIL = env("CRON_NOTIFICATION_EMAIL", NOTIFICATION_EMAIL).lower()
VERSION_NO = "1.0.1"

BASE_URL = env("BASE_URL")

CRON_CLASSES = [
    "appmonitor_client.cron.CronJobAppMonitorClient",
    "disturbance.cron.CronJobProcessReportQueue",
    "disturbance.cron.CronJobCronTasks",
    "disturbance.cron.CronJobPopulateOrganisationProperties",
]

POPULATE_ORGANISATION_PROPERTIES_RUN_AT_TIMES = env("POPULATE_ORGANISATION_PROPERTIES_RUN_AT_TIMES", ["03:30"])

CKEDITOR_CONFIGS = {
    "default": {
        "toolbar": "full",
        "height": 300,
        "width": "100%",
    },
    "awesome_ckeditor": {
        "toolbar": "Basic",
    },
}

BUILD_TAG = env(
    "BUILD_TAG", hashlib.md5(os.urandom(32)).hexdigest()
)  # URL of the Dev app.js served by webpack & express
GEOCODING_ADDRESS_SEARCH_TOKEN = env("GEOCODING_ADDRESS_SEARCH_TOKEN", "ACCESS_TOKEN_NOT_FOUND")
RESTRICTED_RADIUS = 3000  # unit: [m]
DBCA_ABN = "38 052 249 024"
if env("CONSOLE_EMAIL_BACKEND", False):
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

if SHOW_DEBUG_TOOLBAR:

    def show_toolbar(request):
        return True

    MIDDLEWARE_CLASSES += [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
    ]
    INSTALLED_APPS += ("debug_toolbar",)
    INTERNAL_IPS = ("127.0.0.1", "localhost")

    # this dict removes check to dtermine if toolbar should display --> works for rks docker container
    DEBUG_TOOLBAR_CONFIG = {
        "RESULTS_CACHE_SIZE": 1000,
        "SHOW_TOOLBAR_CALLBACK": show_toolbar,
        "INTERCEPT_REDIRECTS": False,
    }

SITE_STATUS_DRAFT = "draft"
SITE_STATUS_PENDING = "pending"
SITE_STATUS_APPROVED = "approved"  # This status 'approved' is assigned to the ApiarySiteOnProposal object once it's approved.  'current' is assigned to the ApiarySiteOnApproval object after that.
SITE_STATUS_DENIED = "denied"
SITE_STATUS_CURRENT = "current"
SITE_STATUS_NOT_TO_BE_REISSUED = "not_to_be_reissued"
SITE_STATUS_SUSPENDED = "suspended"
SITE_STATUS_TRANSFERRED = (
    "transferred"  # This status 'transferred' is assigned to the old relationship (ApiarySiteOnApproval object)
)
SITE_STATUS_VACANT = "vacant"
SITE_STATUS_DISCARDED = "discarded"
BASE_EMAIL_TEXT = "disturbance/emails/apiary_base_email.txt"
BASE_EMAIL_HTML = "disturbance/emails/apiary_base_email.html"
ORGANISATION_PERMISSION_MODULE = "disturbance.permission"

HTTP_HOST_FOR_TEST = "localhost:9061"

# 1. Determine dynamic levels based on the DEBUG setting
default_log_level = "DEBUG" if DEBUG else "INFO"

# 2. Ensure the log directory exists so RotatingFileHandler doesn't crash
file_path = LOGGING.get("handlers", {}).get("file", {}).get("filename")
if file_path:
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

# 3. Clean out unwanted base loggers
LOGGERS_TO_REMOVE = {"wildlifecompliance", "wildlifelicensing", "log", "disturbance"}
LOGGING["loggers"] = {k: v for k, v in LOGGING.get("loggers", {}).items() if k not in LOGGERS_TO_REMOVE}

# 4. Apply formatters and general settings
LOGGING["disable_existing_loggers"] = False

LOGGING.setdefault("formatters", {})["verbose2"] = {
    "format": "%(levelname)s %(asctime)s %(name)s [Line:%(lineno)s][%(funcName)s] %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S",
}

# 5. Handlers configuration
if "console" in LOGGING.get("handlers", {}):
    LOGGING["handlers"]["console"]["formatter"] = "verbose2"
    LOGGING["handlers"]["console"]["level"] = default_log_level

if "file" in LOGGING.get("handlers", {}):
    LOGGING["handlers"]["file"]["formatter"] = "verbose2"
    LOGGING["handlers"]["file"]["level"] = "INFO"
    LOGGING["handlers"]["file"]["backupCount"] = 5
    LOGGING["handlers"]["file"]["encoding"] = "utf-8"

# 6. Root & Django Logger configuration
LOGGING["loggers"][""]["level"] = default_log_level

if "django" in LOGGING["loggers"]:
    LOGGING["loggers"]["django"]["handlers"] = ["file", "console"]
    LOGGING["loggers"]["django"]["level"] = "INFO"

# 7. Conditionally suppress noisy libraries only during DEBUG mode
CHATTY_LOGGERS = ["asyncio", "urllib3", "boto3", "botocore", "paramiko"]

for logger_name in CHATTY_LOGGERS:
    LOGGING["loggers"][logger_name] = {
        "level": "WARNING" if DEBUG else "INFO",
        "propagate": True,
    }

TEMPLATE_TITLE = "Apiary System"
TEMPLATE_HEADER_LOGO = "/static/disturbance/img/logo-park-stay-trunc.gif"
TEMPLATE_GROUP = "parkswildlife"

LEDGER_TEMPLATE = "bootstrap5"

# Use git commit hash for purging cache in browser for deployment changes
GIT_COMMIT_HASH = os.popen(f"cd {BASE_DIR}; git log -1 --format=%H").read()
GIT_COMMIT_DATE = os.popen(f"cd {BASE_DIR}; git log -1 --format=%cd").read()
if len(GIT_COMMIT_HASH) == 0:
    GIT_COMMIT_HASH = os.popen("cat /app/git_hash").read()
APPLICATION_VERSION = env("APPLICATION_VERSION", "1.0.0") + "-" + GIT_COMMIT_HASH[:7]

APIARY_EXTERNAL_URL = env("APIARY_EXTERNAL_URL", "External url not configured")
SESSION_ENGINE = "django.contrib.sessions.backends.file"
if env("EMAIL_INSTANCE") is not None and env("EMAIL_INSTANCE", "") != "PROD":
    SESSION_FILE_PATH = env("SESSION_FILE_PATH", BASE_DIR + "/session_store/")
    if not os.path.isdir(SESSION_FILE_PATH):
        os.mkdir(SESSION_FILE_PATH)
else:
    SESSION_FILE_PATH = env("SESSION_FILE_PATH", "/app/session_store/")

SESSION_COOKIE_SECURE = env("SESSION_COOKIE_SECURE", True)
CSRF_COOKIE_SECURE = env("CSRF_COOKIE_SECURE", True)
SESSION_COOKIE_AGE = env("SESSION_COOKIE_AGE", 3600)
LEDGER_UI_ACCOUNTS_MANAGEMENT = [
    {"first_name": {"options": {"view": True, "edit": True}}},
    {"last_name": {"options": {"view": True, "edit": True}}},
    {"residential_address": {"options": {"view": True, "edit": True}}},
    {"postal_address": {"options": {"view": True, "edit": True}}},
    {"phone_number": {"options": {"view": True, "edit": True}}},
    {"mobile_number": {"options": {"view": True, "edit": True}}},
    # {'dob' : {'options' : {'view': False, 'edit': False}}},
    {"postal_same_as_residential": {"options": {"view": True, "edit": True}}},
    {"address_details": {"options": {"billing_address": {"show": False}}}},
]
LEDGER_UI_SYSTEM_ACCOUNTS_MANAGEMENT["address_details"]["options"]["billing_address"]["show"] = False
LEDGER_UI_ORGANISATION_MANAGEMENT = [
    {"organisation_name": {"options": {"view": True, "edit": True}}},
    {"organisation_abn": {"options": {"view": True, "edit": True}}},
    {"postal_address": {"options": {"view": True, "edit": True}}},
]

LEDGER_UI_ACCOUNTS_MANAGEMENT_KEYS = []
for am in LEDGER_UI_ACCOUNTS_MANAGEMENT:
    LEDGER_UI_ACCOUNTS_MANAGEMENT_KEYS.append(list(am.keys())[0])

LEDGER_UI_CARDS_MANAGEMENT = env("LEDGER_UI_CARDS_MANAGEMENT", True)

MIDDLEWARE = MIDDLEWARE_CLASSES

CONTAINER_IMAGE_TAG = env("CONTAINER_IMAGE_TAG", "CONTAINER_IMAGE_TAG ENV Not Set")

RUNNING_DEVSERVER = len(sys.argv) > 1 and sys.argv[1] == "runserver"

# Sentry settings
SENTRY_DSN = env("SENTRY_DSN", default=None)
SENTRY_SAMPLE_RATE = env("SENTRY_SAMPLE_RATE", default=1.0)  # Error sampling rate
SENTRY_TRANSACTION_SAMPLE_RATE = env("SENTRY_TRANSACTION_SAMPLE_RATE", default=0.0)  # Transaction sampling
if not RUNNING_DEVSERVER and SENTRY_DSN and EMAIL_INSTANCE:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        sample_rate=SENTRY_SAMPLE_RATE,
        traces_sample_rate=SENTRY_TRANSACTION_SAMPLE_RATE,
        environment=EMAIL_INSTANCE.lower(),
        release=CONTAINER_IMAGE_TAG,
    )

# Make sure this returns true when in local development
# so you can use the vite dev server with hot module reloading
DJANGO_VITE_DEV_MODE = RUNNING_DEVSERVER and EMAIL_INSTANCE == "DEV" and DEBUG is True

STATIC_URL_PREFIX = "/static/disturbance_vue/" if DJANGO_VITE_DEV_MODE else "disturbance_vue/"

DJANGO_VITE = {
    "default": {
        "dev_mode": DJANGO_VITE_DEV_MODE,
        "manifest_path": os.path.join(BASE_DIR, "disturbance", "static", "disturbance_vue", "manifest.json"),
        "dev_server_host": "localhost",  # Default host for vite (can change if needed)
        "dev_server_port": 5173,  # Default port for vite (can change if needed)
        "static_url_prefix": STATIC_URL_PREFIX,
    }
}
VUE3_ENTRY_SCRIPT = env(  # This is not a reserved keyword.
    "VUE3_ENTRY_SCRIPT",
    "src/main.js",  # This path will be auto prefixed with the static_url_prefix from DJANGO_VITE above
)  # Path of the vue3 entry point script served by vite

LEDGER_SYSTEM_ID = env(
    "PAYMENT_INTERFACE_SYSTEM_PROJECT_CODE",
    "PAYMENT_INTERFACE_SYSTEM_PROJECT_CODE not configured",
)
LEDGER_USER = env("LEDGER_USER", "")
LEDGER_PASS = env("LEDGER_PASS", "")

KB_USER = env("KB_USER", LEDGER_USER)
KB_PASSWORD = env("KB_PASSWORD", LEDGER_PASS)
KB_SERVER_URL = env("KB_SERVER_URL", "https://kb.dbca.wa.gov.au/")
KB_BASEMAP_STREET_LAYER = env("KB_BASEMAP_STREET_LAYER", "kaartdijin-boodja-public:mapbox-streets-public")
KB_BASEMAP_SATELLITE_LAYER = env("KB_BASEMAP_SATELLITE_LAYER", "kaartdijin-boodja-public:mapbox-satellite-public")
KB_TENURE_GEOSERVER_URL = env("KB_TENURE_GEOSERVER_URL", "https://kb.dbca.wa.gov.au/geoserver/ows")
KB_DBCA_LEGISLATED_TENURE_LAYER = env(
    "KB_DBCA_LEGISLATED_TENURE_LAYER", "kaartdijin-boodja-public:CPT_DBCA_LEGISLATED_TENURE"
)
KB_TENURE_PROPERY_NAME = env("KB_TENURE_PROPERY_NAME", "LEG_TENURE")

CSRF_TRUSTED_ORIGINS_STRING = decouple.config("CSRF_TRUSTED_ORIGINS", default="[]")
CSRF_TRUSTED_ORIGINS = json.loads(str(CSRF_TRUSTED_ORIGINS_STRING))
FILE_UPLOAD_PERMISSIONS = None
