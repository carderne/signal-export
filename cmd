sig () {
    input=$(readlink -f $1)
    output=$(readlink -f $2)
    shift 2
    docker run -v $input:/tmp/Signal/ -v $output:/output -it carderne/signal-export:latest $@
}
