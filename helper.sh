# This is a utility function to make running the Docker image easier
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
