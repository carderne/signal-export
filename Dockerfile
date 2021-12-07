FROM python:3.9.7

ENV PYTHONUNBUFFERED=1

ENV LD_LIBRARY_PATH=/usr/local/lib

RUN git clone --depth=1 --branch=master https://github.com/sqlcipher/sqlcipher.git && \
  cd sqlcipher && \
  ./configure --enable-tempstore=yes \
    CFLAGS="-DSQLITE_HAS_CODEC" LDFLAGS="-lcrypto -lsqlite3" && \
  make && \
  make install

RUN pip3 install \
    beautifulsoup4==4.8.2 \
    typer==0.4.0 \
    emoji==1.4.2 \
    Markdown==3.0 \
    pysqlcipher3==1.0.4

COPY . signal-export/
RUN pip3 install --use-feature=in-tree-build ./signal-export/

RUN groupadd dummy -g1000 && useradd dummy -u1000 -g1000

COPY docker_entry.sh .

ENTRYPOINT ["./docker_entry.sh"]
