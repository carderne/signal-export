# signal-export
Forked from https://github.com/mattsta/signal-backup  
Use to extract messages from Signal desktop client.

## Usage
First clone and install requirements (preferably into a virtualenv):
```
git clone https://github.com/carderne/signal-backup.git
cd signal-backup
pip install -r requirements.txt
```

Then use the script as follows (script should automatically locate your Signal directory):
```
Usage: sigexport.py [OPTIONS] [DST]

  Read the Signal directory and output .json and .html files to DST
  directory. Assumes the following default directories, can be over-ridden
  wtih --config.

  Default Signal directories:
   - Linux: ~/.config/Signal
   - macOS: ~/Library/Application Support/Signal
   - Windows: ~/AppData/Roaming/Signal

Options:
  -c, --config PATH  Path to Signal config and database
  --help             Show this message and exit.
```

Then either open the output html file in a browser, or do something with the JSON files.

## Troubleshooting
If you run into issues with `pysqlcipher3`, do as follows to fix:
```
sudo apt update
sudo apt install libsqlcipher-dev
git clone https://github.com/carderne/pysqlcipher3.git
cd pysqlcipher3
python setup.py install
```

