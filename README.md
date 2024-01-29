## AutoScaler Application

### Overview

AutoScaler is an application designed to automatically scale a separate application based on CPU utilization metrics. It monitors the application's emulated CPU usage and dynamically adjusts the number of replicas to keep the average CPU usage around a specified target.

### Prerequisites


1. Python 3.8 or higher
2. pip (Python package manager)
3. Virtual environment (optional but recommended)
4. Docker (for Docker deployment)
5. Visual Studio Code with Remote - Containers extension (for VS Code remote development)
6. Bandit (for security analysis)
7. SAST and DAST tools of your choice (ex: Snyk, OWASP ZAP)
8. Access to a macOS machine (for installation on macOS)

### Installation and Setup


#### Clone the repository

```bash
git clone https://github.com/prnam/autoscaler.git && cd autoscaler
```

#### Setting up a Python Virtual Environment on macOS
1. **Install Python 3:** Ensure Python 3.8 or higher is installed on your macOS. You can check the Python version by running `python --version` in the terminal.
2. Create a Virtual Environment:
    ```sh
    python -m venv venv
    ```
3. Activate the Virtual Environment:
    ```sh
    source venv/bin/activate
    ```
4. Install Dependencies:
    ```sh
    pip install -r requirements.txt
    ```
#### Setting up Visual Studio Code for Remote Development
1. Install Visual Studio Code: Download and install VS Code from Visual Studio Code website.
2. Install Remote - Containers Extension: Open VS Code, go to Extensions, and search for "Remote - Containers". Install the extension.
3. Open Project in Container: Open the project folder in VS Code, then use the command palette (Cmd+Shift+P) and select "Remote-Containers: Open Folder in Container".

### Running Security Analysis
1. Bandit for Python Security Analysis (SAST):
    ```sh
    bandit autoscaler.py
    ```
2. DAST (Dynamic Application Security Testing): Deploy the application in a staging environment and run the DAST tool against it.
3. Run SCA tools to check for vulnerabilities in dependencies. Tools like `snyk` or `whitesource` can be used.
    - Check for vulnerable dependencies using `snyk`:
        ```bash
        snyk test
        ```

### Testing

1. Run tests using pytest:

    ```sh
    pytest -v .
    ```

### Production Deployment

#### Building a Binary
1. Use tools like PyInstaller to build a standalone binary:
    ```sh
    pyinstaller --onefile autoscaler.py
    ```
#### Building a Docker Image
1. Create a Dockerfile: Write a Dockerfile for the application.
2. Build the Docker Image:
    ```sh
    docker build --target release-stage -t autoscaler:1.0 .
    ```
3. Push the image to a registry:
    ```sh
    docker push your-registry/autoscaler:1.0
    ```
4. Scan the Docker image for vulnerabilities using `snyk`:
    ```sh
    snyk container test autoscaler:1.0
    ```
5. Run the Docker Container:
    ```sh
    docker run -d --name autoscaler_container autoscaler
    ```
    ```sh
    docker run -d --name autoscaler_container -e HOST=host.docker.internal -e USE_HTTPS=false autoscaler:1.0
    ```
### Running the Application on Workstation (tested on MacOS ARM)

To run the AutoScaler, use the following command with the necessary arguments:

```sh
python autoscaler.py --host <host> --port <port> [--https] [--target-cpu-usage <value>] [--polling-interval <interval>] [--retry-count <count>] [--retry-delay <delay>]
```

> Note: Replace <host>, <port>, and other placeholders with appropriate values. Add --https if HTTPS is needed.

Examples:
1. Running Without Parameters: If you run the AutoScaler without any parameters, it will use the default values defined in the code. To do this, simply execute:

    ```sh
    python autoscaler.py
    ```
2. Running With Different Parameters: You can customize the behavior of the AutoScaler by providing different command-line arguments.

    a. Specify Host and Port:
    ```sh
    python autoscaler.py --host 192.168.1.100 --port 8080
    ```

    b. Enable HTTPS:
    ```sh
    python autoscaler.py --https
    ```

    c. Set Target CPU Usage:
    ```sh
    python autoscaler.py --target-cpu-usage 0.75
    ```

    d. Change Polling Interval:
    ```sh
    python autoscaler.py --polling-interval 10
    ```
    > Note: Polling interval is recommended to be set based on the time it takes for replica to scale, balance traffic in the application, and release the resource usage (here it is CPU) to reflect its true consumption.

    e. Adjust Retry Count and Delay:
    ```sh
    python autoscaler.py --retry-count 3 --retry-delay 2
    ```

You can check the different usage of parameters by running `python autoscaler.py -h` in the terminal.

### Contributing
This documentation covers only MacOS-specific instructions and may have missing instructions based on your environment. Hence, we request that you follow the standard fork, branch, and pull request workflow and contribute to this repo.


### License

This private license is for interview evaluation purposes only. No part of the code should be used beyond the purpose it is shared with.


