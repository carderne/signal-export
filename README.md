# signal-export
[![cicd](https://github.com/carderne/signal-export/actions/workflows/cicd.yml/badge.svg)](https://github.com/carderne/signal-export/actions/workflows/cicd.yml)
[![PyPI version](https://badge.fury.io/py/signal-export.svg)](https://pypi.org/project/signal-export/)

Export chats from the [Signal](https://www.signal.org/) [Desktop app](https://www.signal.org/download/) to Markdown and HTML files with attachments. Each chat is exported as an individual .md/.html file and the attachments for each are stored in a separate folder. Attachments are linked from the Markdown files and displayed in the HTML (pictures, videos, voice notes).

Currently this seems to be the only way to get chat history out of Signal!

Adapted from [mattsta/signal-backup](https://github.com/mattsta/signal-backup), which I suspect will be hard to get working now.

## Example
An export for a group conversation looks as follows:
```markdown
[2019-05-29, 15:04] Me: How is everyone?
[2019-05-29, 15:10] Aya: We're great!
[2019-05-29, 15:20] Jim: I'm not.
```

Images are attached inline with `![name](path)` while other attachments (voice notes, videos, documents) are included as links like `[name](path)` so a click will take you to the file.

This is converted to HTML at the end so it can be opened with any web browser. The stylesheet `.css` is still very basic but I'll get to it sooner or later.

## 🚀 Installation with Docker
This tool has some pretty difficult dependencies, so it's easier to get some help from Docker.
For most people this will probably be the easiest way.
It requires installing Docker and then pulling a [200MB image](https://hub.docker.com/r/carderne/sigexport), so avoid this if data use is a concern.

First off, [install Docker](https://docs.docker.com/get-docker/) (including following the [post-installation steps](https://docs.docker.com/engine/install/linux-postinstall/) for managing Docker as a non-root user).  
And make sure you have Python installed.

Then install this package:
```bash
pip install signal-export
```

Then run the script!
It will do some Docker stuff under the hood to get your data out of the encrypted database.
```bash
sigexport ~/signal-chats
# output will be saved to the supplied directory
```

**NB** On Windows/PowerShell, you may get an error like `term 'sigexport' is not recognized`, in which case you can use the following:
```bash
python -m sigexport.main ~/signal-chats
```

## Usage
Please fully exit your Signal app before proceeding, otherwise you will likely encounter an `I/O disk` error, due to the message database being made read-only, as it was being accessed by the app.

See the full help info:
```bash
sigexport --help
```

Disable pagination on HTML, and overwrite anything at the destination:
```bash
sigexport --paginate=0 --overwrite ~/signal-chats
```

List available chats and exit:
```bash
sigexport --list-chats
```

Export only the selected chats:
```bash
sigexport --chats=Jim,Aya ~/signal-chats
```

You can add `--source /path/to/source/dir/` if the script doesn't manage to find the Signal config location.
Default locations per OS are below.
The directory should contain a folder called `sql` with `db.sqlite` inside it.
- Linux: `~/.config/Signal/`
- macOS: `~/Library/Application Support/Signal/`
- Windows: `~/AppData/Roaming/Signal/`

You can also use `--old /previously/exported/dir/` to merge the new export with a previous one.
_Nothing will be overwritten!_
It will put the combined results in whatever output directory you specified and leave your previos export untouched.
Exercise is left to the reader to verify that all went well before deleting the previous one.

## 🗻 No-Python install
I don't recommend this, and you will have issues with file-ownership and other stuff.
You can also run the Docker image directly, it just requires copy-pasting a much-longer command and being careful with volume mounts.

First set the appropriate environment variables for your OS:
```bash
# Only enter one of these!
SIGNAL_INPUT="$HOME/.config/Signal"                             # Linux
SIGNAL_INPUT="$HOME/snap/signal-desktop/current/.config/Signal" # Snap
SIGNAL_INPUT="$HOME/Library/Application Support/Signal"         # macOS
SIGNAL_INPUT="$HOME/AppData/Roaming/Signal"                     # Powershell

# And your output location (must be an absolute path)
SIGNAL_OUTPUT="$HOME/Downloads/signal-output"
```

Then run the below command, which pulls in the environment variables you set above.
```bash
# Note that the --overwrite flag is necessary when running like this
# careful where you point it!
docker run --rm \
  -v "$SIGNAL_INPUT:/Signal" \
  -v "$SIGNAL_OUTPUT:/output" \
    carderne/sigexport:latest \
    --overwrite /output \         # this line is obligatory!
    --chats Jim                   # this line isn't
```

## 🗻 BYOD (Build-Your-Own-Docker) image
Running this script using the methods above requires you to trust that I haven't snuck anything into the Docker image.
You can inspect the code in this repo, and after `pip install`ing, you can confirm that the code installed on your computer matches this repo.
But the methods above rely on the [Docker image](https://hub.docker.com/r/carderne/sigexport), which is a bit more complex.

You can check the [Dockerfile](./Dockerfile) in this repo, and the [GitHub Actions workflow](./.github/workflows/cicd.yaml).
You can check that the last [Actions run](https://github.com/carderne/signal-export/actions) matches the time on the last push to the DockerHub registry.
But you can't guarantee that I didn't sneak something in, so the next thing is to check the image itself.

So you can run `docker inspect carderne/sigexport` and check the `Entrypoint` and `Cmd` values.
Then you can run `docker run --rm -it --entrypoint='' carderne/sigexport bash` and check what Entrypoint/Cmd values correspond to inside the container, and check that _that_ matches the repo!

You can also just build your own Docker image from this repo:
```bash
git clone https://github.com/carderne/signal-export.git
cd signal-export
docker build -t yourname/sigexport .
```

And _then_ run the Python script, but tell it to use the image you just created:
```bash
sigexport --docker-image yourname/sigexport outputdir/
```


## 🌋 No-Docker install
This is hard mode, and involves installing more stuff.
Probably easy on macOS, slightly involved on Linux, and impossible on Windows.

Before you can install `signal-export`, you need to get `sqlcipher` working.
Follow the instructions for your OS:

### Ubuntu (other distros can adapt to their package manager)
Install the required libraries.
```bash
sudo apt install libsqlite3-dev tclsh libssl-dev
```

Then clone [sqlcipher](https://github.com/sqlcipher/sqlcipher) and install it:
```bash
git clone https://github.com/sqlcipher/sqlcipher.git
cd sqlcipher
./configure --enable-tempstore=yes CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto -lsqlite3"
make && sudo make install
```

### macOS
- Install [Homebrew](https://brew.sh).
- Run `brew install openssl sqlcipher`

### Windows
Ubuntu on WSL2 should work!
That is, install WSL2 and Ubuntu on Windows, and then follow the **For Linux** instructions and feel your way forward.
But probably just give up here and use the Docker method instead.

### Install signal-export
Then you're ready to install signal-export:
(Note the `[sql]` that has been added!)
```bash
pip install signal-export[sql]
```

Then you should be able to use the [Usage instructions](#usage) as above.

## Development
```bash
git clone https://github.com/carderne/signal-export.git
cd signal-export
pip install -e .[dev,sql]
pre-commit install
```

Run tests with:
```bash
make test
```

And check types with:
```bash
mypy sigexport/
```

## Similar things
- [signal-backup-decode](https://github.com/pajowu/signal-backup-decode) might be easier if you use Android!
- [signal2html](https://github.com/GjjvdBurg/signal2html) also Android only
