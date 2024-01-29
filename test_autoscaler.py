import os
import sys
import signal
import pytest
from autoscaler import AutoScaler, handle_sigterm
from unittest.mock import Mock, patch
from functools import partial
from autoscaler import parse_arguments


class MockConfig:
    """
    Mock configuration class for testing AutoScaler.

    Attributes:
        host (str): Hostname or IP address of the application.
        port (int): Port number on which the application is running.
        use_https (bool): Indicates whether HTTPS should be used.
        target_cpu_usage (float): Target CPU usage.
        polling_interval (int): Interval in seconds between status checks.
        retry_count (int): Number of retry attempts for failed requests.
        retry_delay (int): Delay in seconds between retries.
    """

    def __init__(
        self,
        host,
        port,
        use_https,
        target_cpu_usage,
        polling_interval,
        retry_count,
        retry_delay,
    ):
        self.host = host
        self.port = port
        self.use_https = use_https
        self.target_cpu_usage = target_cpu_usage
        self.polling_interval = polling_interval
        self.retry_count = retry_count
        self.retry_delay = retry_delay


@pytest.fixture
def mock_config():
    """
    Provides a pytest fixture for a mock AutoScaler configuration.

    This fixture creates a MockConfig instance with predefined values that can be used across different test functions.

    Returns:
        MockConfig: A configured mock object for the AutoScaler.
    """
    return MockConfig("localhost", 8123, False, 0.80, 15, 3, 2)


@pytest.mark.parametrize("cpu_usage", [i / 100 for i in range(0, 101)])
def test_auto_scaler_adjustment(mocker, mock_config, cpu_usage):
    """
    Test the AutoScaler's ability to adjust the number of replicas based on CPU usage.
    The test simulates different CPU usage scenarios and checks if the AutoScaler appropriately adjusts the number of replicas.

    Args:
        mocker: Pytest fixture for mocking.
        mock_config: Mock configuration object for the AutoScaler.
        cpu_usage (float): Simulated CPU usage value for the test.
    """
    # Setup initial conditions
    current_replicas = 1
    expected_replicas = current_replicas

    # Create an AutoScaler instance with mock configuration
    auto_scaler = AutoScaler(
        mock_config.host,
        mock_config.port,
        mock_config.use_https,
        mock_config.target_cpu_usage,
        mock_config.polling_interval,
        mock_config.retry_count,
        mock_config.retry_delay,
    )
    constructed_url = auto_scaler.construct_url("/app/replicas")

    # Mock the responses for the HTTP requests
    mocker.patch(
        "requests.get",
        return_value=Mock(
            status_code=200,
            json=lambda: {
                "cpu": {"highPriority": cpu_usage},
                "replicas": current_replicas,
            },
        ),
    )
    mock_put = mocker.patch("requests.put", return_value=Mock(status_code=204))

    # Run the auto-scaling process once
    auto_scaler.run_once = True
    auto_scaler.run()

    # Determine the expected number of replicas based on the simulated CPU usage
    if cpu_usage == 0.80:
        expected_replicas = current_replicas
    elif cpu_usage < 0.80:
        expected_replicas = max(1, current_replicas - 1)
    else:
        expected_replicas = current_replicas + 1

    if expected_replicas != current_replicas:
        mock_put.assert_called_with(
            constructed_url,
            json={"replicas": expected_replicas},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
    else:
        mock_put.assert_not_called()


def test_get_current_status_server_error(mocker, mock_config):
    """
    Test the AutoScaler's handling of an error response when getting the current status.
    This test ensures that the AutoScaler correctly handles server errors by returning None.

    Args:
        mocker: Pytest fixture for mocking.
        mock_config: Mock configuration object for the AutoScaler.
    """
    auto_scaler = AutoScaler(
        mock_config.host,
        mock_config.port,
        mock_config.use_https,
        mock_config.target_cpu_usage,
        mock_config.polling_interval,
        mock_config.retry_count,
        mock_config.retry_delay,
    )
    mocker.patch(
        "requests.get",
        return_value=Mock(status_code=500, text="error retrieving status"),
    )

    response = auto_scaler.get_current_status()
    assert response is None


def test_set_replica_count_server_error(mocker, mock_config, caplog):
    """
    Test the AutoScaler's handling of an error response when setting the replica count.
    This test checks if the appropriate error message is logged when an error occurs.

    Args:
        mocker: Pytest fixture for mocking.
        mock_config: Mock configuration object for the AutoScaler.
        caplog: Pytest fixture for capturing log output.
    """
    auto_scaler = AutoScaler(
        mock_config.host,
        mock_config.port,
        mock_config.use_https,
        mock_config.target_cpu_usage,
        mock_config.polling_interval,
        mock_config.retry_count,
        mock_config.retry_delay,
    )
    mocker.patch(
        "requests.put",
        return_value=Mock(status_code=500, text="error updating replicas"),
    )

    auto_scaler.set_replica_count(10)
    assert "error updating replicas" in caplog.text


def test_handle_sigterm(mock_config):
    """
    Test the handling of the SIGTERM signal by the AutoScaler.
    The test verifies that the AutoScaler correctly sets the stop_requested flag when a SIGTERM signal is received.

    Args:
        mock_config: Mock configuration object for the AutoScaler.
    """
    global auto_scaler  # Declare as global to modify the variable within this test

    auto_scaler = AutoScaler(
        mock_config.host,
        mock_config.port,
        mock_config.use_https,
        mock_config.target_cpu_usage,
        mock_config.polling_interval,
        mock_config.retry_count,
        mock_config.retry_delay,
    )

    # Register the signal handler
    signal.signal(
        signal.SIGTERM,
        partial(
            handle_sigterm,
            auto_scaler=auto_scaler))

    # Send SIGTERM to the current process
    os.kill(os.getpid(), signal.SIGTERM)

    # Check if the stop_requested flag is set to True
    assert auto_scaler.stop_requested


def test_valid_arguments():
    """
    Test the parse_arguments function with valid arguments.
    """
    valid_args = [
        "autoscaler.py",
        "--target-cpu-usage",
        "0.75",
        "--polling-interval",
        "10",
        "--retry-count",
        "5",
        "--retry-delay",
        "3",
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
    ]
    with patch.object(sys, "argv", valid_args):
        args = parse_arguments()
        assert args.target_cpu_usage == 0.75
        assert args.polling_interval == 10
        assert args.retry_count == 5
        assert args.retry_delay == 3
        assert args.host == "127.0.0.1"
        assert args.port == 8080


def test_invalid_ip_argument():
    """
    Test the parse_arguments function with an invalid IP address argument.
    """
    invalid_ip_args = ["autoscaler.py", "--host", "invalid_ip"]
    with patch.object(sys, "argv", invalid_ip_args), pytest.raises(SystemExit):
        parse_arguments()


def test_invalid_port_argument():
    """
    Test the parse_arguments function with an invalid port argument.
    """
    invalid_port_args = [
        "autoscaler.py",
        "--port",
        "70000"]  # Invalid port number
    with patch.object(sys, "argv", invalid_port_args), pytest.raises(SystemExit):
        parse_arguments()


def test_https_argument_enabled():
    """
    Test the parse_arguments function with the --https argument enabled.
    Verifies that the use_https attribute is set to True when the --https flag is provided.
    """
    https_args = [
        "autoscaler.py",
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
        "--https"]
    with patch.object(sys, "argv", https_args):
        args = parse_arguments()
        assert args.https is True


def test_https_argument_disabled():
    """
    Test the parse_arguments function without the --https argument.
    Verifies that the use_https attribute is set to False when the --https flag is not provided.
    """
    no_https_args = ["autoscaler.py", "--host", "127.0.0.1", "--port", "8080"]
    with patch.object(sys, "argv", no_https_args):
        args = parse_arguments()
        assert args.https is False
