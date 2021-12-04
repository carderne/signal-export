# signal-export
Export chats from the [Signal](https://www.signal.org/) [Desktop app](https://www.signal.org/download/) to Markdown and HTML files with attachments. Each chat is exported as an individual .md/.html file and the attachments for each are stored in a separate folder. Attachments are linked from the Markdown files and displayed in the HTML (pictures, videos, voice notes).

Currently this seems to be the only way to get chat history out of Signal!

Adapted from https://github.com/mattsta/signal-backup, which I suspect will be hard to get working now.

## Example
An export for a group conversation looks as follows:
```markdown
[2019-05-29, 15:04] Me: How is everyone?
[2019-05-29, 15:10] Aya: We're great!
[2019-05-29, 15:20] Jim: I'm not.
```

Images are attached inline with `![name](path)` while other attachments (voice notes, videos, documents) are included as links like `[name](path)` so a click will take you to the file.

This is converted to HTML at the end so it can be opened with any web browser. The stylesheet `.css` is still very basic but I'll get to it sooner or later.

## Installation
Before you can install `signal-export`, you need to get `sqlcipher` working. Follow the instructions for your OS:

### For Linux

Before you can install the pip requirements, you need to get sqlcipher working. For that you need to compile it from source on Debian based distributions to get a recent version:
```
sudo apt install libsqlite3-dev libsqlite3-dev tclsh libssl-dev
```

Then clone [sqlcipher](https://github.com/sqlcipher/sqlcipher) and install it:
```
git clone https://github.com/sqlcipher/sqlcipher.git
cd sqlcipher
./configure --enable-tempstore=yes CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto -lsqlite3"
make
sudo make install
```

### For MacOS
- Install [Homebrew](https://brew.sh).
- Run `brew install openssl sqlcipher`

### For Windows
YMMV, but apparently Ubuntu 20.04 on WSL2 should work! That is, install WSL2 and Ubuntu 20.04 on Windows, and then follow the **For Linux** instructions and feel your way forward.

### Install signal-export
Install signal-export from GitHub:
```
pip install git+https://github.com/carderne/signal-export.git
```

## Usage
The following should work:
```
sigexport outputdir
```

To create HTML with no pagination:
```
sigexport outputdir -p0
```

If you get an error:

    pysqlcipher3.dbapi2.DatabaseError: file is not a database

try adding the `--manual` option.

The full options are below:
```
Usage: sigexport [OPTIONS] DEST

Arguments:
  DEST  [required]

Options:
  --source PATH           Path to Signal source database
  --old PATH              Path to previous export to merge
  -o, --overwrite         Overwrite existing output  [default: False]
  -p, --paginate INTEGER  Messages per page in HTML; set to 0 for infinite
                          [default: 100]
  --chats TEXT            Comma-separated chat names to include: contact names
                          or group names
  -l, --list-chats        List available chats and exit  [default: False]
  -m, --manual            Attempt to manually decrypt DB  [default: False]
  -v, --verbose           [default: False]
  --help                  Show this message and exit.
```

You can add `--source /path/to/source/dir/` if the script doesn't manage to find the Signal config location. Default locations per OS are below. The directory should contain a folder called `sql` with a `db.sqlite` inside it.
- Linux: `~/.config/Signal/`
- macOS: `~/Library/Application Support/Signal/`
- Windows: `~/AppData/Roaming/Signal/`

You can also use `--old /previously/exported/dir/` to merge the new export with a previous one. _Nothing will be overwritten!_ It will put the combined results in whatever output directory you specified and leave your previos export untouched. Exercise is left to the reader to verify that all went well before deleting the previous one.

## Development
```
git clone https://github.com/carderne/signal-export.git
cd signal-export
pip install -e .[dev]
pre-commit install
```

Run tests with:
```
tox
```

## Docker image
```
docker build --rm -t signal-export:latest .
```
The docker image can be used with any command line arguments to signal-export as an alternative to installing sqlcipher and other dependencies directly, and should work on at least any x64 system.
```
SIGNAL_DATA_PATH=/path/to/Signal  # where your Signal data directory is located
OUTPUT_DIR=/path/to/output        # a directory where you want the data to be exported to
OUTPUT_NAME=`date +%Y%m%d-%H%M`   # name of the directory for the export

docker run --rm --name signal-export -v ${SIGNAL_DATA_PATH}/:/tmp/Signal/ -v ${OUTPUT_DIR}/:/tmp/output/ -it signal-export:latest /tmp/output/${OUTPUT_NAME} --source /tmp/Signal
```
Command line arguments can also be passed to the container as normal
```
docker run --rm --name signal-export -v ${SIGNAL_DATA_PATH}/:/tmp/Signal/ -v ${OUTPUT_DIR}/:/tmp/output/ -it signal-export:latest /tmp/output/${OUTPUT_NAME} --source /tmp/Signal -v -p 0 --overwrite
```
