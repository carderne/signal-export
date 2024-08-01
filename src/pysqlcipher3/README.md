# pysqlcipher3

Source: https://github.com/rigglemania/pysqlcipher3/

All files in this tree include their original copyright statements.

Vendored to make static builds easier.

Build on macOS:
```bash
export LDFLAGS="-L/opt/homebrew/opt/openssl@3/lib"
export CPPFLAGS="-I/opt/homebrew/opt/openssl@3/include"
python setup.py bdist_wheel

# or
python -m build
```
