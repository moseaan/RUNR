# Dogehype Social Media Automator

This script provides a basic Graphical User Interface (GUI) to automate placing orders on dogehype.com using Playwright.

## Features

*   Simple UI for selecting Platform, Engagement Type, Link, and Quantity.
*   Automated login process for Dogehype (requires email verification via mail.com).
*   Persistent browser session to minimize logins.
*   Automated order placement for configured services.
*   Basic input validation (Link format, Quantity > 0, Minimum Quantity).
*   Status updates within the UI.

## Setup

1.  **Clone/Download:** Get the project files.
2.  **Python:** Ensure you have Python 3 installed.
3.  **Create Virtual Environment:**
    ```bash
    python -m venv .venv
    ```
4.  **Activate Virtual Environment:**
    *   Windows (Powershell): `.\.venv\Scripts\Activate.ps1`
    *   Windows (CMD): `.\.venv\Scripts\activate.bat`
    *   macOS/Linux: `source .venv/bin/activate`
5.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt 
    ```
6.  **Install Playwright Browsers:**
    ```bash
    playwright install
    ```
7.  **Configure Credentials:**
    *   Create a file named `.env` in the project root.
    *   Add the following lines, replacing placeholders with your actual credentials:
        ```dotenv
        TARGET_EMAIL="your_dogehype_and_mail.com_email@example.com"
        MAIL_PASSWORD="your_mail.com_password"
        ```
    *   **IMPORTANT:** Ensure this `.env` file is listed in your `.gitignore` file to avoid committing secrets.
8.  **Configure Target URL (Optional):**
    *   Verify/update the `TARGET_WEBSITE_URL` in `config.py` if needed.
9.  **Configure Services (IMPORTANT):**
    *   Edit `config.py`.
    *   Update the `CATEGORY_MAPPING` dictionary. The keys are `(Platform, EngagementType)` from the UI. The values MUST be the EXACT text labels shown in the Dogehype **Category** dropdown for that service.
    *   Update the `MINIMUM_QUANTITIES` dictionary with the correct minimum order size for each service.
    *   If a service requires selection from a second "Service" dropdown after selecting the category, you need to:
        *   Edit `automation.py`.
        *   Find the `place_order` function.
        *   Add an `elif platform == "..." and engagement_type == "...":` block to set the `service_label` variable to the EXACT text of the option in the **Service** dropdown.

## Running the Application

1.  Ensure your virtual environment is activated.
2.  Run the main application:
    ```bash
    python main_app.py
    ```
3.  Use the UI to select the platform, engagement type, enter the link and quantity.
4.  Click "Start Automation".
5.  Confirm the action in the popup dialog.
6.  The script will launch a browser, log in (or reuse the session), and attempt to place the order.
7.  Observe the status label in the UI and console output for progress.

## Running Tests

Basic unit tests for configuration mappings can be run:
```bash
python test_app_logic.py
```

## Notes

*   **UI Freezing:** The UI will become unresponsive while the browser automation is running. This is expected behavior in this version.
*   **Selectors:** The Playwright selectors used (especially for the order form) might break if Dogehype updates its website structure. You may need to update selectors in `automation.py` using `playwright codegen` if errors occur.
*   **Error Handling:** Basic error handling is included, but site-specific errors during order placement might not be caught if the site doesn't display clear error messages.
*   **Session Persistence:** The login session is stored in the `dogehype_session` folder. Delete this folder to force a full re-login. 