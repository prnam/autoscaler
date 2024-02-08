import time
import logging
import argparse
import signal
import sys
import ipaddress
from datetime import datetime
from functools import partial
from urllib.parse import urlunparse
import requests


class AutoScaler:
    """
    A class used to automatically scale an application based on CPU utilization.
    """

    def __init__(self, host, port, use_https, target_cpu_usage, polling_interval, retry_count, retry_delay):
        """
        Initializes the AutoScaler with the given configuration.

        Parameters:
            host (str): The host of the application to be monitored.
            port (int): The port on which the application is running.
            use_https (bool): Flag to determine if HTTPS should be used.
            target_cpu_usage (float): The target CPU usage to maintain.
            polling_interval (int): The interval, in seconds, between checks.
            retry_count (int): The number of retries for failed requests.
            retry_delay (int): The delay, in seconds, between retries.
        """
        self.host = host
        self.port = port
        self.use_https = use_https
        self.target_cpu_usage = target_cpu_usage
        self.polling_interval = polling_interval
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self.session = requests.Session()
        # If set to True, the run loop will execute only once (useful for testing)
        self.run_once = False
        self.stop_requested = False

    def construct_url(self, path):
        """
        Constructs the complete URL based on the host, port, and HTTPS setting.
        """
        scheme = "https" if self.use_https else "http"
        hostport = f"{self.host}:{self.port}"
        return urlunparse((scheme, hostport, path, "", "", ""))

    def get_current_status(self):
        """
        Retrieves the current status of the application including CPU usage and replica count.

        The method makes an HTTP GET request to the application's status endpoint. If the request fails, it retries a specified number of times with an exponential backoff delay between
        attempts. The response is expected to contain the current CPU usage and the number of replicas in a JSON format.

        Returns:
            dict: A dictionary containing the current CPU usage and replica count, or
            None: If the request fails or an error occurs after all retry attempts.
        """
        attempts = 0
        while attempts < self.retry_count:
            try:
                # Make the HTTP GET request to the application's status endpoint
                response = requests.get(self.construct_url("/app/status"), headers={"Accept": "application/json"}, timeout=5)

                # Check if the response is successful (HTTP 200 OK)
                if response.status_code == 200:
                    # Return the JSON response containing the status
                    return response.json()
                else:
                    # Log an error if the response status code indicates a failure
                    logging.error(f"HTTP Verb: {response.request.method}, HTTP Status: {response.status_code}, HTTP Message: {response.text.strip()}")

            except requests.exceptions.RequestException as e:
                # Log an error if a request exception occurs (e.g., network
                # issues)
                logging.error("Request error: %s", e)

            # Increment the number of attempts and apply an exponential backoff for retries
            attempts += 1
            logging.error(f"HTTP Verb: GET, Retry (in seconds): {self.retry_delay**attempts}, Attempt #: {attempts}")
            time.sleep(self.retry_delay**attempts)

        # Return None if all retry attempts fail
        return None

    def set_replica_count(self, new_count):
        """
        Sets the number of replicas for the application based on the current CPU usage.

        Parameters:
            new_count (int): The new number of replicas to set.

        This method attempts to update the number of replicas for the application by making HTTP PUT requests to the application's replicas endpoint.
        It uses an exponential backoff retry mechanism to handle failures.

        Args:
            new_count (int): The desired number of replicas to be set.

        Returns:
            None: If the request fails or an error occurs.
        """
        success = False
        attempts = 0
        while not success and attempts < self.retry_count:
            try:
                # Prepare data for the PUT request
                data = {"replicas": new_count}

                # Make the HTTP PUT request
                response = requests.put(self.construct_url("/app/replicas"), json=data, headers={"Content-Type": "application/json"}, timeout=5)

                # Check the response status code
                if response.status_code == 204:
                    success = True
                    return
                else:
                    logging.error(f"HTTP Verb: {response.request.method}, HTTP Status: {response.status_code}, HTTP Message: {response.text.strip()}")

            except requests.exceptions.RequestException as e:
                # Handle request exceptions (e.g., network issues)
                logging.error("Request error: %s", e)

            # Increment retry attempts and log details
            attempts += 1
            logging.error(f"HTTP Verb: PUT, Retry (in seconds): {self.retry_delay**attempts}, Attempt #: {attempts}")

            # Apply exponential backoff delay before the next retry
            time.sleep(self.retry_delay**attempts)

    def run(self):
        """
        Starts the auto-scaling process. Continuously monitors the application and adjusts the number of replicas based on the CPU usage.

        This method runs in a loop, checking the application's status at each polling interval and adjusting the number of replicas to maintain the target CPU usage.
        The method retrieves the current CPU usage and the number of replicas from the application, calculates whether an adjustment is needed, and sets the new number of replicas if necessary.
        The loop continues until the `stop_requested` flag is set to True. If `run_once` is set to True, the loop runs only once, which is useful for testing purposes.
        """
        while not self.stop_requested:
            status = self.get_current_status()  # Get current status of the application
            if status:
                # Current CPU usage
                current_cpu = status["cpu"]["highPriority"]
                # Current number of replicas
                current_replicas = status["replicas"]
                new_replicas = current_replicas  # Initialize new_replicas

                # Calculate the necessary adjustment based on CPU usage
                if current_cpu < self.target_cpu_usage:
                    new_replicas = max(1, current_replicas - 1)  # Decrease replicas if CPU usage is below target
                if current_cpu > self.target_cpu_usage:
                    new_replicas = current_replicas + 1  # Increase replicas if CPU usage is above target

                # Log the current status and any adjustments made
                logging.info(f"Current CPU: {current_cpu}, Current Replicas: {current_replicas}, New Replicas: {new_replicas}")

                # Update the number of replicas if there is a change
                if new_replicas != current_replicas:
                    self.set_replica_count(new_replicas)

            # Break the loop if run_once is set (useful for testing)
            if self.run_once:
                break

            # Wait for the specified polling interval before the next check
            time.sleep(self.polling_interval)

    def request_stop(self):
        """
        Requests the auto-scaling process to stop.

        This method sets a flag that will cause the main loop in the 'run' method to exit at the end of its current iteration.
        """
        self.stop_requested = True


class ValidatePortAction(argparse.Action):
    """
    A custom action for argparse to validate the port number.

    This class extends argparse.Action and is used to check if the provided port number is within a valid range. If the port number is not valid, it raises an argparse.ArgumentError. This approach allows for custom validation logic without displaying the range of valid choices in the help message.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        """
        The method called by argparse when this action is triggered.

        Args:
            parser (ArgumentParser): The ArgumentParser object.
            namespace (Namespace): The Namespace object containing parsed arguments.
            values (int): The command-line argument value for this action.
            option_string (str, optional): The option string that triggered this action.

        Raises:
            argparse.ArgumentError: If the provided port number is not within the valid range.
        """
        min_port = 1
        max_port = 65535
        if not min_port <= values <= max_port:
            # If the port number is outside the valid range, raise an error
            raise argparse.ArgumentError(self, f"Invalid port number. Must be between {min_port} and {max_port}")

        # If validation is successful, set the value in the namespace
        setattr(namespace, self.dest, values)

def parse_arguments():
    """
    Parses command-line arguments for the AutoScaler application.

    This function defines the command-line arguments that the AutoScaler accepts, processes the arguments provided by the user, and returns them in a structured
    format for use in the application.

    The function also validates the application URL argument to ensure it's a well-formed URL with a valid IP address and port.

    Returns:
        argparse.Namespace: An object containing the parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="Auto-scaler for adjusting the number of replicas based on CPU utilization.")
    parser.add_argument("-tcu", "--target-cpu-usage", type=float, default=0.80, help="Target CPU usage to maintain (default: 0.80)")
    parser.add_argument("-pi", "--polling-interval", type=int, default=15, help="Seconds between polling (default: 15)")
    parser.add_argument("-rc", "--retry-count", type=int, default=6, help="Number of retries on failure (default: 6)")
    parser.add_argument("-rd", "--retry-delay", type=int, default=2, help="Seconds between retries (default: 2)")
    parser.add_argument("-ip", "--host", type=str, default="localhost", help="Host of the application (default: localhost)")
    parser.add_argument("-p", "--port", type=int, default=8123, action=ValidatePortAction, help="Port of the application (default: 8123)")
    parser.add_argument("--https", action="store_true", help="Enable HTTPS for the application")

    args = parser.parse_args()

    if not is_valid_ip_address(args.host):
        logging.error(f"Invalid IP address provided.")
        sys.exit(1)

    return args


def is_valid_ip_address(ip):
    """
    Validates if the provided string is a valid IPv4 or IPv6 address or 'localhost'.

    Args:
        ip (str): The IP address or 'localhost' to validate.

    Returns:
        bool: True if the IP address or 'localhost' or 'host.docker.internal' is valid, False otherwise.
    """
    if ip == "localhost" or ip == "host.docker.internal":
        return True
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def handle_sigterm(signum, frame, auto_scaler):
    """
    Signal handler for the SIGTERM signal.

    This function is called when the application receives a SIGTERM signal, typically sent by the operating system or a process manager to request the application to
    terminate gracefully. The function sets a flag in the AutoScaler instance to indicate that it should stop running.

    Args:
        signum (int): The signal number (should be signal.SIGTERM).
        frame (frame object): The current stack frame object at the point where the signal was received.
        auto_scaler (AutoScaler): An instance of AutoScaler to be stopped.
    """
    print("SIGTERM received, stopping AutoScaler...")
    auto_scaler.request_stop()


def main():
    """
    Main function to initialize and run the AutoScaler application.

    This function sets up logging with a specified format and logging level. It parses command-line arguments to configure the AutoScaler instance.
    After parsing the arguments, it creates an AutoScaler instance and sets up a signal handler for graceful shutdown upon receiving a SIGTERM signal.
    The function starts the auto-scaling process and keeps it running until it's interrupted by a keyboard interrupt (Ctrl+C) or a SIGTERM signal.

    Upon receiving a keyboard interrupt, the function requests the AutoScaler to stop its operation gracefully.
    """

    global auto_scaler
    auto_scaler = None

    try:
        start_time = datetime.now()
        # Configure logging with a specific format and level
        logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
        logging.info("AutoScaler started")
        # Initialize auto_scaler to None
        args = parse_arguments()

        
        # Parse command-line arguments for the AutoScaler configuration
        auto_scaler = AutoScaler(args.host, args.port, args.https, args.target_cpu_usage, args.polling_interval, args.retry_count, args.retry_delay)

        # Set up a signal handler for gracefully handling SIGTERM signals
        signal.signal(signal.SIGTERM, partial(handle_sigterm, auto_scaler=auto_scaler))

        # Start the auto-scaling process
        auto_scaler.run()

    except KeyboardInterrupt:
        # Handle keyboard interrupt (Ctrl+C) and request a graceful shutdown of the AutoScaler
        logging.info(f"Stopping AutoScaler...")
        auto_scaler.request_stop()
    # except Exception as e:
    #     # Handle keyboard interrupt (Ctrl+C) and request a graceful shutdown of the AutoScaler
    #     logging.info(f"Expection raised. Reason: {e}")
    #     auto_scaler.request_stop()
    except SystemExit as e:
        # Log an error message for invalid arguments
        logging.error(f"Invalid arguments provided. Exiting with code {e.code}.")

    finally:
        if auto_scaler is not None:
            auto_scaler.request_stop()
        logging.info(f"AutoScaler Stopped")
        
        shutdown_time = datetime.now()
        logging.info(f"Started at: {start_time.isoformat()}, Shutdown at: {shutdown_time.isoformat()}, Uptime: {shutdown_time - start_time}")
        


if __name__ == "__main__":
    main()
