"""
RUNR System Tray Application
Runs the Flask server in the background with a system tray icon.
"""
import os
import sys
import threading
import webbrowser
import subprocess

# Add app_files to path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

try:
    import pystray
    from PIL import Image
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    print("pystray or Pillow not installed. Run: pip install pystray Pillow")

# Configuration
DEFAULT_PORT = 4000
APP_NAME = "RUNR"
ICON_PATH = os.path.join(APP_DIR, "static", "favicon.png")


def get_icon_image():
    """Load the tray icon image."""
    try:
        if os.path.exists(ICON_PATH):
            return Image.open(ICON_PATH)
    except Exception as e:
        print(f"Could not load icon: {e}")
    
    # Create a simple default icon if no icon file exists
    img = Image.new('RGB', (64, 64), color=(0, 120, 212))
    return img


class TrayApp:
    def __init__(self, port=DEFAULT_PORT):
        self.port = port
        self.server_thread = None
        self.server_running = False
        self.icon = None
        self.app_url = f"http://127.0.0.1:{port}"
        
    def start_server(self):
        """Start the Flask server in a background thread."""
        if self.server_running:
            return
            
        def run_server():
            try:
                # Import and run the Flask app
                from waitress import serve
                import app as flask_app
                
                self.server_running = True
                print(f"🚀 RUNR server starting on {self.app_url}")
                serve(flask_app.app, host='0.0.0.0', port=self.port, threads=4)
            except Exception as e:
                print(f"Server error: {e}")
                self.server_running = False
        
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
    def open_browser(self, icon=None, item=None):
        """Open the app in the default browser."""
        webbrowser.open(self.app_url)
        
    def quit_app(self, icon=None, item=None):
        """Quit the application."""
        print("Shutting down RUNR...")
        if self.icon:
            self.icon.stop()
        os._exit(0)
        
    def create_menu(self):
        """Create the system tray menu."""
        return pystray.Menu(
            pystray.MenuItem(f"RUNR - Port {self.port}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open in Browser", self.open_browser, default=True),
            pystray.MenuItem("Copy URL", self.copy_url),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Exit", self.quit_app)
        )
    
    def copy_url(self, icon=None, item=None):
        """Copy the app URL to clipboard."""
        try:
            import subprocess
            subprocess.run(['clip'], input=self.app_url.encode(), check=True)
            print(f"URL copied: {self.app_url}")
        except Exception as e:
            print(f"Could not copy URL: {e}")
    
    def run(self):
        """Run the tray application."""
        if not TRAY_AVAILABLE:
            print("System tray not available. Running server directly...")
            self.start_server()
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                print("Shutting down...")
            return
            
        # Start the server first
        self.start_server()
        
        # Give server a moment to start
        import time
        time.sleep(1)
        
        # Create and run the tray icon
        self.icon = pystray.Icon(
            APP_NAME,
            get_icon_image(),
            f"{APP_NAME} - Running",
            self.create_menu()
        )
        
        print(f"✅ RUNR is running in the system tray")
        print(f"   URL: {self.app_url}")
        print(f"   Right-click the tray icon for options")
        
        # Run the icon (this blocks)
        self.icon.run()


def main():
    """Main entry point."""
    # Get port from environment or use default
    port = int(os.environ.get('PORT', os.environ.get('RUNR_PORT', DEFAULT_PORT)))
    
    # Change to app directory
    os.chdir(APP_DIR)
    
    # Load environment variables
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(APP_DIR), '.env')
        if os.path.exists(env_path):
            load_dotenv(env_path)
    except ImportError:
        pass
    
    app = TrayApp(port=port)
    app.run()


if __name__ == "__main__":
    main()
