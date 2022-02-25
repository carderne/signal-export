# This is a utility function to make running the Docker image easier
signalexport () {
    if [[ -z "$1" ]]; then
        echo 'Must provide output path as first parameters'
        echo 'e.g. signalexport output'
    else
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            input="$HOME/.config/Signal/"
        elif [[ "$OSTYPE" == "darwin"* ]]; then
            input="$HOME/Library/Application Support/Signal/"
        else
            input="$HOME/AppData/Roaming/Signal/"
        fi

        output=$(realpath $1)
        shift 1
        docker run --rm -it --name signal-export \
          -v "$input:/Signal" \
          -v "$output:/output" \
          carderne/signal-export:latest $@
    fi
}
