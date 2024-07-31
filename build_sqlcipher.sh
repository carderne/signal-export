#!/bin/bash

apt-get update && apt-get install -y git gcc libsqlite3-dev tclsh libssl-dev libc6-dev make

git clone --depth=1 --branch=master https://github.com/sqlcipher/sqlcipher.git && \
  cd sqlcipher && \
  ./configure --enable-tempstore=yes \
    CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto -lsqlite3" && \
  make sqlite3.c
