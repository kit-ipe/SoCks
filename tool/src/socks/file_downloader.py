import pathlib
import urllib
import requests
import tqdm

import socks.pretty_print as pretty_print


class File_Downloader:
    """
    A class for downloading files
    """

    @staticmethod
    def _check_status_code(url: str) -> str:
        """
        Stops the program execution if the status code is not 200 (OK).

        Args:
            url:
                File URL.

        Returns:
            None

        Raises:
            None
        """

        # Send a HEAD request to get the HTTP headers
        response = requests.head(url, allow_redirects=True)

        if response.status_code == 404:
            # File not found
            pretty_print.print_error(
                f"The following file is not available: {url}\nStatus code {response.status_code} (File not found)"
            )
            sys.exit(1)
        elif response.status_code != 200:
            # Unexpected status code
            pretty_print.print_error(
                f"The following file is not available: {url}\nUnexpected status code {response.status_code}"
            )
            sys.exit(1)

    @staticmethod
    def get_last_modified(url: str) -> str:
        """
        Fetches the Last-Modified timestamp, if available.

        Args:
            url:
                File URL.

        Returns:
            The Last-Modified timestamp.

        Raises:
            None
        """

        File_Downloader._check_status_code(url)

        # Send a HEAD request to get the HTTP headers
        response = requests.head(url, allow_redirects=True)

        # Get timestamp of the file online
        last_mod_online = response.headers.get("Last-Modified")

        if not last_mod_online:
            pretty_print.print_error(f"No 'Last-Modified' header found for {url}")
            sys.exit(1)

        return parser.parse(last_mod_online).timestamp()

    @staticmethod
    def get_file(url: str, output_dir: pathlib.Path) -> dict:
        """
        Downloads a single file.

        Args:
            url:
                File URL.
            output_dir:
                Target directory in which the downloaded file is to be stored.

        Returns:
            None

        Raises:
            RuntimeError:
                If it is not possible to retrieve the file name.
        """

        # Progress callback function to show a status bar
        def download_progress(block_num, block_size, total_size):
            if download_progress.t is None:
                download_progress.t = tqdm.tqdm(total=total_size, unit="B", unit_scale=True, unit_divisor=1024)
            downloaded = block_num * block_size
            download_progress.t.update(downloaded - download_progress.t.n)

        File_Downloader._check_status_code(url)

        # Retrieve name of the file
        # Send a HEAD request to get the HTTP headers
        response = requests.head(url, allow_redirects=True)

        # Check the Content-Disposition header
        content_disposition = response.headers.get("Content-Disposition")
        if content_disposition and "filename=" in content_disposition:
            # Extract the filename from the header
            filename = content_disposition.split("filename=")[1].strip('"')
        else:
            # Fallback to extracting the filename from the URL
            filename = pathlib.Path(urllib.parse.urlparse(url=url).path).name

        if not filename:
            raise RuntimeError("Unable to retrieve file name")

        # Download the file
        download_progress.t = None
        print(f"Downloading {filename}...")
        urllib.request.urlretrieve(url=url, filename=output_dir / filename, reporthook=download_progress)
        if download_progress.t:
            download_progress.t.close()
