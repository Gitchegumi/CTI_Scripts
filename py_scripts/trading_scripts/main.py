"""The main entry point for the trading strategies application.
"""
import logging as log
import importlib

import api.utils as utils # pylint: disable=import-error

# Available strategies
STRATEGIES = {
    "1": "strategies.trailing_sl_atr",
    # Add other strategies here in the format "key": "module_path"
}


def main():
    """Main entry point for the trading strategies application.
    """
    utils.setup_logging()
    log.info("************ Starting Application ************")

    print("Select a strategy to run:")
    for key, module_name in STRATEGIES.items():
        print(f"{key}: {module_name}")

    choice = input("Enter the number of the strategy: ").strip()
    if choice not in STRATEGIES:
        log.error("Invalid choice. Exiting.")
        return

    selected_strategy = STRATEGIES[choice]
    try:
        strategy_module = importlib.import_module(selected_strategy)
        if hasattr(strategy_module, "run_strategy"):
            log.info("Running strategy: %s", selected_strategy)
            strategy_module.run_strategy()
        else:
            log.error("Selected module does not have a 'run_strategy' function.")
    except ImportError as e:
        log.error("Failed to import strategy module: %s", e)
    except AttributeError as e:
        log.error("Selected module does not have a 'run_strategy' function: %s", e)

if __name__ == "__main__":
    main()
