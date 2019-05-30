# signal-export
Export your Signal chats to markdown files with attachments. Each chat is exported as an individual .md file and the attachments for each are stored in a separate folder. Attachments are linked from the markdown files and can be previewed with something like [grip](https://github.com/joeyespo/grip).

Forked from https://github.com/mattsta/signal-backup

## Usage
First clone and install requirements (preferably into a virtualenv):
```
git clone https://github.com/carderne/signal-export.git
cd signal-export
pip install -r requirements.txt
```

Then use the script as follows (script should automatically locate your Signal directory):
```
Usage: sigexport.py [OPTIONS] [DST]

  Read the Signal directory and output attachments and chat files to DST
  directory. Assumes the following default directories, can be over-ridden
  wtih --config.

  Default Signal directories:
   - Linux: ~/.config/Signal
   - macOS: ~/Library/Application Support/Signal
   - Windows: ~/AppData/Roaming/Signal

Options:
  -c, --config PATH  Path to Signal config and database
  -o, --overwrite    Flag to overwrite existing output
  --help             Show this message and exit.
```

## Troubleshooting
If you run into issues with `pysqlcipher3`, do as follows to fix:
```
sudo apt update
sudo apt install libsqlcipher-dev
git clone https://github.com/carderne/pysqlcipher3.git
cd pysqlcipher3
python setup.py install
```
