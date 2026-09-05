# ============================================================
# master_scheduler.py
#
# BTC AUTOMATION MASTER SCHEDULER
#
# DAILY PIPELINE:
#
#   1. YahooFinanceDataOnce.py
#   2. prepare_btc_ml_data.py
#   3. evaluate_prediction.py
#   4. daily_btc_prediction.py
#
# WEEKLY PIPELINE:
#
#   1. model_performance.py
#
# Timezone:
#   Asia/Karachi
#
# Daily:
#   05:10 AM
#
# Weekly:
#   Sunday 05:10 AM
#
# ============================================================

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

BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

PYTHON = sys.executable

TIMEZONE = ZoneInfo(
    "Asia/Karachi"
)


# ============================================================
# DAILY SCHEDULE
# ============================================================

DAILY_HOUR = 5
DAILY_MINUTE = 10


# ============================================================
# WEEKLY SCHEDULE
#
# Python weekday:
#
# Monday    = 0
# Tuesday   = 1
# Wednesday = 2
# Thursday  = 3
# Friday    = 4
# Saturday  = 5
# Sunday    = 6
# ============================================================

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

PERFORMANCE_MODULE = "weekly_model_comparison.py"


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

    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(message)s"
    ),

    handlers=[

        logging.FileHandler(
            LOG_FILE,
            encoding="utf-8"
        ),

        logging.StreamHandler()

    ]

)


logger = logging.getLogger(
    __name__
)


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


    # --------------------------------------------------------
    # Check file
    # --------------------------------------------------------

    if not os.path.isfile(
        module_path
    ):

        logger.error(
            f"Module not found: "
            f"{module_path}"
        )

        return False


    logger.info("")
    logger.info(
        "=" * 80
    )

    logger.info(
        f"STARTING MODULE: "
        f"{module_name}"
    )

    logger.info(
        "=" * 80
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


        elapsed = (
            time.time()
            -
            start_time
        )


        # ----------------------------------------------------
        # STDOUT
        # ----------------------------------------------------

        if result.stdout:

            logger.info(
                f"\n{result.stdout}"
            )


        # ----------------------------------------------------
        # STDERR
        # ----------------------------------------------------

        if result.stderr:

            logger.warning(
                f"\n{result.stderr}"
            )


        # ----------------------------------------------------
        # FAILED
        # ----------------------------------------------------

        if result.returncode != 0:

            logger.error(

                f"{module_name} FAILED | "
                f"Exit Code: "
                f"{result.returncode} | "
                f"Time: "
                f"{elapsed:.2f}s"

            )

            return False


        # ----------------------------------------------------
        # SUCCESS
        # ----------------------------------------------------

        logger.info(

            f"{module_name} COMPLETED | "
            f"Time: "
            f"{elapsed:.2f}s"

        )

        return True


    except Exception as e:

        logger.exception(

            f"Exception while running "
            f"{module_name}: {e}"

        )

        return False


# ============================================================
# CHECK REQUIRED MODULES
# ============================================================

def check_required_modules():

    modules = [

        DATA_MODULE,

        FEATURE_MODULE,

        EVALUATION_MODULE,

        PREDICTION_MODULE,

        PERFORMANCE_MODULE

    ]


    missing = []


    for module in modules:

        path = os.path.join(
            BASE_DIR,
            module
        )


        if not os.path.isfile(path):

            missing.append(
                module
            )


    if missing:

        logger.error(
            "Missing required modules:"
        )


        for module in missing:

            logger.error(
                f"  - {module}"
            )


        return False


    logger.info(
        "All required modules found."
    )

    return True


# ============================================================
# DAILY PIPELINE
# ============================================================

def run_daily_pipeline():

    logger.info("")
    logger.info(
        "#" * 80
    )

    logger.info(
        "DAILY BTC PIPELINE STARTED"
    )

    logger.info(
        "#" * 80
    )


    # ========================================================
    # STEP 1
    # ========================================================

    logger.info(
        "STEP 1/4: Updating BTC historical data..."
    )


    if not run_module(
        DATA_MODULE
    ):

        logger.error(
            "STEP 1 FAILED."
        )

        logger.error(
            "Daily pipeline stopped."
        )

        return False


    # ========================================================
    # STEP 2
    # ========================================================

    logger.info(
        "STEP 2/4: Preparing ML features..."
    )


    if not run_module(
        FEATURE_MODULE
    ):

        logger.error(
            "STEP 2 FAILED."
        )

        logger.error(
            "Daily pipeline stopped."
        )

        return False


    # ========================================================
    # STEP 3
    #
    # Evaluate yesterday/previous predictions.
    #
    # This must happen BEFORE generating today's
    # prediction.
    # ========================================================

    logger.info(
        "STEP 3/4: Evaluating previous predictions..."
    )


    if not run_module(
        EVALUATION_MODULE
    ):

        logger.warning(
            "Prediction evaluation failed."
        )

        logger.warning(
            "Continuing to prediction generation..."
        )


    # ========================================================
    # STEP 4
    # ========================================================

    logger.info(
        "STEP 4/4: Generating new predictions..."
    )


    if not run_module(
        PREDICTION_MODULE
    ):

        logger.error(
            "STEP 4 FAILED."
        )

        logger.error(
            "New prediction generation failed."
        )

        return False


    logger.info("")
    logger.info(
        "#" * 80
    )

    logger.info(
        "DAILY BTC PIPELINE COMPLETED SUCCESSFULLY"
    )

    logger.info(
        "#" * 80
    )


    return True


# ============================================================
# WEEKLY PIPELINE
# ============================================================

def run_weekly_pipeline():

    logger.info("")
    logger.info(
        "#" * 80
    )

    logger.info(
        "WEEKLY MODEL PERFORMANCE STARTED"
    )

    logger.info(
        "#" * 80
    )


    # --------------------------------------------------------
    # Run performance evaluation
    # --------------------------------------------------------

    if run_module(
        PERFORMANCE_MODULE
    ):

        logger.info(
            "WEEKLY MODEL PERFORMANCE "
            "COMPLETED SUCCESSFULLY."
        )

        logger.info(
            "#" * 80
        )

        return True


    logger.error(
        "WEEKLY MODEL PERFORMANCE FAILED."
    )

    logger.info(
        "#" * 80
    )

    return False


# ============================================================
# LAST RUN TRACKING
# ============================================================

last_daily_run = None

last_weekly_run = None


# ============================================================
# SCHEDULE CHECK
# ============================================================

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

        and

        now.minute == DAILY_MINUTE

    ):

        if last_daily_run != today:

            logger.info(
                f"Daily schedule triggered at "
                f"{now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            )


            success = run_daily_pipeline()


            if success:

                last_daily_run = today

                logger.info(
                    "Daily run marked as completed."
                )

            else:

                logger.error(
                    "Daily pipeline failed."
                )

                # ------------------------------------------------
                # IMPORTANT:
                #
                # We do NOT mark it as completed if it failed.
                #
                # However, because the scheduler checks every
                # 20 seconds, it could retry during the same
                # minute only if still 05:10.
                #
                # After 05:11 it will wait until next day.
                # ------------------------------------------------


    # ========================================================
    # WEEKLY JOB
    # ========================================================

    if (

        now.weekday() == WEEKLY_DAY

        and

        now.hour == WEEKLY_HOUR

        and

        now.minute == WEEKLY_MINUTE

    ):

        if last_weekly_run != today:

            logger.info(
                f"Weekly schedule triggered at "
                f"{now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
            )


            success = run_weekly_pipeline()


            if success:

                last_weekly_run = today

                logger.info(
                    "Weekly run marked as completed."
                )

            else:

                logger.error(
                    "Weekly pipeline failed."
                )


# ============================================================
# NEXT DAILY RUN
# ============================================================

def calculate_next_daily_run():

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
# NEXT WEEKLY RUN
# ============================================================

def calculate_next_weekly_run():

    now = get_now()


    days_ahead = (
        WEEKLY_DAY
        -
        now.weekday()
    ) % 7


    next_run = (

        now

        +

        timedelta(
            days=days_ahead
        )

    ).replace(

        hour=WEEKLY_HOUR,

        minute=WEEKLY_MINUTE,

        second=0,

        microsecond=0

    )


    if next_run <= now:

        next_run += timedelta(
            days=7
        )


    return next_run


# ============================================================
# STARTUP
# ============================================================

def startup():

    now = get_now()


    logger.info("")
    logger.info(
        "=" * 80
    )

    logger.info(
        "BTC AUTOMATION SYSTEM STARTED"
    )

    logger.info(
        "=" * 80
    )


    logger.info(
        f"Current Pakistan Time: "
        f"{now.strftime('%Y-%m-%d %H:%M:%S %Z')}"
    )


    logger.info(
        "Timezone: Asia/Karachi"
    )


    logger.info(
        "Daily Schedule: "
        "05:10 AM"
    )


    logger.info(
        "Weekly Schedule: "
        "Sunday 05:10 AM"
    )


    logger.info(
        f"Next Daily Run: "
        f"{calculate_next_daily_run()}"
    )


    logger.info(
        f"Next Weekly Run: "
        f"{calculate_next_weekly_run()}"
    )


    logger.info(
        f"Python: {PYTHON}"
    )


    logger.info(
        f"Project Directory: "
        f"{BASE_DIR}"
    )


    logger.info(
        f"Log File: "
        f"{LOG_FILE}"
    )


    logger.info(
        "=" * 80
    )


    # --------------------------------------------------------
    # Check files
    # --------------------------------------------------------

    if not check_required_modules():

        logger.error(
            "Some required modules are missing."
        )

        logger.error(
            "Please fix the filenames before "
            "starting the scheduler."
        )


    logger.info(
        "Scheduler is now running..."
    )


    logger.info(
        "=" * 80
    )


# ============================================================
# MAIN LOOP
# ============================================================

def main():

    startup()


    while True:

        try:

            check_schedule()


            # ------------------------------------------------
            # Check every 20 seconds.
            # ------------------------------------------------

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


            # ------------------------------------------------
            # Keep scheduler alive
            # ------------------------------------------------

            time.sleep(30)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()
