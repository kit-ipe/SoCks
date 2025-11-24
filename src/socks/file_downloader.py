import sys
import pathlib
import urllib
from dateutil import parser
import requests
import tqdm
import hashlib

import socks.pretty_print as pretty_print


class File_Downloader:
    """
    A class for downloading files
    """

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
            RuntimeError:
                If it isn't possible to retrieve the HTTP header or if the header doesn't contain the required info.
        """

        # Send a HEAD request to get the HTTP headers
        response = requests.head(url, allow_redirects=True)

        # Check if the header is valid
        if response.status_code != 200:
            raise RuntimeError(
                f"The HTTP headers for the following URL cannot be retrieved: {url}\n"
                f"HTTP status code {response.status_code}"
            )

        # Get timestamp of the file online
        last_mod_online = response.headers.get("Last-Modified")

        if not last_mod_online:
            raise RuntimeError(f"No 'Last-Modified' entry found in the header of {url}")

        return parser.parse(last_mod_online).timestamp()

    @staticmethod
    def get_file(url: str, output_dir: pathlib.Path) -> pathlib.Path:
        """
        Downloads a single file.

        Args:
            url:
                File URL.
            output_dir:
                Target directory in which the downloaded file is to be stored.

        Returns:
            Path of the downloaded file.

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

        # Send a HEAD request to get the HTTP headers
        response = requests.head(url, allow_redirects=True)

        # Retrieve name of the file
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
        try:
            download_progress.t = None
            print(f"Downloading {filename}...")
            download_location = output_dir / filename
            urllib.request.urlretrieve(url=url, filename=download_location, reporthook=download_progress)
            if download_progress.t:
                download_progress.t.close()
        except urllib.error.HTTPError as e:
            pretty_print.print_error(f"Unable to download file from {url}\n{e}")
            sys.exit(1)

        # Return path of the downloaded file
        return download_location

    @staticmethod
    def get_checksum(url: str, hash_function: str) -> str:
        """
        Calculate checksum of a single file.

        Args:
            url:
                File URL.
            hash_function:
                The hash function to be used. Must be supported by hashlib.

        Returns:
            Hash value of the file.

        Raises:
            RuntimeError:
                If it is not possible to retrieve the file name.
        """

        # Open the URL and read the entire file into memory
        with urllib.request.urlopen(url) as response:
            file_data = response.read()

        # Calculate hash value
        hash_obj = hashlib.new(hash_function)
        hash_obj.update(file_data)

        return hash_obj.hexdigest()
