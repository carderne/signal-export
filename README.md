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
### 🚀 Easy mode (maybe?): Docker
This tool has some pretty difficult dependencies, and so a generous contributor added a Dockerfile! For most people this will probably be the easiest way. It requires installing Docker and then pulling a large image, so avoid this if data use is a concern.

First off, [install Docker](https://docs.docker.com/get-docker/).

Then set your input location depending on your OS.
It could even be something different from the below, so figure it out!
```bash
SIGNAL_INPUT=~/.config/Signal                         # Linux
SIGNAL_INPUT="~/Library/Application Support/Signal"   # macOS
SIGNAL_INPUT="~/AppData/Roaming/Signal"               # Windows
```

And your output location (again, just use one of these!).
You can't just specify a subdirectory or Docker will complain!
```bash
SIGNAL_OUTPUT=~/Documents/output     # specify relative to home dir
SIGNAL_OUTPUT=/path/to/output        # or specify the full path
```

Then run the following command:
```bash
docker run --rm -it --name signal-export \
  -v ${SIGNAL_INPUT}:/Signal \
  -v ${SIGNAL_OUTPUT}:/output \
  carderne/signal-export:latest
```

You can also pass command line arguments to the script as normal, e.g.:
```bash
docker run --rm -it --name signal-export \
  -v ${SIGNAL_INPUT}:/Signal \
  -v ${SIGNAL_OUTPUT}:/output \
  carderne/signal-export:latest --overwrite --chats=Jim
```

#### A helpful shortcut
If you want to make your life even easier, then add the following snippet to your `.bashrc` (or equivalent):
```bash
signalexport () {
    if [[ -z "$1" || -z "$2" ]]; then
        echo 'Must provide input path and input path as first two parameters'
        echo 'e.g. signalexport ~/.config/Signal output/'
    else
        input=$(readlink -f $1)
        output=$(readlink -f $2)
        shift 2
        docker run --rm -it --name signal-export \
          -v $input:/Signal \
          -v $output:/output \
          carderne/signal-export:latest $@
    fi
}
```

Then resource your `.bashrc` as follows:
```bash
source ~/.bashrc
```

And then you can simply run the following.
(And have some Docker annoyances ironed out).
```bash
signalexport ~/.config/Signal output --overwrite --chats=Jim
```

### 🦆 Slightly harder: build your own Docker image
You can always build your own Docker image if you prefer that.
Just clone this repository and build it.
```bash
git clone https://github.com/carderne/signal-export.git
cd signal-export
docker build -t carderne/signal-export:latest .
```

(You can obviously give it a different name and drop the `carderne` bit!)

### 🌋 Hard mode: install stuff
This involves actually installing the stuff into your system, but has proven hard to get work for many, especially on Windows.

Before you can install `signal-export`, you need to get `sqlcipher` working.
Follow the instructions for your OS:

#### For Ubuntu (other distros can adapt to their package manager)
Install the required libraries.
```
sudo apt install libsqlite3-dev libsqlite3-dev tclsh libssl-dev
```

Then clone [sqlcipher](https://github.com/sqlcipher/sqlcipher) and install it:
```
git clone https://github.com/sqlcipher/sqlcipher.git
cd sqlcipher
./configure --enable-tempstore=yes CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto -lsqlite3"
make && sudo make install
```

#### For MacOS
- Install [Homebrew](https://brew.sh).
- Run `brew install openssl sqlcipher`

#### For Windows
YMMV, but apparently Ubuntu 20.04 on WSL2 should work!
That is, install WSL2 and Ubuntu 20.04 on Windows, and then follow the **For Linux** instructions and feel your way forward.
But probably just give up here and use the Docker method instead.

### Install signal-export
Then you're ready to install signal-export:
```
pip install git+https://github.com/carderne/signal-export.git
```

## Usage
The below refer to running the script normally.
If you installed using Docker, then this will give you an overview of the command-line options you can use.
Just note that with the Docker method, you can't specify the `output` and `--source` directories as command-line options, as they are handled by the `docker_entry.sh` script.

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

