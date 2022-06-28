#!/home/<username>/.pyenv/versions/3.9.9/bin/python

# Inspired by
# - https://github.com/anuragrana/Python-Scripts/blob/master/Convert-Ebook-To-Kindle-Format.py
# - https://gist.github.com/vaind/14061727a20400dea625cecf5ddc3132

import subprocess, os, sys, base64, time, logging
from typing import List

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (Mail, Attachment, FileContent, FileName, FileType, Disposition)

from dotenv import dotenv_values

logger = logging.getLogger(__name__)

logger.info("Custom script started.")

# /home/<username>
cwd = os.getcwd()
project_path = os.path.join(cwd, "scripts/readarr_send_to_kindle/")
# Regular environment variables are strip out by readarr
environment_variables = dotenv_values(f"{project_path}.env")

IGNORED_EXTENSIONS = ["pdf", "m4b", "mp3"]
OUTPUT_FORMAT = "mobi"
RETRIES = 5

book_path = os.environ.get("readarr_addedbookpaths")
event_type = os.environ.get("readarr_eventtype")
api_key = environment_variables.get("READARR_SNDGRD_AP_KY")
kindle_email = environment_variables.get("READARR_KINDLE_EMAIL")
from_email = environment_variables.get("READARR_FROM_EMAIL")

if not api_key: sys.exit("SendGrid API Key doesn't exists")
if event_type == "Test":
    logger.info("Closing the program because we are in Readarr's test environment")
    sys.exit(0)
if not book_path: sys.exit("Book path doesn't exists")
if not event_type: sys.exit("There's no event type to work with")
if event_type != "Download":
    logger.warning("readarr_eventtype should be 'Download' but %s was returned", event_type)
    sys.exit(0)


def get_folder(filepath: str) -> str:
    """Get the folder of the file.

    The `/` is necessary for when we want
    to leave only the filename from the directory.
    Without `/` at the end, the filename would be `/filename`
    which is not convenient.
    """
    return os.path.dirname(filepath) + "/"


def get_original_filename(filepath: str) -> str:
    """Get the filename from filepath. Exclude the directory."""
    folder = get_folder(filepath)
    filename = filepath.replace(folder, "")
    return filename


def get_filename_part(filename: str) -> str:
    """Get the filename without extension."""
    dot_splitted = filename.split(".")
    return ".".join(dot_splitted[0:-1])


def get_filename_ext(filename: str) -> str:
    """Get the extension of the file"""
    return filename.split(".")[-1]


def get_converted_filename(filename: str) -> str:
    """The name of the resulting file after conversion"""
    filename_part = get_filename_part(filename)
    converted_filename = f"{filename_part}.{OUTPUT_FORMAT}"
    return converted_filename


def get_all_filenames_in_dir(current_dir: str) -> List[str]:
    """Get all the filenames that exists in current book dir"""
    return [
        get_original_filename(filepath)
        for filepath in os.listdir(current_dir)
    ]


folder = get_folder(book_path)
filename = get_original_filename(book_path)
filename_part = get_filename_part(filename)
ext = get_filename_ext(filename)
current_filenames = get_all_filenames_in_dir(folder)
converted_filename = get_converted_filename(filename)
new_book_path = folder + converted_filename

if ext.lower() in IGNORED_EXTENSIONS:
    logger.info("Closing the program because %s is an ignored extension", ext.lower())
    sys.exit(0)


if converted_filename in current_filenames:
    logger.info("Closing the program because %s already exists", converted_filename)
    sys.exit(0)


# Conversion to mobi
logger.info("Starting book conversion to mobi")
calibre_bin_path = os.path.join(cwd, "calibre-bin/calibre/")
result = subprocess.call([f"{calibre_bin_path}ebook-convert", book_path, new_book_path])


if int(result) != 0:
    logger.critical("ebook-convert raised the following error: %s", result)
    sys.exit("Conversion raised and error.")


file_is_ready = False
try_counter = 1


while not file_is_ready and try_counter <= RETRIES:
    current_filenames = get_all_filenames_in_dir(folder)
    if converted_filename not in current_filenames:
        try_counter += try_counter
        time.sleep(1)
        continue

    file_is_ready = True


if not file_is_ready:
    logger.critical("Converted file wasn't saved in directory: %s", folder)
    sys.exit("Ebook conversion failed.")


logger.info("Sending converted ebook through email.")
message = Mail(
    from_email=from_email, to_emails=kindle_email,
    subject='Send To Kindle', html_content='Send To Kindle'
)


with open(new_book_path, 'rb') as f:
    data = f.read()
    f.close()


encoded_file = base64.b64encode(data).decode()


attachedFile = Attachment(
    FileContent(encoded_file),
    FileName(converted_filename),
    FileType('text/html'),
    Disposition('attachment')
)
message.attachment = attachedFile
sg = SendGridAPIClient(api_key)
response = sg.send(message)

# delete mobi file
logger.info("Ebook sended. Deleting mobi file now...")
os.remove(new_book_path)

logger.info("Custom script done.")
