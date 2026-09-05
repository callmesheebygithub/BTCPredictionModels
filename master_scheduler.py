import os
import sys
import time
import subprocess
import logging
from datetime import datetime, timedelta

from zoneinfo import ZoneInfo


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PYTHON = sys.executable

TIMEZONE = ZoneInfo("Asia/Karachi")

# ------------------------------------------------------------
# DAILY SCHEDULE
# Pakistan Standard Time
# ------------------------------------------------------------

DAILY_HOUR = 5
DAILY_MINUTE = 10

# ------------------------------------------------------------
# WEEKLY SCHEDULE
# Sunday = 6
# Same time: 5:10 AM
# ------------------------------------------------------------

WEEKLY_DAY = 6
WEEKLY_HOUR = 5
WEEKLY_MINUTE = 10


# ============================================================
# MODULES
# ============================================================

DATA_MODULE = "YahooFinanceDataOnce.py"
FEATURE_MODULE = "prepare_btc_ml_data.py"
EVALUATION_MODULE = "evaluate_predictions.py"
PREDICTION_MODULE = "daily_prediction.py"
WEEKLY_MODULE = "weekly_model_comparison.py"


# ============================================================
# LOGGING
# ============================================================

LOG_DIR = os.path.join(
    BASE_DIR,
    "logs"
)

os.makedirs(
    LOG_DIR,
    exist_ok=True
)

LOG_FILE = os.path.join(
    LOG_DIR,
    "master_scheduler.log"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8"
        ),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


# ============================================================
# TIME
# ============================================================

def get_now():

    return datetime.now(
        TIMEZONE
    )


# ============================================================
# RUN MODULE
# ============================================================

def run_module(module_name):

    module_path = os.path.join(
        BASE_DIR,
        module_name
    )

    if not os.path.exists(module_path):

        logger.error(
            f"Module not found: {module_path}"
        )

        return False

    logger.info(
        f"STARTING MODULE: {module_name}"
    )

    start_time = time.time()

    try:

        result = subprocess.run(
            [
                PYTHON,
                module_path
            ],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )

        elapsed = time.time() - start_time

        if result.stdout:

            logger.info(
                f"\n{result.stdout}"
            )

        if result.stderr:

            logger.warning(
                f"\n{result.stderr}"
            )

        if result.returncode != 0:

            logger.error(
                f"{module_name} FAILED "
                f"| Exit Code: {result.returncode} "
                f"| Time: {elapsed:.2f}s"
            )

            return False

        logger.info(
            f"{module_name} COMPLETED "
            f"| Time: {elapsed:.2f}s"
        )

        return True

    except Exception as e:

        logger.exception(
            f"Exception while running "
            f"{module_name}: {e}"
        )

        return False


# ============================================================
# DAILY PIPELINE
# ============================================================

def run_daily_pipeline():

    logger.info("")
    logger.info("=" * 80)
    logger.info("DAILY BTC PIPELINE STARTED")
    logger.info("=" * 80)

    # --------------------------------------------------------
    # STEP 1
    # Download latest BTC data
    # --------------------------------------------------------

    logger.info(
        "STEP 1/4: Updating BTC historical data..."
    )

    if not run_module(DATA_MODULE):

        logger.error(
            "Daily pipeline stopped."
        )

        return False

    # --------------------------------------------------------
    # STEP 2
    # Update ML features
    # --------------------------------------------------------

    logger.info(
        "STEP 2/4: Preparing ML features..."
    )

    if not run_module(FEATURE_MODULE):

        logger.error(
            "Daily pipeline stopped."
        )

        return False

    # --------------------------------------------------------
    # STEP 3
    # Evaluate old predictions
    #
    # IMPORTANT:
    # This happens BEFORE creating today's prediction.
    # --------------------------------------------------------

    logger.info(
        "STEP 3/4: Evaluating previous predictions..."
    )

    if not run_module(EVALUATION_MODULE):

        logger.warning(
            "Prediction evaluation failed."
        )

        # Don't stop the entire pipeline.
        # We can still generate today's prediction.

    # --------------------------------------------------------
    # STEP 4
    # Generate new predictions
    # --------------------------------------------------------

    logger.info(
        "STEP 4/4: Generating new predictions..."
    )

    if not run_module(PREDICTION_MODULE):

        logger.error(
            "New prediction generation failed."
        )

        return False

    logger.info("")
    logger.info(
        "DAILY BTC PIPELINE COMPLETED SUCCESSFULLY"
    )
    logger.info("=" * 80)

    return True


# ============================================================
# WEEKLY PIPELINE
# ============================================================

def run_weekly_pipeline():

    logger.info("")
    logger.info("=" * 80)
    logger.info("WEEKLY MODEL COMPARISON STARTED")
    logger.info("=" * 80)

    if run_module(WEEKLY_MODULE):

        logger.info(
            "WEEKLY MODEL COMPARISON COMPLETED."
        )

        logger.info("=" * 80)

        return True

    logger.error(
        "WEEKLY MODEL COMPARISON FAILED."
    )

    logger.info("=" * 80)

    return False


# ============================================================
# SCHEDULE CHECK
# ============================================================

last_daily_run = None
last_weekly_run = None


def check_schedule():

    global last_daily_run
    global last_weekly_run

    now = get_now()

    today = now.date()

    # ========================================================
    # DAILY JOB
    # ========================================================

    if (
        now.hour == DAILY_HOUR
        and now.minute == DAILY_MINUTE
    ):

        if last_daily_run != today:

            logger.info(
                f"Daily schedule triggered at {now}"
            )

            run_daily_pipeline()

            last_daily_run = today

    # ========================================================
    # WEEKLY JOB
    # ========================================================

    if (
        now.weekday() == WEEKLY_DAY
        and now.hour == WEEKLY_HOUR
        and now.minute == WEEKLY_MINUTE
    ):

        if last_weekly_run != today:

            logger.info(
                f"Weekly schedule triggered at {now}"
            )

            run_weekly_pipeline()

            last_weekly_run = today


# ============================================================
# NEXT RUN DISPLAY
# ============================================================

def calculate_next_run():

    now = get_now()

    next_run = now.replace(
        hour=DAILY_HOUR,
        minute=DAILY_MINUTE,
        second=0,
        microsecond=0
    )

    if next_run <= now:

        next_run += timedelta(
            days=1
        )

    return next_run


# ============================================================
# STARTUP
# ============================================================

def startup():

    now = get_now()

    logger.info("")
    logger.info("=" * 80)
    logger.info("BTC AUTOMATION SYSTEM STARTED")
    logger.info("=" * 80)

    logger.info(
        f"Current Pakistan Time: {now}"
    )

    logger.info(
        f"Timezone: Asia/Karachi"
    )

    logger.info(
        "Daily Schedule: 05:10 AM"
    )

    logger.info(
        "Weekly Schedule: Sunday 05:10 AM"
    )

    logger.info(
        f"Next Daily Run: {calculate_next_run()}"
    )

    logger.info(
        f"Python: {PYTHON}"
    )

    logger.info(
        f"Project Directory: {BASE_DIR}"
    )

    logger.info(
        f"Log File: {LOG_FILE}"
    )

    logger.info("=" * 80)
    logger.info(
        "Scheduler is now running..."
    )
    logger.info("=" * 80)


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    startup()

    while True:

        try:

            check_schedule()

            # Check every 20 seconds.
            # This keeps the scheduler lightweight.

            time.sleep(20)

        except KeyboardInterrupt:

            logger.info(
                "Scheduler manually stopped."
            )

            break

        except Exception as e:

            logger.exception(
                f"Unexpected scheduler error: {e}"
            )

            # Scheduler continues running.

            time.sleep(30)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()