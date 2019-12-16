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

Then use the script as follows (script should automatically locate your Signal directory):
```
Usage: ./sigexport.py [OPTIONS] [DST]

  Read the Signal directory and output attachments and chat files to DST
  directory. Assumes the following default directories, can be overridden
  wtih --config.

  Deafault for DST is a sub-directory output/ in the current directory.

  Default Signal directories:
   - Linux: ~/.config/Signal
   - macOS: ~/Library/Application Support/Signal
   - Windows: ~/AppData/Roaming/Signal

Options:
  -c, --config PATH  Path to Signal config and database
  -o, --overwrite    Flag to overwrite existing output
  -m, --manual       Flag to manually decrypt the database
  --help             Show this message and exit.
```

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

If you **stil** get issues, then we need to do manually decrypt the database. The following should work to get sqlcipher manually installed (from [this](https://stackoverflow.com/a/25132478) SO answer):
```
sudo apt remove sqlcipher
sudo apt install libssl-dev
```

Then clone [sqlcipher](https://github.com/sqlcipher/sqlcipher) somewhere and install it:
```
cd ~/Downloads
git clone https://github.com/sqlcipher/sqlcipher.git
mkdir build && cd build
../sqlcipher/configure --enable-tempstore=yes CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto";
make install
```

Then rerun the tool as follows. This will manually decrypt the database to a `db-decrypted.sqlite` file and use that to create the export (the decrypted database is deleted afterwards).
```
./sigexport.py --overwrite --manual
```
