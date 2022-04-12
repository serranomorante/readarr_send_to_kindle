#!/home/$USER/.pyenv/shims/python

# Inspired by
# https://github.com/anuragrana/Python-Scripts/blob/master/Convert-Ebook-To-Kindle-Format.py
# and
# https://gist.github.com/vaind/14061727a20400dea625cecf5ddc3132

import subprocess, os, sys, base64, time
from typing import List

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import (Mail, Attachment, FileContent, FileName, FileType, Disposition)

from dotenv import load_dotenv

load_dotenv()

IGNORED_EXTENSIONS = ["pdf", "m4b", "mp3"]
OUTPUT_FORMAT = "mobi"
RETRIES = 5

book_path = os.environ.get("readarr_addedbookpaths")
event_type = os.environ.get("readarr_eventtype")
api_key = os.getenv("READARR_SNDGRD_AP_KY")
kindle_email = os.getenv("READARR_KINDLE_EMAIL")
from_email = os.getenv("READARR_FROM_EMAIL")


if not api_key:
    print("SendGrid API Key doesn't exists")
    sys.exit(0)

    
if event_type == "Test":
    sys.exit(0)


if not book_path:
    sys.exit(0)


if not event_type:
    sys.exit(0)


if event_type != "Download":
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
    sys.exit(0)


if converted_filename in current_filenames:
    sys.exit(0)


# Convert to mobi
result = subprocess.call(["/home/$USER/calibre-bin/calibre/ebook-convert", book_path, new_book_path])


if int(result) != 0:
    print(f"ebook-convert raised error: {result}")
    sys.exit(0)


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
    print(f"Converted file doesn't exist in current directory: {folder}")
    sys.exit(0)


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
os.remove(new_book_path)
