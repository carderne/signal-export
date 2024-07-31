#!/bin/bash

apt-get update && apt-get install -y git gcc libsqlite3-dev tclsh libssl-dev libc6-dev make

git clone --depth=1 --branch=master https://github.com/sqlcipher/sqlcipher.git
cd sqlcipher && \
  ./configure --enable-tempstore=yes \
    CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto -lsqlite3" && \
  make sqlite3.c && \
  cd ..

git clone --depth=1 --branch=master https://github.com/rigglemania/pysqlcipher3.git
cd pysqlcipher3 && \
  mkdir amalgamation && \
  cp ../sqlcipher/sqlite3.[ch] amalgamation && \
  mkdir src/python3/sqlcipher && \
  cp ../sqlcipher/sqlite3.[ch] src/python3/sqlcipher && \
  python setup.py build_amalgamation && \
  python setup.py build && \
  cd ..

mkdir src/pysqlcipher3
for f in pysqlcipher3/build/lib.*/pysqlcipher3/*.{py,so}; do
  cp $f src/pysqlcipher3
done
