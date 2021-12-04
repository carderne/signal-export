FROM ubuntu:20.04
# install dependencies for sqlcipher
RUN export DEBIAN_FRONTEND=noninteractive ; apt update && apt -y install python3-pip libssl-dev tclsh git libsqlite3-dev
RUN cd /opt/ && git clone https://github.com/sqlcipher/sqlcipher.git && cd sqlcipher && ./configure --enable-tempstore=yes CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto -lsqlite3" && make && make install
ENV LD_LIBRARY_PATH=/usr/local/lib
RUN pip3 install git+https://github.com/carderne/signal-export.git
ENTRYPOINT ["sigexport"]
