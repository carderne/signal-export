# signal-export
Export chats from the [Signal](https://www.signal.org/) [Desktop app](https://www.signal.org/download/) to markdown files with attachments. Each chat is exported as an individual .md file and the attachments for each are stored in a separate folder. Attachments are linked from the markdown files and can be previewed with something like [grip](https://github.com/joeyespo/grip) or [Typora](https://typora.io/).

Currently this seems to be the only way to get chat history out of Signal.

Forked from https://github.com/mattsta/signal-backup

## Example
An export for a group conversation looks as follows:
```markdown
[2019-05-29, 15:04] Me: How is everyone?
[2019-05-29, 15:10] Aya: We're great!
[2019-05-29, 15:20] Jim: I'm not.
```

Images are attached inline with `![name](path)` while other attachments (voice notes, videos, documents) are included as links like `[name](path)` so a click will take you to the file.

## Usage
First clone and install requirements (preferably into a virtualenv):
```
git clone https://github.com/carderne/signal-export.git
cd signal-export
pip install -r requirements.txt
```

Then use the script as follows:
```
Usage: ./sigexport.py [OPTIONS] [DEST]

Options:
  -s, --source PATH  Path to Signal config and database
  -o, --overwrite    Flag to overwrite existing output
  -m, --manual       Flag to manually decrypt the database
  --help             Show this message and exit.
```

This will attempt to find default Signal config location location for your OS and export to the given directory:
```
./sigexport.py exported
```

Add `--overwrite` to overwrite output files.

You can use `--source /path/to/source/files` if the script doesn't manage to find it. Default locations per OS:
- Linux: `~/.config/Signal`
- macOS: `~/Library/Application Support/Signal`
- Windows: `~/AppData/Roaming/Signal`


## Troubleshooting
If you run into issues with `pysqlcipher3` on Ubuntu/Linux (e.g. you get the error `pysqlcipher3.dbapi2.DatabaseError: file is encrypted or is not a database`) then do the following:
```
sudo apt update
sudo apt install libsqlcipher-dev libssl-dev sqlcipher
git clone https://github.com/carderne/pysqlcipher3.git
pip uninstall pysqlcipher3
cd pysqlcipher3
python setup.py install
```

And then try the script again
```
./sigexport.py --overwrite exported
```

## Still not working?
If you **stil** get issues, then we need to do manually decrypt the database. The following should work to get sqlcipher manually installed (from [this](https://stackoverflow.com/a/25132478) StackOverflow answer):
```
sudo apt remove sqlcipher
```

Then clone [sqlcipher](https://github.com/sqlcipher/sqlcipher) and install it:
```
git clone https://github.com/sqlcipher/sqlcipher.git
cd sqlcipher
mkdir build && cd build
../configure --enable-tempstore=yes CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto"
sudo make install
```

Then rerun the tool as follows. This will manually decrypt the database to a `db-decrypted.sqlite` file and use that to create the export (the decrypted database is deleted afterwards).
```
./sigexport.py --overwrite --manual exported
```

## TODO
- [ ] Better way to merge with previous experts. Could [potentially use](https://stackoverflow.com/a/6297993) `sort -k1.1,2.6 -u`, except in long messages there are lines without datetime stamps, so it breaks. Probably need Python solution, that considers subsequent lines as part of that line.
- [ ] Html output: header, basic stylesheet, inline videos and voice notes. Should be a post-proc step after markdown. Each line that starts with `[` gets a or something, format date nicely etc.
