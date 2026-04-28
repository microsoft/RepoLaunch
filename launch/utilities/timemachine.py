"""
PyPI time machine server for historical package resolution.

Provides a local PyPI server that only serves packages released before
a specified cutoff date, enabling reproducible environment setup.
"""

import socket
import threading
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup
from tornado.ioloop import IOLoop
from tornado.routing import PathMatches
from tornado.web import Application, RequestHandler

from launch.core.runtime import SetupRuntime

MAIN_PYPI = "https://pypi.org/simple/"
JSON_URL = "https://pypi.org/pypi/{package}/json"

PACKAGE_HTML = """
<!DOCTYPE html>
<html>
  <head>
    <title>Links for {package}</title>
  </head>
  <body>
    <h1>Links for {package}</h1>
{links}
  </body>
</html>
"""


def parse_iso(dt):
    """
    Parse ISO date string to datetime object.
    
    Args:
        dt (str): ISO date string in various formats
        
    Returns:
        datetime: Parsed datetime object
    """
    try:
        return datetime.strptime(dt, "%Y-%m-%d")
    except Exception:
        try:
            return datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return datetime.strptime(dt, "%Y-%m-%dT%H:%M:%SZ")


def make_app(cutoff_date):
    """
    Create Tornado app that serves PyPI packages before cutoff date.
    
    Args:
        cutoff_date (str): ISO date string for package cutoff
        
    Returns:
        Application: Configured Tornado application
    """
    CUTOFF = parse_iso(cutoff_date)
    INDEX = requests.get(MAIN_PYPI).content

    class MainIndexHandler(RequestHandler):
        async def get(self):
            return self.write(INDEX)

    class PackageIndexHandler(RequestHandler):
        async def get(self, package):
            try:
                response = requests.get(JSON_URL.format(package=package))
                if response.status_code == 404:
                    # Package doesn't exist - return 404 to pip
                    self.set_status(404)
                    self.write(f"Package '{package}' not found")
                    return
                
                response.raise_for_status()
                package_index = response.json()
            except (requests.RequestException, ValueError) as e:
                # Network error or invalid JSON response
                self.set_status(500)
                self.write(f"Error fetching package '{package}': {str(e)}")
                return
            
            # Check if releases key exists
            if "releases" not in package_index:
                # Package exists but has no releases (empty package)
                self.write(PACKAGE_HTML.format(package=package, links=""))
                return
                
            release_links = ""
            for release in package_index["releases"].values():
                for file in release:
                    try:
                        release_date = parse_iso(file["upload_time"])
                        if release_date < CUTOFF:
                            if file["requires_python"] is None:
                                release_links += '    <a href="{url}#sha256={sha256}">{filename}</a><br/>\n'.format(
                                    url=file["url"],
                                    sha256=file["digests"]["sha256"],
                                    filename=file["filename"],
                                )
                            else:
                                rp = file["requires_python"].replace(">", "&gt;")
                                release_links += '    <a href="{url}#sha256={sha256}" data-requires-python="{rp}">{filename}</a><br/>\n'.format(
                                    url=file["url"],
                                    sha256=file["digests"]["sha256"],
                                    rp=rp,
                                    filename=file["filename"],
                                )
                    except (KeyError, ValueError):
                        # Skip malformed file entries
                        continue

            self.write(PACKAGE_HTML.format(package=package, links=release_links))

    return Application(
        [
            (r"/", MainIndexHandler),
            (PathMatches(r"/(?P<package>\S+)\//?"), PackageIndexHandler),
        ]
    )


class PyPiServer:
    """
    PyPI time machine server wrapper for lifecycle management.
    
    Attributes:
        port (int): Server port number
    """
    def __init__(self, server, ioloop, thread, port):
        self._server = server
        self._ioloop = ioloop
        self._thread = thread
        self.port = port  # User-facing

    def stop(self, quiet=True):
        """
        Stop the Tornado server and IOLoop thread.
        
        Args:
            quiet (bool): Whether to suppress stop messages
        """
        def shutdown():
            self._server.stop()
            if not quiet:
                print("Server is stopping...")

        self._ioloop.add_callback(shutdown)
        self._ioloop.add_callback(self._ioloop.stop)
        self._thread.join()
        if not quiet:
            print("Server stopped and IOLoop thread joined.")


def start_pypi_timemachine(cutoff_date, port=None, quiet=True):
    """
    Start a PyPI time machine server on specified port.
    
    Args:
        cutoff_date (str): ISO date string for package cutoff
        port (int, optional): Port number, uses ephemeral if None
        quiet (bool): Whether to suppress startup messages
        
    Returns:
        PyPiServer: Running server instance
    """
    app = make_app(cutoff_date)

    # Pick ephemeral port if not specified
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("localhost", 0))
    chosen_port = port if port else sock.getsockname()[1]
    sock.close()

    server = app.listen(port=chosen_port)

    ioloop = IOLoop.current()
    thread = threading.Thread(target=ioloop.start, daemon=True)
    thread.start()

    if not quiet:
        print(
            f"Started pypi-timemachine server at http://localhost:{chosen_port} (cutoff={cutoff_date})"
        )

    return PyPiServer(server, ioloop, thread, chosen_port)


def start_timemachine(session: SetupRuntime, date: str) -> PyPiServer:
    """
    Start time machine server and configure pip in container session.
    
    Args:
        session (SetupRuntime): Container session to configure
        date (str): ISO date string for package cutoff
        
    Returns:
        PyPiServer: Running time machine server
    """
    server = start_pypi_timemachine(cutoff_date=date)
    session.send_command("pip install --upgrade pip")
    session.send_command(
        f"pip config set global.index-url http://host.docker.internal:{server.port}"
    )
    session.send_command("pip config set global.trusted-host host.docker.internal")
    return server



def find_latest_version(package_name, query_date):
    date_version_mapping = collect_pypi_history(package_name)
    query_date = datetime.fromisoformat(query_date).replace(tzinfo=timezone.utc)
    # find the latest version before the query date
    if not date_version_mapping:
        return None
    latest_version = None
    for date, version in date_version_mapping:
        if date < query_date:
            latest_version = version
            break
    return latest_version


def collect_pypi_history(package_name):
    url = f"https://pypi.org/project/{package_name}/#history"
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch data for package: {package_name}")
        return
    soup = BeautifulSoup(response.text, "html.parser")
    releases = soup.find_all("div", class_="release")
    date_version_mapping = []
    for release in releases:
        version = release.find("p", class_="release__version").text.strip()
        date = release.find("time")[
            "datetime"
        ].strip()  # Extract the 'datetime' attribute
        date = datetime.fromisoformat(date)  # Convert to datetime object
        if date.tzinfo is None:  # Ensure the date is offset-aware
            date = date.replace(tzinfo=timezone.utc)
        date_version_mapping.append((date, version))

    return date_version_mapping


if __name__ == "__main__":

    # test collect pypi_history
    package_name = "numpy"
    history = collect_pypi_history(package_name)
    if history:
        for date, version in history:
            print(f"Date: {date}, Version: {version}")

    latest_version = find_latest_version("numpy", "2023-10-01")
    print(f"Latest version before 2023-10-01: {latest_version}")


    # test time machine
    server = start_pypi_timemachine("2023-10-01")
    input("Press Enter to stop the server...")
    server.stop()